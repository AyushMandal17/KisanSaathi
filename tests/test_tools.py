from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import Settings
from app.schemas import CropPlot, FarmerProfile, ToolResult
from app.tools.cache import ToolCache
from app.tools.crop_stage import CropStageTool
from app.tools.mandi import MandiTool
from app.tools.protocol import RealTools
from app.tools.weather import WeatherTool

NOW = datetime(2026, 10, 31, 6, 30, tzinfo=timezone.utc)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, cache_path=tmp_path / "cache.sqlite3", tool_retries=1)


@pytest.fixture
def profile():
    return FarmerProfile(farmer_id="TEST", name="DEMO Test", village="Test village",
                         district="Dhar", state="Madhya Pradesh", lat=22.6, lon=75.7,
                         crops=[CropPlot(crop="soybean", sowing_date="2026-07-05")])


def forecast():
    start = NOW.replace(hour=0, minute=0)
    return {
        "hourly": {
            "time": [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(120)],
            "precipitation": [100] * 7 + [1] * 113,
            "temperature_2m": [30] * 120,
            "precipitation_probability": [70] * 120,
        },
        "daily": {"time": [(start + timedelta(days=i)).date().isoformat() for i in range(5)],
                  "precipitation_sum": [24] * 5, "temperature_2m_max": [30] * 5,
                  "temperature_2m_min": [20] * 5},
    }


def test_weather_uses_future_rolling_hours():
    result = WeatherTool.parse(forecast(), NOW)
    assert result.value["rain_next_24h_mm"] == 24
    assert result.value["rain_next_48h_mm"] == 48
    assert result.value["rain_next_72h_mm"] == 72
    assert result.value["forecast_start"] == "2026-10-31T07:00:00+00:00"
    assert result.value["rain_probability_pct"] == 70


def test_missing_rain_is_not_filled_with_zero():
    payload = forecast()
    payload["hourly"]["precipitation"][8] = None
    with pytest.raises(ValueError):
        WeatherTool.parse(payload, NOW)


def test_missing_probability_is_omitted():
    payload = forecast()
    payload["hourly"].pop("precipitation_probability")
    assert "rain_probability_pct" not in WeatherTool.parse(payload, NOW).value


def test_cache_keeps_source_timestamp_and_survives_restart(tmp_path):
    path = tmp_path / "cache.sqlite3"
    result = ToolResult(tool="weather", source="Test fixture", fetched_at=NOW,
                        confidence="medium", value={"rain_next_48h_mm": 2})
    ToolCache(path).put("weather:test", result)
    cached = ToolCache(path).get("weather:test", now=NOW + timedelta(hours=1))
    assert cached.is_cached and cached.fetched_at == NOW
    assert ToolCache(path).get("weather:test", max_age_seconds=20, now=NOW + timedelta(hours=1)) is None
    cached.value["rain_next_48h_mm"] = 900
    assert ToolCache(path).get("weather:test", now=NOW).value["rain_next_48h_mm"] == 2


def test_corrupt_cache_is_ignored_without_deleting_it(tmp_path):
    path = tmp_path / "broken.sqlite3"
    path.write_text("not a database", encoding="utf-8")
    assert ToolCache(path).get("weather:test", now=NOW) is None
    assert path.read_text(encoding="utf-8") == "not a database"


@pytest.mark.asyncio
async def test_weather_retry_and_expired_cache_fallback(settings, profile):
    calls = []
    def failure(request):
        calls.append(request)
        raise httpx.ConnectError("Test offline", request=request)
    cache = ToolCache(settings.cache_path)
    cached = WeatherTool.parse(forecast(), NOW).model_copy(update={"fetched_at": NOW - timedelta(hours=8)})
    cache.put("weather:22.60000:75.70000", cached)
    async with httpx.AsyncClient(transport=httpx.MockTransport(failure)) as client:
        result = await WeatherTool(settings, cache, client, lambda: NOW).fetch(profile)
    assert len(calls) == 2
    assert result.is_cached and result.fetched_at == cached.fetched_at
    assert result.value["stale"] is True
    assert "ConnectError" in result.value["warnings"][0]


@pytest.mark.asyncio
async def test_weather_failure_without_cache_is_unknown(settings, profile):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        result = await WeatherTool(settings, ToolCache(settings.cache_path), client, lambda: NOW).fetch(profile)
    assert result.error and result.confidence == "unknown" and result.value == {}


