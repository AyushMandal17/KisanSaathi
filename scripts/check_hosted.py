"""Run separately from the test suite: verifies the deployed ASGI entrypoint."""
import asyncio
import os

os.environ["DATA_MODE"] = "demo"
os.environ["USE_MOCK_LLM"] = "true"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"
import httpx
from deploy import app

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for path in ("/health", "/meta", "/farmers", "/dashboard/F001", "/dashboard/F003", "/fpo"):
            response = await client.get("/api" + path)
            assert response.status_code == 200, (path, response.status_code)
        farmers = (await client.get("/api/farmers")).json()
        assert len(farmers) == 3
        assert (await client.post("/api/farmers", json=farmers[0])).status_code == 403
        assert (await client.put("/api/farmers/F001", json=farmers[0])).status_code == 403
        for scenario, expected in (("rain", "HIGH"), ("dry", "LOW"), ("api_failure", "UNKNOWN")):
            response = await client.post("/api/advise", json={"farmer_id": "F001", "question": "Soybean mein spray karun kya?", "demo_scenario": scenario})
            assert response.status_code == 200
            answer = response.json()
            assert answer["risk_level"] == expected, answer
            assert answer["answer_text"]
        alerts = await client.post("/api/alerts/generate", json={"farmer_id": "F001", "demo_scenario": "rain"})
        assert alerts.status_code == 200 and alerts.json()["alerts"]
        assert (await client.get("/api/dashboard/unknown")).status_code == 404
        assert (await client.post("/api/advise", json={"farmer_id":"F001", "question":" "})).status_code == 422
    print("Hosted API checks passed: profiles, read-only guard, snapshots, FPO, advice scenarios, alerts, errors.")

if __name__ == "__main__":
    asyncio.run(check())
