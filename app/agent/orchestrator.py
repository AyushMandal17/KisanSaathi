"""Deterministic, dependency-injected pipeline and proactive checks."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from app.agent.advisor import Advisor
from app.agent.intent import DOSAGE, IntentExtractor
from app.agent.language import message, reply_language
from app.llm.client import build_llm
from app.risk.engine import RiskEngine
from app.schemas import AdvisoryResponse, FarmerProfile, Intent, RiskResult, ToolResult
from app.tools.protocol import RealTools, Tools

log = logging.getLogger(__name__)
NEEDED = {
    "spray": ("weather",), "irrigation": ("weather",),
    "harvest": ("weather", "crop_stage"), "sowing": ("weather",),
    "sell": ("mandi",), "price": ("mandi",),
    "weather": ("weather",), "crop_stage": ("crop_stage",),
}
DECISIONS = {"spray", "irrigation", "harvest", "sowing", "sell"}


class Orchestrator:
    def __init__(self, settings: Any, tools: Tools | None = None,
                 llm: Any = None, risk_engine: Any = None):
        self.settings = settings
        self.tools = tools if tools is not None else RealTools(settings)
        self.llm = llm if llm is not None else build_llm(settings)
        self.risk = risk_engine if risk_engine is not None else RiskEngine(settings)
        self.extractor = IntentExtractor(settings, self.llm)
        self.advisor = Advisor(settings, self.llm)

    async def collect(self, profile: FarmerProfile, crop: str | None,
                      names: tuple[str, ...]) -> tuple[dict[str, ToolResult], dict[str, float]]:
        async def run(name: str) -> tuple[str, ToolResult, float]:
            start = perf_counter()
            try:
                method = getattr(self.tools, name)
                operation = method(profile) if name == "weather" else method(profile, crop)
                result = await operation
                if not isinstance(result, ToolResult):
                    raise TypeError("Invalid tool result")
            except Exception as exc:
                log.warning("Tool failed name=%s error_type=%s", name, type(exc).__name__)
                result = ToolResult(tool=name, source=f"{name} unavailable",
                                    fetched_at=datetime.now(timezone.utc),
                                    error="Source could not be read; please retry")
            return name, result, round((perf_counter() - start) * 1000, 2)
        completed = await asyncio.gather(*(run(name) for name in names))
        return ({name: result for name, result, _ in completed},
                {name: duration for name, _, duration in completed})

    def evaluate(self, kind: str, crop: str | None,
                 results: dict[str, ToolResult]) -> RiskResult:
        try:
            return self.risk.evaluate(kind, crop, results)
        except Exception as exc:
            log.warning("Risk evaluation failed error_type=%s", type(exc).__name__)
            return RiskResult(risk_type=kind, level="UNKNOWN",
                              reasons=["Risk checks could not evaluate the available evidence"],
                              rule_source="Risk engine unavailable")

    async def advise(self, profile: FarmerProfile, question: str) -> dict[str, Any]:
        start = perf_counter()
        intent = await self.extractor.extract(profile, question)
        language = reply_language(intent)
        debug: dict[str, Any] = {"intent": intent.model_dump(mode="json"),
                                 "tool_results": {}, "risk_results": [], "timings": {}}
        if intent.intent == "other" or intent.missing_fields:
            kind = "clarify" if intent.missing_fields else ("expert" if DOSAGE.search(question) else "other")
            response = AdvisoryResponse(answer_text=message(kind, language), language=language,
                                        recommendation="consult_expert" if kind == "expert" else "unknown",
                                        data_gaps=intent.missing_fields,
                                        refer_to_expert=kind == "expert")
            debug["timings"]["total_ms"] = round((perf_counter() - start) * 1000, 2)
            return {"response": response, "debug": debug}
        results, times = await self.collect(profile, intent.crop, NEEDED[intent.intent])
        risk = self.evaluate(intent.intent, intent.crop, results) if intent.intent in DECISIONS else None
        response, checks = await self.advisor.generate(intent, risk, results, language, question)
        debug.update({"tool_results": {k: v.model_dump(mode="json") for k, v in results.items()},
                      "risk_results": [risk.model_dump(mode="json")] if risk else [],
                      "timings": {**times, "total_ms": round((perf_counter() - start) * 1000, 2)},
                      **checks})
        return {"response": response, "debug": debug}

    async def alerts(self, profile: FarmerProfile) -> list[dict[str, Any]]:
        alerts = []
        for plot in profile.crops:
            results, times = await self.collect(profile, plot.crop, ("weather", "crop_stage"))
            for kind in ("spray", "irrigation", "harvest"):
                relevant = {name: results[name] for name in NEEDED[kind]}
                risk = self.evaluate(kind, plot.crop, relevant)
                if risk.level not in {"MEDIUM", "HIGH"}:
                    continue
                intent = Intent(intent=kind, crop=plot.crop,
                                language="en" if profile.language == "en" else "hi", confidence=1)
                response, checks = await self.advisor.generate(intent, risk, relevant,
                                                               reply_language(intent))
                alerts.append({"response": response, "debug": {
                    "intent": intent.model_dump(mode="json"),
                    "tool_results": {k: v.model_dump(mode="json") for k, v in relevant.items()},
                    "risk_results": [risk.model_dump(mode="json")],
                    "timings": times, **checks}})
        return alerts