@pytest.mark.asyncio
async def test_weather_live_adapter_uses_profile_coordinates(settings, profile):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=forecast())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WeatherTool(settings, ToolCache(settings.cache_path), client, lambda: NOW).fetch(profile)
    assert result.error is None and not result.is_cached
    assert requests[0].url.params["latitude"] == str(profile.lat)
    assert requests[0].url.params["longitude"] == str(profile.lon)


@pytest.mark.asyncio
async def test_crop_stage_estimated_and_out_of_range_controlled(settings, profile):
    tool = CropStageTool(settings, lambda: NOW)
    result = await tool.fetch(profile, "soybean")
    assert result.value["stage"] == "maturity" and result.value["estimated"]
    assert result.value["calendar_status"] == "demo"
    profile.crops[0].sowing_date = (NOW + timedelta(days=2)).date()
    result = await tool.fetch(profile, "soybean")
    assert result.error and result.confidence == "unknown"
    profile.crops[0].sowing_date = (NOW - timedelta(days=500)).date()
    assert (await tool.fetch(profile, "soybean")).error


@pytest.mark.asyncio
async def test_sample_prices_never_look_live(settings, profile):
    tool = MandiTool(settings, ToolCache(settings.cache_path), clock=lambda: NOW)
    result = await tool.fetch(profile, "soybean")
    assert result.confidence == "low" and result.is_cached and "SAMPLE" in result.source
    assert result.value["sample"] and result.value["prices"]
    assert result.fetched_at == datetime(2026, 10, 31, 6, tzinfo=timezone.utc)
    assert (await tool.fetch(profile, "unknown_crop")).error


@pytest.mark.asyncio
async def test_live_mandi_filters_prices_and_preserves_arrival_date(settings, profile):
    settings.data_gov_api_key, settings.data_gov_resource_id = "fake-test-key", "test-resource"
    calls = []
    def handler(request):
        calls.append(request)
        district = request.url.params["filters[district]"]
        rows = [{"state": "Madhya Pradesh", "district": district, "market": district,
                 "commodity": "Soyabean", "variety": "Yellow", "grade": "FAQ",
                 "arrival_date": "30/10/2026", "min_price": "4000", "max_price": "4500", "modal_price": "4200"}]
        return httpx.Response(200, json={"records": rows})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MandiTool(settings, ToolCache(settings.cache_path), client, lambda: NOW).fetch(profile, "soybean")
    assert len(calls) == 3 and not result.is_cached and result.confidence == "medium"
    assert result.value["prices"][0]["arrival_date"] == "2026-10-30"
    assert result.value["comparable_price_gap_pct"] == 0
    assert result.value["sample"] is False
    assert all(call.url.params["filters[commodity]"] == "Soyabean" for call in calls)


def test_stale_mandi_uses_arrival_date_even_when_fetch_is_recent(settings, profile):
    tool = MandiTool(settings, ToolCache(settings.cache_path), clock=lambda: NOW)
    result = tool.sample(profile, "soybean", scenario="stale_mandi")
    assert result.value["stale"]
    assert result.fetched_at < NOW - timedelta(days=2)
    assert tool.sample(profile, "soybean", scenario="no_mandi").error


def test_missing_grade_cannot_support_market_comparison(settings, profile):
    tool = MandiTool(settings, ToolCache(settings.cache_path), clock=lambda: NOW)
    rows = tool.sample(profile, "soybean").value["prices"]
    for row in rows:
        row["grade"] = ""
    assert "comparable_price_gap_pct" not in tool.payload(rows, profile, sample=False)


@pytest.mark.asyncio
async def test_demo_scenarios_are_explicit_and_network_independent(settings, profile):
    tools = RealTools(settings)
    result = await tools.weather(profile)
    assert "DEMO" in result.source and result.value["simulated"]
    tools.set_scenario("dry")
    assert (await tools.weather(profile)).value["rain_next_48h_mm"] == 0
    tools.set_scenario("heatwave")
    assert (await tools.weather(profile)).value["temperature_max_c"] == 43
    tools.set_scenario("api_failure")
    assert (await tools.weather(profile)).error


@pytest.mark.live
@pytest.mark.asyncio
async def test_open_meteo_live(settings, profile):
    result = await WeatherTool(settings, ToolCache(settings.cache_path)).fetch(profile)
    assert result.error is None, result.error
    assert result.source == "Open-Meteo" and not result.is_cached
    assert result.value["rain_next_72h_mm"] >= 0
