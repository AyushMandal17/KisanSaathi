"""LLM explanations are optional; code owns decisions, provenance and safe fallback."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.agent.guardrails import AdvisoryDraft, data_gaps, validate_draft
from app.agent.language import safe_body, source_line, uncertainty
from app.agent.prompts import ADVISOR_SYSTEM
from app.llm.client import LLM
from app.schemas import AdvisoryResponse, Intent, RiskResult, SourceRef, ToolResult
from app.tools.quality import evidence_gaps

log = logging.getLogger(__name__)


class Advisor:
    def __init__(self, settings: Any, llm: LLM):
        self.settings = settings
        self.llm = llm

    async def generate(self, intent: Intent, risk: RiskResult | None,
                       results: dict[str, ToolResult], language: str,
                       question: str = "") -> tuple[AdvisoryResponse, dict[str, Any]]:
        render_results = dict(results)
        now = datetime.now(timezone.utc)
        for name in ("weather", "crop_stage"):
            result = results.get(name)
            if result is None:
                continue
            invalid = bool(evidence_gaps(result, self.settings, now))
            if name == "crop_stage":
                invalid = invalid or not result.value.get("stage") or not isinstance(
                    result.value.get("days_since_sowing"), int)
                if isinstance(result.value.get("days_since_sowing"), int):
                    invalid = invalid or result.value["days_since_sowing"] < 0
            if invalid:
                render_results[name] = result.model_copy(update={"error": "Evidence is not current and reliable",
                                                                 "confidence": "unknown"})
        body, recommendation = safe_body(intent, risk, render_results, language)
        seed = AdvisoryDraft(answer_text=body, recommendation=recommendation,
                             risk_level=risk.level if risk else "UNKNOWN")
        chosen = seed
        issues: list[str] = []
        accepted = False
        payload = {"question": question, "language": language, "seed": seed.model_dump(),
                   "intent": intent.model_dump(),
                   "risk": risk.model_dump() if risk else None,
                   "evidence": {k: v.value for k, v in results.items() if not v.error}}
        for attempt in range(2):
            try:
                candidate = await self.llm.complete([
                    {"role": "system", "content": ADVISOR_SYSTEM +
                     (" Previous attempt failed: " + ", ".join(issues) if issues else "")},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
                    AdvisoryDraft)
                if not isinstance(candidate, AdvisoryDraft):
                    issues = ["invalid_draft_type"]
                    continue
                issues = validate_draft(candidate, seed, results, language)
                if not issues:
                    chosen, accepted = candidate, True
                    break
                log.warning("Advisory rejected checks=%s attempt=%s", ",".join(issues), attempt + 1)
            except Exception as exc:
                # Never include exception text: provider errors can contain request data.
                log.warning("Advisory template fallback error_type=%s", type(exc).__name__)
                issues = ["llm_unavailable"]
                break
        gaps = data_gaps(results, self.settings)
        note = uncertainty(language, intent.intent)
        if any("stale" in gap for gap in gaps):
            note = (("Some records are stale. " if language == "en" else "कुछ रिकॉर्ड पुराने हैं। ") + note)
        if risk and risk.level == "UNKNOWN":
            gaps.extend(reason for reason in risk.reasons if reason not in gaps)
        sources = [SourceRef(name=r.source, fetched_at=r.fetched_at, is_cached=r.is_cached)
                   for r in results.values() if not r.error]
        citation = source_line(results, language)
        answer = chosen.answer_text + ("\n" + citation if citation else "")
        response = AdvisoryResponse(
            answer_text=answer, language=language, recommendation=seed.recommendation,
            risk_level=seed.risk_level, sources=sources, uncertainty_note=note,
            data_gaps=list(dict.fromkeys(gaps)),
            refer_to_expert=bool(risk and (risk.level == "UNKNOWN" or "DEMO" in risk.rule_source)))
        return response, {"llm_provider": self.llm.last_provider,
                          "safe_template_used": not accepted, "guardrail_failures": issues}
