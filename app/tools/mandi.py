"""Configurable Agmarknet adapter with transparent cache and sample fallbacks."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import httpx
import yaml

from app.schemas import FarmerProfile, ToolResult
from app.tools.cache import ToolCache, utcnow
from app.tools.weather import finite_number


class MandiTool:
    def __init__(self, settings, cache: ToolCache,
                 client: httpx.AsyncClient | None = None,
                 clock: Callable[[], datetime] = utcnow):
        self.settings, self.cache, self.client, self.clock = settings, cache, client, clock
        self.config = yaml.safe_load(settings.mandi_config_path.read_text(encoding="utf-8"))
        self.crops = yaml.safe_load(settings.crops_path.read_text(encoding="utf-8"))["crops"]

    def districts(self, profile: FarmerProfile) -> list[str]:
        nearby = self.config["nearby_districts"].get(profile.state, {}).get(profile.district, [])
        return list(dict.fromkeys([profile.district, *nearby]))

    def commodity(self, crop: str) -> str:
        return self.crops.get(crop.casefold(), {}).get("mandi_commodity", crop)

    def _date(self, value: str) -> str:
        for pattern in self.config["date_formats"]:
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                continue
        raise ValueError("Unrecognized arrival date")

    def normalize(self, raw: dict) -> dict:
        fields = self.config["fields"]
        row = {name: str(raw.get(field, "")).strip() for name, field in fields.items()}
        for name in ("min_price", "max_price", "modal_price"):
            row[name] = finite_number(str(row[name]).replace(",", ""))
        if not 0 < row["min_price"] <= row["modal_price"] <= row["max_price"]:
            raise ValueError("Inconsistent price range")
        if not all(row.get(name) for name in ("market", "district", "commodity", "state")):
            raise ValueError("Missing price provenance")
        row["arrival_date"] = self._date(row["arrival_date"])
        row["unit"] = self.config["unit"]
        return row

    def payload(self, rows: list[dict], profile: FarmerProfile, *, sample: bool,
                warnings: list[str] | None = None) -> dict:
        today = self.clock().astimezone(ZoneInfo("Asia/Kolkata")).date()
        max_days = self.settings.mandi_max_age_hours / 24
        stale = any(not 0 <= (today - datetime.fromisoformat(row["arrival_date"]).date()).days <= max_days
                    for row in rows)
        value = {"prices": rows, "sample": sample, "stale": stale,
                 "warnings": list(warnings or []), "unit": self.config["unit"],
                 "coverage": "Configured district and nearby districts; not a geospatial nearest-market search."}
        # Only compare same-day, same-variety, same-grade prices, using best local quote.
        local = [row for row in rows if row["district"].casefold() == profile.district.casefold()
                 and row.get("variety") and row.get("grade")]
        if local:
            anchor = max(local, key=lambda row: (row["arrival_date"], row["modal_price"]))
            comparable = [row for row in rows if all(row.get(key) == anchor.get(key)
                                                    for key in ("commodity", "variety", "grade", "arrival_date", "unit"))]
            if len({row["market"] for row in comparable}) >= 2:
                best = max(row["modal_price"] for row in comparable)
                value["local_modal_price"] = anchor["modal_price"]
                value["best_modal_price"] = best
                value["comparable_price_gap_pct"] = round((best - anchor["modal_price"]) / best * 100, 2)
        if stale:
            value["warnings"].append("Arrival dates are stale or in the future; do not use for a sale decision.")
        return value

    async def fetch(self, profile: FarmerProfile, crop: str) -> ToolResult:
        now = self.clock()
        key = f"mandi:{profile.state}:{profile.district}:{crop.casefold()}"
        fresh = self.cache.get(key, self.settings.mandi_ttl_seconds, now)
        if fresh:
            fresh.value = self.payload(fresh.value.get("prices", []), profile, sample=False,
                                       warnings=fresh.value.get("warnings", []))
            return fresh
        error = "Live mandi is not configured; verify the resource ID and supply an API key."
        key_value = self.settings.data_gov_api_key
        if hasattr(key_value, "get_secret_value"):
            key_value = key_value.get_secret_value()
        if key_value and self.settings.data_gov_resource_id:
            own_client = self.client is None
            client = self.client or httpx.AsyncClient()
            try:
                results = await asyncio.gather(
                    *(self._district(client, profile, district, crop, key_value)
                      for district in self.districts(profile)), return_exceptions=True,
                )
                rows, warnings = [], []
                for result in results:
                    if isinstance(result, BaseException):
                        warnings.append(f"One district unavailable ({type(result).__name__}).")
                    else:
                        rows.extend(result)
                if rows:
                    newest: dict[tuple, dict] = {}
                    for row in rows:
                        identity = tuple(row[key] for key in ("state", "district", "market", "commodity", "variety", "grade"))
                        if identity not in newest or row["arrival_date"] > newest[identity]["arrival_date"]:
                            newest[identity] = row
                    result = ToolResult(tool="mandi", value=self.payload(list(newest.values()), profile,
                                        sample=False, warnings=warnings),
                                        source="data.gov.in (Agmarknet)", fetched_at=now, confidence="medium")
                    self.cache.put(key, result)
                    return result
                error = "No matching live mandi records were returned."
                if warnings:
                    error = "Live mandi unavailable; falling back to saved data."
            finally:
                if own_client:
                    await client.aclose()
        cached = self.cache.get(key, now=now)
        if cached:
            cached.value = self.payload(cached.value.get("prices", []), profile, sample=False,
                                       warnings=[error, "Last successful price snapshot; check fetch and arrival dates."])
            if (now - cached.fetched_at).total_seconds() > self.settings.mandi_max_age_hours * 3600:
                cached.value["stale"] = True
            return cached
        return self.sample(profile, crop, reason=error)

    async def _district(self, client: httpx.AsyncClient, profile: FarmerProfile,
                        district: str, crop: str, api_key: str) -> list[dict]:
        api = self.config["api"]
        rows = []
        url = f"{self.settings.data_gov_base_url.rstrip('/')}/{self.settings.data_gov_resource_id}"
        for page in range(api["max_pages"]):
            params = {api["key_parameter"]: api_key, api["format_parameter"]: api["format_value"],
                      api["state_filter"]: profile.state, api["district_filter"]: district,
                      api["commodity_filter"]: self.commodity(crop),
                      api["limit_parameter"]: api["page_size"], api["offset_parameter"]: page * api["page_size"]}
            payload = None
            for attempt in range(self.settings.tool_retries + 1):
                try:
                    response = await client.get(url, params=params, timeout=self.settings.weather_timeout_seconds)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload.get(api["records_field"]), list):
                        raise ValueError("Missing records array")
                    break
                except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                    if attempt == self.settings.tool_retries:
                        raise
            records = payload[api["records_field"]]
            for raw in records:
                try:
                    row = self.normalize(raw)
                    if (row["state"].casefold() == profile.state.casefold()
                            and row["district"].casefold() == district.casefold()
                            and row["commodity"].casefold() == self.commodity(crop).casefold()):
                        rows.append(row)
                except (ValueError, TypeError, AttributeError):
                    continue
            if len(records) < api["page_size"]:
                break
        return rows

    def sample(self, profile: FarmerProfile, crop: str, reason: str = "Demo mode.",
               scenario: str = "rain") -> ToolResult:
        now = self.clock()
        if scenario in {"no_mandi", "api_failure"}:
            return ToolResult(tool="mandi", source="DEMO SCENARIO - mandi unavailable",
                              fetched_at=now, error="Simulated missing mandi data")
        try:
            with (self.settings.data_dir / "sample_mandi.csv").open(encoding="utf-8", newline="") as handle:
                raw_rows = list(csv.DictReader(handle))
            selected = [row for row in raw_rows
                        if row["state"].casefold() == profile.state.casefold()
                        and row["district"].casefold() in {district.casefold() for district in self.districts(profile)}
                        and row["commodity"].casefold() == self.commodity(crop).casefold()]
            if not selected:
                raise ValueError("No sample data for this crop and district")
            rows = [self.normalize(row) for row in selected]
            stamp = min(datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00")) for row in selected)
            if scenario == "stale_mandi":
                stamp = now - timedelta(days=10)
                rows = [dict(row, arrival_date=(now.date() - timedelta(days=10)).isoformat()) for row in rows]
            value = self.payload(rows, profile, sample=True,
                                 warnings=[reason, "SYNTHETIC SAMPLE - these are not market quotations."])
            return ToolResult(tool="mandi", value=value,
                              source="SAMPLE DATA - synthetic mandi prices, not market quotes",
                              fetched_at=stamp, is_cached=True, confidence="low")
        except (OSError, ValueError, KeyError, TypeError):
            return ToolResult(tool="mandi", source="data.gov.in (Agmarknet); sample fallback",
                              fetched_at=now, error="Live prices unavailable and no matching sample data")
