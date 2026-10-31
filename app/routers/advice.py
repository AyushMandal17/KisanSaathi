"""HTTP envelopes extend, but never edit, the team's shared data contract."""
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.agent.orchestrator import Orchestrator
from app.db import get_session
from app.repository import FarmerRepository
from app.schemas import AdvisoryResponse, FarmerProfile, ToolResult
from app.tools.quality import evidence_gaps

Scenario = Literal["rain", "dry", "heatwave", "api_failure", "stale_mandi", "no_mandi"]
router = APIRouter(tags=["advice"])


class AdviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    farmer_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=500)
    demo_scenario: Scenario | None = None

    @field_validator("question")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value.strip()


class AlertsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    farmer_id: str = Field(min_length=1, max_length=80)
    demo_scenario: Scenario | None = None


class AdviceEnvelope(AdvisoryResponse):
    debug: dict = Field(default_factory=dict)


class FarmerRateLimiter:
    """Process-local sliding window, deliberately scoped to a single-worker demo."""
    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.events = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, farmer_id: str):
        now = time.monotonic()
        with self.lock:
            events = self.events[farmer_id]
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                retry = max(1, int(self.window - now + events[0]) + 1)
                raise HTTPException(429, "Please wait before requesting more advice.",
                                    headers={"Retry-After": str(retry)})
            events.append(now)


def resolve(request: Request, farmer_id: str, session: Session) -> FarmerProfile:
    profile = FarmerRepository(session).get(farmer_id)
    if profile is None:
        raise HTTPException(404, "Farmer not found")
    request.app.state.limiter.check(farmer_id)
    return profile


def service(request: Request, scenario: Scenario | None = None) -> Orchestrator:
    settings = request.app.state.settings
    if scenario:
        if settings.data_mode != "demo":
            raise HTTPException(422, "Demo scenarios are available only in DATA_MODE=demo")
        settings = settings.model_copy(update={"demo_scenario": scenario})
    return Orchestrator(settings, tools=request.app.state.tools, llm=request.app.state.llm)


def envelope(bundle: dict) -> AdviceEnvelope:
    response = bundle["response"]
    if not isinstance(response, AdvisoryResponse):
        response = AdvisoryResponse.model_validate(response)
    return AdviceEnvelope(**response.model_dump(), debug=bundle["debug"])


@router.post("/advise", response_model=AdviceEnvelope)
async def advise(body: AdviceRequest, request: Request, session: Session = Depends(get_session)):
    profile = resolve(request, body.farmer_id, session)
    return envelope(await service(request, body.demo_scenario).advise(profile, body.question))


@router.post("/alerts/generate")
async def alerts(body: AlertsRequest, request: Request, session: Session = Depends(get_session)):
    profile = resolve(request, body.farmer_id, session)
    bundles = await service(request, body.demo_scenario).alerts(profile)
    return {"farmer_id": profile.farmer_id, "generated_at": datetime.now(timezone.utc),
            "alerts": [envelope(bundle) for bundle in bundles]}


def gaps(results: dict[str, ToolResult], settings) -> list[str]:
    return [note for result in results.values() for note in evidence_gaps(result, settings)]


async def snapshot(profile: FarmerProfile, agent: Orchestrator) -> dict:
    weather, _ = await agent.collect(profile, None, ("weather",))

    async def plot_data(plot):
        results, _ = await agent.collect(profile, plot.crop, ("mandi", "crop_stage"))
        results.update(weather)
        risks = [agent.evaluate(kind, plot.crop, results)
                 for kind in ("spray", "irrigation", "harvest", "sowing", "sell")]
        return {"crop": plot.crop, "tool_results": results, "risk_results": risks,
                "data_gaps": gaps(results, agent.settings)}

    plots = await asyncio.gather(*(plot_data(plot) for plot in profile.crops))
    return {"farmer": profile, "as_of": datetime.now(timezone.utc),
            "data_mode": agent.settings.data_mode, "weather": weather["weather"],
            "plots": plots, "data_gaps": [] if plots else ["No crop or sowing date saved"]}


@router.get("/dashboard/{farmer_id}")
async def dashboard(farmer_id: str, request: Request, demo_scenario: Scenario | None = None,
                    session: Session = Depends(get_session)):
    profile = resolve(request, farmer_id, session)
    return await snapshot(profile, service(request, demo_scenario))


@router.get("/fpo")
async def fpo(request: Request, demo_scenario: Scenario | None = None,
              session: Session = Depends(get_session)):
    profiles = FarmerRepository(session).list()
    agent = service(request, demo_scenario)
    for profile in profiles:
        request.app.state.limiter.check(profile.farmer_id)
    snapshots = await asyncio.gather(*(snapshot(profile, agent) for profile in profiles))
    rows = []
    for item in snapshots:
        profile = item["farmer"]
        for plot in item["plots"] or [None]:
            if plot:
                stage = plot["tool_results"]["crop_stage"].value.get("stage", "Unknown")
                risks = {risk.risk_type: risk.level for risk in plot["risk_results"]}
                issues = plot["data_gaps"]
                reliable = sum(not evidence_gaps(tool, agent.settings)
                               for tool in plot["tool_results"].values())
            else:
                stage, risks, issues, reliable = "Unknown", {}, item["data_gaps"], 0
            rows.append({"farmer_id": profile.farmer_id, "farmer": profile.name,
                         "village": profile.village, "crop": plot["crop"] if plot else "Not saved",
                         "stage": stage, "risks": risks, "reliable_sources": reliable,
                         "expected_sources": 3, "data_gaps": issues,
                         "demo_rule": bool(plot and any(r.evidence.get("demo_rule") for r in plot["risk_results"]))})
    return {"as_of": datetime.now(timezone.utc), "rows": rows}
