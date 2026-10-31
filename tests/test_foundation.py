import json

from fastapi.testclient import TestClient

from app.config import PROJECT_DIR, Settings
from app.main import create_app
from app.schemas import FarmerProfile


def test_health_and_farmer_roundtrip():
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    profile = FarmerProfile.model_validate(json.loads(
        (PROJECT_DIR / "data/seed_farmers.json").read_text(encoding="utf-8")
    )["farmers"][0]).model_dump(mode="json")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.post("/farmers", json=profile).status_code == 201
        assert client.post("/farmers", json=profile).status_code == 409
        assert client.get("/farmers").json() == [profile]
        profile["name"] = "Edited DEMO"
        assert client.put("/farmers/F001", json=profile).json()["name"] == "Edited DEMO"
        assert client.get("/farmers/not-found").status_code == 404
        assert client.put("/farmers/wrong", json=profile).status_code == 400


def test_profile_validation():
    with TestClient(create_app(Settings(_env_file=None, database_url="sqlite:///:memory:"))) as client:
        assert client.post("/farmers", json={"farmer_id": "bad"}).status_code == 422
