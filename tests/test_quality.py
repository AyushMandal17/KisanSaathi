from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.schemas import ToolResult
from app.tools.quality import evidence_gaps

NOW = datetime(2026, 10, 31, 6, tzinfo=timezone.utc)


def weather(**updates):
    fields = dict(tool="weather", source="Open-Meteo", fetched_at=NOW,
                  confidence="medium", value={"rain_next_48h_mm": 2})
    fields.update(updates)
    return ToolResult(**fields)


@pytest.mark.parametrize("updates,expected", [
    ({"confidence": "low"}, "low or unknown confidence"),
    ({"confidence": "unknown", "error": "offline"}, "offline"),
    ({"fetched_at": NOW.replace(tzinfo=None)}, "missing time zone"),
    ({"fetched_at": NOW + timedelta(minutes=5)}, "future fetch time"),
    ({"fetched_at": NOW - timedelta(hours=7)}, "stale fetch time"),
    ({"value": {"stale": True}}, "stale data"),
    ({"value": {"sample": True}}, "sample records"),
])
def test_shared_quality_flags(updates, expected):
    issues = evidence_gaps(weather(**updates), Settings(_env_file=None), NOW)
    assert any(expected in issue for issue in issues)
    assert all(issue.startswith("weather:") for issue in issues)


def test_fresh_cache_and_estimated_stage_are_acceptable_context():
    settings = Settings(_env_file=None)
    assert not evidence_gaps(weather(is_cached=True), settings, NOW)
    stage = ToolResult(tool="crop_stage", source="DEMO estimated calendar", fetched_at=NOW,
                       confidence="medium", value={"stage": "maturity", "estimated": True})
    assert not evidence_gaps(stage, settings, NOW)


def test_synthetic_weather_requires_honest_labels_and_demo_mode():
    settings = Settings(_env_file=None, data_mode="demo")
    result = weather(source="DEMO SCENARIO - simulated weather", value={"simulated": True}, confidence="high")
    assert not evidence_gaps(result, settings, NOW)
    assert evidence_gaps(result, settings.model_copy(update={"data_mode": "live"}), NOW)
    assert evidence_gaps(result.model_copy(update={"source": "Open-Meteo"}), settings, NOW)
    assert evidence_gaps(result.model_copy(update={"value": {"rain_next_48h_mm": 2}}), settings, NOW)


@pytest.mark.parametrize("rows,expected", [
    ([], "no price records"),
    ([{}], "missing or invalid arrival date"),
    ([{"arrival_date": "not-a-date"}], "missing or invalid arrival date"),
    ([{"arrival_date": "2026-10-01"}], "stale arrival date"),
    ([{"arrival_date": "2026-11-01"}], "future arrival date"),
])
def test_mandi_arrival_quality_is_independent_of_fetch_age(rows, expected):
    result = ToolResult(tool="mandi", source="data.gov.in", fetched_at=NOW,
                        confidence="medium", value={"prices": rows})
    issues = evidence_gaps(result, Settings(_env_file=None), NOW)
    assert any(expected in issue for issue in issues)


def test_arrival_dates_follow_indian_trading_day():
    now = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)
    result = ToolResult(tool="mandi", source="data.gov.in", fetched_at=now, confidence="medium",
                        value={"prices": [{"arrival_date": "2026-10-31"}]})
    assert not evidence_gaps(result, Settings(_env_file=None), now)
