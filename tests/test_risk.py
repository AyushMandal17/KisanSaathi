from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.risk.engine import RiskEngine
from app.schemas import RiskResult, ToolResult

NOW = datetime(2026, 10, 31, 6, tzinfo=timezone.utc)


def evidence():
    return {
        "weather": ToolResult(tool="weather", source="TEST FIXTURE", fetched_at=NOW,
                              confidence="medium", value={"rain_next_48h_mm": 0, "temperature_max_c": 30}),
        "crop_stage": ToolResult(tool="crop_stage", source="TEST FIXTURE", fetched_at=NOW,
                                 confidence="medium", value={"stage": "maturity"}),
        "mandi": ToolResult(tool="mandi", source="TEST FIXTURE", fetched_at=NOW, confidence="medium",
                            value={"comparable_price_gap_pct": 0, "sample": False,
                                   "prices": [{"arrival_date": "2026-10-31"}]}),
    }


@pytest.fixture
def engine():
    return RiskEngine(Settings(_env_file=None), clock=lambda: NOW)


@pytest.mark.parametrize("risk_type,field,high,medium,low", [
    ("spray", "weather.rain_next_48h_mm", 25, 8, 0),
    ("irrigation", "weather.rain_next_48h_mm", 25, 8, 0),
    ("harvest", "weather.rain_next_48h_mm", 25, 8, 0),
    ("sowing", "weather.rain_next_48h_mm", 45, 25, 0),
    ("sell", "mandi.comparable_price_gap_pct", 12, 6, 2),
])
def test_every_risk_has_high_medium_low_unknown(engine, risk_type, field, high, medium, low):
    tool, key = field.split(".")
    for number, expected in [(high, "HIGH"), (medium, "MEDIUM"), (low, "LOW")]:
        results = evidence()
        results[tool].value[key] = number
        result = engine.evaluate(risk_type, "soybean", results)
        assert isinstance(result, RiskResult) and result.level == expected
        assert result.evidence["demo_rule"] and result.evidence["status"] == "demo"
        assert "DEMO RULE" in result.rule_source
    assert engine.evaluate(risk_type, "soybean", {}).level == "UNKNOWN"


@pytest.mark.parametrize("risk_type", ["spray", "irrigation", "harvest", "sowing", "sell"])
@pytest.mark.parametrize("failure", ["low", "unknown", "error", "stale", "future", "naive", "missing", "nan"])
def test_unreliable_required_evidence_never_makes_a_decision(engine, risk_type, failure):
    results = evidence()
    name = "mandi" if risk_type == "sell" else "weather"
    result = results[name]
    if failure in {"low", "unknown"}:
        result.confidence = failure
    elif failure == "error":
        results[name] = ToolResult(tool=name, source="TEST FIXTURE", fetched_at=NOW, error="offline")
    elif failure == "stale":
        result.fetched_at = NOW - timedelta(days=7)
    elif failure == "future":
        result.fetched_at = NOW + timedelta(hours=1)
    elif failure == "naive":
        result.fetched_at = NOW.replace(tzinfo=None)
    elif failure == "missing":
        result.value = {}
    elif failure == "nan":
        key = "comparable_price_gap_pct" if name == "mandi" else "rain_next_48h_mm"
        result.value[key] = float("nan")
    assert engine.evaluate(risk_type, "soybean", results).level == "UNKNOWN"


def test_sample_and_stale_arrival_prices_cannot_guide_sales(engine):
    results = evidence()
    results["mandi"].value["sample"] = True
    assert engine.evaluate("sell", "soybean", results).level == "UNKNOWN"
    results = evidence()
    results["mandi"].value["prices"][0]["arrival_date"] = "2026-09-01"
    assert engine.evaluate("sell", "soybean", results).level == "UNKNOWN"


def test_immature_crop_raises_harvest_risk_even_with_dry_weather(engine):
    results = evidence()
    results["crop_stage"].value["stage"] = "flowering"
    assert engine.evaluate("harvest", "soybean", results).level == "HIGH"


def test_heatwave_and_exact_threshold_priority(engine):
    results = evidence()
    results["weather"].value["temperature_max_c"] = 43
    assert engine.evaluate("spray", "soybean", results).level == "HIGH"
    assert engine.evaluate("irrigation", "soybean", results).level == "MEDIUM"
    assert engine.evaluate("sowing", "soybean", results).level == "HIGH"
    results = evidence()
    results["weather"].value["rain_next_48h_mm"] = 20
    assert engine.evaluate("spray", "soybean", results).level == "HIGH"
    results["weather"].value["rain_next_48h_mm"] = 5
    assert engine.evaluate("spray", "soybean", results).level == "MEDIUM"


def test_missing_crop_and_type_mismatch_are_unknown(engine):
    assert engine.evaluate("spray", None, evidence()).level == "UNKNOWN"
    results = evidence()
    results["weather"].value["rain_next_48h_mm"] = "rainy"
    assert engine.evaluate("spray", "soybean", results).level == "UNKNOWN"


def test_unneeded_failed_tool_does_not_block_weather_decision(engine):
    results = evidence()
    results["mandi"] = ToolResult(tool="mandi", source="TEST FIXTURE", fetched_at=NOW, error="offline")
    assert engine.evaluate("spray", "soybean", results).level == "LOW"
