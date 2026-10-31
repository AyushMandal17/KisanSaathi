import json

import httpx
import pytest

from app.config import PROJECT_DIR, Settings
from app.main import create_app
from app.schemas import AdvisoryResponse, FarmerProfile


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_url="sqlite:///:memory:", use_mock_llm=True,
                    data_mode="demo", cache_path=tmp_path / "cache.sqlite3", rate_limit_requests=100)


@pytest.fixture
async def client(settings):
    application = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application, raise_app_exceptions=False),
                                base_url="http://test") as browser:
        profiles = json.loads((PROJECT_DIR / "data/seed_farmers.json").read_text(encoding="utf-8"))["farmers"]
        for profile in profiles:
            assert (await browser.post("/farmers", json=profile)).status_code == 201
        yield browser


@pytest.mark.parametrize("scenario,expected", [("rain", "HIGH"), ("dry", "LOW"), ("api_failure", "UNKNOWN")])
async def test_full_advice_pipeline(client, scenario, expected):
    response = await client.post("/advise", json={"farmer_id": "F001", "question": "Soybean mein spray karun kya?",
                                                 "demo_scenario": scenario})
    assert response.status_code == 200, response.text
    payload = response.json()
    advisory = AdvisoryResponse.model_validate({k: v for k, v in payload.items() if k != "debug"})
    assert advisory.risk_level == expected
    assert advisory.language == "hi"
    assert advisory.recommendation != "do"
    assert payload["debug"]["intent"]["crop"] == "soybean"
    assert set(payload["debug"]["tool_results"]) == {"weather"}


async def test_refusal_and_clarification(client):
    dose = (await client.post("/advise", json={"farmer_id": "F001", "question": "What pesticide dose should I use?"})).json()
    assert dose["refer_to_expert"]
    assert dose["sources"] == []
    assert dose["debug"]["tool_results"] == {}
    missing = (await client.post("/advise", json={"farmer_id": "F002", "question": "Should I spray?"})).json()
    assert missing["data_gaps"] == ["crop"]
    followup = (await client.post("/advise", json={"farmer_id": "F002", "question": "Should I spray? Crop: soybean"})).json()
    assert followup["debug"]["intent"]["missing_fields"] == []


async def test_dashboard_alerts_and_fpo(client):
    dashboard = await client.get("/dashboard/F001", params={"demo_scenario": "rain"})
    assert dashboard.status_code == 200, dashboard.text
    assert len(dashboard.json()["plots"][0]["risk_results"]) == 5
    assert dashboard.json()["plots"][0]["tool_results"]["mandi"]["confidence"] == "low"
    alerts = await client.post("/alerts/generate", json={"farmer_id": "F001", "demo_scenario": "rain"})
    assert alerts.status_code == 200, alerts.text
    assert alerts.json()["alerts"]
    assert all(a["risk_level"] in {"HIGH", "MEDIUM"} for a in alerts.json()["alerts"])
    failed = await client.post("/alerts/generate", json={"farmer_id": "F001", "demo_scenario": "api_failure"})
    assert failed.json()["alerts"] == []
    rows = (await client.get("/fpo")).json()["rows"]
    assert len(rows) == 4
    empty = next(row for row in rows if row["farmer_id"] == "F003")
    assert empty["reliable_sources"] == 0
    assert set(empty["risks"].values()) == {"UNKNOWN"}
    assert "sowing date" in empty["data_gaps"][0]


@pytest.mark.parametrize("body,status", [
    ({"farmer_id": "F001", "question": " "}, 422),
    ({"farmer_id": "F001", "question": "a" * 501}, 422),
    ({"farmer_id": "absent", "question": "weather"}, 404),
    ({"farmer_id": "F001", "question": "weather", "lat": 1}, 422),
    ({"farmer_id": "F001", "question": "weather", "demo_scenario": "invented"}, 422),
])
async def test_input_errors_are_controlled(client, body, status):
    assert (await client.post("/advise", json=body)).status_code == status


async def test_rate_limit_is_per_farmer(settings):
    settings.rate_limit_requests = 1
    app = create_app(settings)
    profile = FarmerProfile.model_validate(json.loads((PROJECT_DIR / "data/seed_farmers.json").read_text(encoding="utf-8"))["farmers"][0])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/farmers", json=profile.model_dump(mode="json"))
        payload = {"farmer_id": profile.farmer_id, "question": "What is the weather?"}
        assert (await client.post("/advise", json=payload)).status_code == 200
        limited = await client.post("/advise", json=payload)
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) > 0
        assert (await client.get("/health")).status_code == 200


async def test_live_mode_rejects_demo_override(settings):
    settings.data_mode = "live"
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.get("/fpo", params={"demo_scenario": "rain"})
        assert result.status_code == 422
