"""Open-Meteo forecast adapter; HTTP failures never become fabricated weather."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx

from app.schemas import FarmerProfile, ToolResult
from app.tools.cache import ToolCache, utcnow


def finite_number(value: object) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing numeric observation")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite observation")
    return number


class WeatherTool:
    def __init__(self, settings, cache: ToolCache,
                 client: httpx.AsyncClient | None = None,
                 clock: Callable[[], datetime] = utcnow):
        self.settings, self.cache, self.client, self.clock = settings, cache, client, clock

    async def fetch(self, profile: FarmerProfile) -> ToolResult:
        now = self.clock()
        key = f"weather:{profile.lat:.5f}:{profile.lon:.5f}"
        fresh = self.cache.get(key, self.settings.weather_ttl_seconds, now)
        if fresh:
            return fresh
        params = {
            "latitude": profile.lat, "longitude": profile.lon, "timezone": "UTC",
            "hourly": "precipitation,precipitation_probability,temperature_2m",
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "forecast_days": 5, "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }
        error_name = "Forecast unavailable"
        own_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            for attempt in range(self.settings.tool_retries + 1):
                try:
                    response = await client.get(self.settings.weather_url, params=params,
                                                timeout=self.settings.weather_timeout_seconds)
                    response.raise_for_status()
                    result = self.parse(response.json(), now)
                    self.cache.put(key, result)
                    return result
                except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                    error_name = f"Forecast unavailable ({type(exc).__name__})"
        finally:
            if own_client:
                await client.aclose()
        cached = self.cache.get(key, now=now)
        if cached:
            cached.value["warnings"] = [error_name, "Last successful forecast; check its age."]
            cached.value["stale"] = (now - cached.fetched_at).total_seconds() > self.settings.weather_max_age_hours * 3600
            return cached
        return ToolResult(tool="weather", source="Open-Meteo", fetched_at=now, error=error_name)

    @staticmethod
    def parse(payload: dict, now: datetime) -> ToolResult:
        hourly = payload["hourly"]
        times = [datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
                 for value in hourly["time"]]
        rain = hourly["precipitation"]
        temperatures = hourly["temperature_2m"]
        if len(times) != len(rain) or len(times) != len(temperatures):
            raise ValueError("Mismatched hourly arrays")
        # Start at the next full hour. Previous-hour totals are not future rainfall.
        start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        values: dict = {"forecast_start": start.isoformat(),
                        "forecast_end": (start + timedelta(hours=72)).isoformat(),
                        "simulated": False, "stale": False,
                        "precipitation_kind": "rain + showers + snow", "warnings": []}
        for hours in (24, 48, 72):
            indices = [i for i, stamp in enumerate(times) if start <= stamp < start + timedelta(hours=hours)]
            if len(indices) != hours:
                raise ValueError("Incomplete forecast window")
            numbers = [finite_number(rain[i]) for i in indices]
            if any(number < 0 for number in numbers):
                raise ValueError("Negative precipitation")
            values[f"rain_next_{hours}h_mm"] = round(sum(numbers), 2)
        indices = [i for i, stamp in enumerate(times) if start <= stamp < start + timedelta(hours=48)]
        values["temperature_max_c"] = max(finite_number(temperatures[i]) for i in indices)
        values["temperature_min_c"] = min(finite_number(temperatures[i]) for i in indices)
        probabilities = hourly.get("precipitation_probability", [])
        if len(probabilities) == len(times):
            known = [finite_number(probabilities[i]) for i in indices if probabilities[i] is not None]
            if known and all(0 <= probability <= 100 for probability in known):
                values["rain_probability_pct"] = max(known)
        daily = payload["daily"]
        values["daily"] = [
            {"date": day, "rain_mm": finite_number(daily["precipitation_sum"][i]),
             "temp_max_c": finite_number(daily["temperature_2m_max"][i]),
             "temp_min_c": finite_number(daily["temperature_2m_min"][i])}
            for i, day in enumerate(daily["time"])
        ]
        return ToolResult(tool="weather", value=values, source="Open-Meteo", fetched_at=now, confidence="medium")

    def demo(self, scenario: str) -> ToolResult:
        now = self.clock()
        if scenario == "api_failure":
            return ToolResult(tool="weather", source="DEMO SCENARIO - weather outage",
                              fetched_at=now, error="Simulated API failure; no weather available")
        try:
            fixtures = json.loads((self.settings.data_dir / "demo_weather.json").read_text(encoding="utf-8"))
            scenario_key = scenario if scenario in fixtures["scenarios"] else "rain"
            value = dict(fixtures["scenarios"][scenario_key])
            value["daily"] = [dict(row, date=(now.date() + timedelta(days=i)).isoformat())
                              for i, row in enumerate(value["daily"])]
            value.update({"simulated": True, "scenario": scenario_key, "stale": False,
                          "forecast_start": now.isoformat(),
                          "forecast_end": (now + timedelta(hours=72)).isoformat(),
                          "warnings": [fixtures["notice"]]})
            return ToolResult(tool="weather", value=value,
                              source="DEMO SCENARIO - simulated weather, not a forecast",
                              fetched_at=now, confidence="medium", is_cached=True)
        except (OSError, ValueError, KeyError, TypeError):
            return ToolResult(tool="weather", source="DEMO SCENARIO", fetched_at=now,
                              error="Demo fixture unavailable")
