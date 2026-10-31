"""Explicit synthetic test doubles; never used by the live application."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from app.schemas import FarmerProfile, ToolResult

ROOT = Path(__file__).resolve().parents[1]
EVAL = yaml.safe_load((ROOT / "tests/eval_questions.yaml").read_text(encoding="utf-8"))


def demo_profile(kind: str = "single") -> FarmerProfile:
    data = json.loads((ROOT / "data/seed_farmers.json").read_text(encoding="utf-8"))
    return FarmerProfile.model_validate(data["farmers"][{"single": 0, "multi": 1, "empty": 2}[kind]])


class FakeTools:
    def __init__(self, scenario: str = "rain", crash: str | None = None):
        self.scenario, self.crash = scenario, crash
        self.fixture = EVAL["fixtures"][scenario]
        self.calls: list[str] = []
        self.locations: list[tuple[float, float]] = []
        self.now = datetime.now(timezone.utc)

    def begin(self, name: str, profile: FarmerProfile):
        self.calls.append(name)
        self.locations.append((profile.lat, profile.lon))
        if self.crash == name:
            raise RuntimeError("Synthetic tool exception")

    async def weather(self, profile: FarmerProfile) -> ToolResult:
        self.begin("weather", profile)
        if self.scenario == "api_failure":
            return ToolResult(tool="weather", source="TEST FIXTURE weather unavailable",
                              fetched_at=self.now, error="Synthetic API timeout")
        stamp = self.now
        if self.scenario == "stale_weather":
            stamp -= timedelta(days=2)
        if self.scenario == "future_weather":
            stamp += timedelta(days=1)
        return ToolResult(tool="weather", source="DEMO TEST FIXTURE simulated weather",
                          fetched_at=stamp, confidence="medium", is_cached=self.scenario == "stale_weather",
                          value={"rain_next_48h_mm": self.fixture["rain_mm"],
                                 "temperature_max_c": self.fixture["temperature_c"],
                                 "temperature_min_c": 20, "simulated": True})

    async def mandi(self, profile: FarmerProfile, crop: str) -> ToolResult:
        self.begin("mandi", profile)
        if self.scenario in {"no_mandi", "api_failure"}:
            return ToolResult(tool="mandi", source="TEST FIXTURE mandi unavailable",
                              fetched_at=self.now, error="Synthetic no matching data")
        arrival = self.now.date() - timedelta(days=5 if self.scenario == "stale_mandi" else 0)
        return ToolResult(tool="mandi", source="TEST FIXTURE mandi quotes",
                          fetched_at=self.now, confidence="medium", value={
                              "prices": [{"market": "Test Market A", "district": profile.district,
                                          "commodity": crop, "variety": "Test", "grade": "FAQ",
                                          "modal_price": 4200, "min_price": 4000, "max_price": 4300,
                                          "arrival_date": arrival.isoformat(), "unit": "INR/quintal"},
                                         {"market": "Test Market B", "district": profile.district,
                                          "commodity": crop, "variety": "Test", "grade": "FAQ",
                                          "modal_price": 4300, "min_price": 4100, "max_price": 4400,
                                          "arrival_date": arrival.isoformat(), "unit": "INR/quintal"}],
                              "comparable_price_gap_pct": self.fixture["price_gap_pct"],
                              "sample": False, "stale": self.scenario == "stale_mandi"})

    async def crop_stage(self, profile: FarmerProfile, crop: str) -> ToolResult:
        self.begin("crop_stage", profile)
        if self.scenario == "invalid_stage":
            return ToolResult(tool="crop_stage", source="TEST FIXTURE calendar",
                              fetched_at=self.now, error="Synthetic missing sowing context")
        immature = self.scenario == "immature"
        return ToolResult(tool="crop_stage", source="TEST FIXTURE estimated calendar",
                          fetched_at=self.now, confidence="medium", value={
                              "crop": crop, "stage": "vegetative" if immature else "maturity",
                              "stage_hi": "पत्तियों की बढ़वार" if immature else "पकने की अनुमानित अवस्था",
                              "days_since_sowing": 30 if immature else 110,
                              "estimated": True, "calendar_status": "demo"})
