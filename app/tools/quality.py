"""Shared freshness and provenance gates for decisions, answers and dashboard counts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.schemas import ToolResult


def evidence_gaps(result: ToolResult, settings: Any,
                  now: datetime | None = None) -> list[str]:
    """Return tool-prefixed reasons this result cannot support current advice.

    Synthetic weather can exercise demo rules only in demo mode, with its explicit
    simulated flag and DEMO source label. An estimated crop calendar is valid
    context, but never an observation of actual field conditions.
    """
    now = now or datetime.now(timezone.utc)
    issues: list[str] = []
    if result.error:
        issues.append(result.error)
    if result.confidence in {"low", "unknown"}:
        issues.append("low or unknown confidence")
    stamp = result.fetched_at
    if stamp.utcoffset() is None:
        issues.append("missing time zone")
    else:
        age_seconds = (now - stamp).total_seconds()
        max_hours = settings.mandi_max_age_hours if result.tool == "mandi" else settings.weather_max_age_hours
        if age_seconds < -60:
            issues.append("future fetch time")
        elif age_seconds > max_hours * 3600:
            issues.append("stale fetch time")
    if result.value.get("stale"):
        issues.append("stale data")
    if result.value.get("sample") or "SAMPLE" in result.source.upper():
        issues.append("sample records, not current evidence")
    if (result.tool == "weather" and "DEMO" in result.source.upper()
            and not result.value.get("simulated")):
        issues.append("DEMO weather is missing its simulated-data flag")
    if result.value.get("simulated"):
        if "DEMO" not in result.source.upper():
            issues.append("simulated data is missing its DEMO source label")
        if settings.data_mode != "demo":
            issues.append("simulated data cannot support live advice")
    if result.tool == "mandi" and not result.error:
        rows = result.value.get("prices")
        if not isinstance(rows, list) or not rows:
            issues.append("no price records")
        else:
            # Arrival dates describe an Indian trading day, not a UTC timestamp.
            today = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
            for row in rows:
                try:
                    arrival = date.fromisoformat(row["arrival_date"])
                    age_days = (today - arrival).days
                    if age_days < 0:
                        issues.append("future arrival date")
                    elif age_days * 24 > settings.mandi_max_age_hours:
                        issues.append("stale arrival date")
                except (KeyError, TypeError, ValueError):
                    issues.append("missing or invalid arrival date")
    return [f"{result.tool}: {issue}" for issue in dict.fromkeys(issues)]
