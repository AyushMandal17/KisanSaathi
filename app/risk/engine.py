"""Deterministic, data-quality-gated rule evaluation. No LLM dependency."""
from __future__ import annotations

import math
import operator
from datetime import datetime
from typing import Callable

import yaml

from app.schemas import RiskResult, RiskType, ToolResult
from app.tools.cache import utcnow
from app.tools.quality import evidence_gaps


class RiskEngine:
    OPERATORS = {"lt": operator.lt, "lte": operator.le, "gt": operator.gt,
                 "gte": operator.ge, "eq": operator.eq, "ne": operator.ne}

    def __init__(self, settings, clock: Callable[[], datetime] = utcnow):
        self.settings, self.clock = settings, clock
        self.config = yaml.safe_load(settings.rules_path.read_text(encoding="utf-8"))

    def evaluate(self, risk_type: RiskType, crop: str | None,
                 results: dict[str, ToolResult]) -> RiskResult:
        required = self.config["requirements"].get(risk_type, [])
        problems, facts = [], {}
        if not crop:
            problems.append("Crop is unknown.")
        for name in {field.split(".")[0] for field in required}:
            result = results.get(name)
            if result is None:
                problems.append(f"{name}: required evidence is missing.")
            else:
                problems.extend(evidence_gaps(result, self.settings, self.clock()))
        for field in required:
            tool, key = field.split(".", 1)
            result = results.get(tool)
            value = result.value.get(key) if result else None
            if value is None or isinstance(value, bool) or (isinstance(value, (int, float)) and not math.isfinite(value)):
                problems.append(f"Required evidence missing: {field}.")
            else:
                facts[field] = value
        if problems or not required:
            return RiskResult(risk_type=risk_type, level="UNKNOWN", reasons=list(dict.fromkeys(problems)) or ["No rule configured."],
                              evidence=facts, rule_source="Data-quality gate; no agronomic conclusion")
        matches = []
        for rule in self.config["rules"]:
            if rule["risk_type"] != risk_type or rule["crop"] not in {"any", crop}:
                continue
            try:
                if all(self.OPERATORS[condition["op"]](facts[condition["field"]], condition["value"])
                       for condition in rule["conditions"]):
                    matches.append(rule)
            except (KeyError, TypeError, ValueError):
                return RiskResult(risk_type=risk_type, level="UNKNOWN", reasons=["Rule or evidence format is invalid."],
                                  evidence=facts, rule_source="Rule validation gate")
        if not matches:
            return RiskResult(risk_type=risk_type, level="UNKNOWN", reasons=["No configured rule matched the evidence."],
                              evidence=facts, rule_source="Rule coverage gate")
        ranks = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        chosen = max(matches, key=lambda rule: ranks[rule["level"]])
        evidence = dict(facts, rule_id=chosen["id"], status=chosen["status"],
                        demo_rule=chosen["status"] == "demo",
                        scope="Weather/calendar/price screening only; not a full agronomic assessment")
        return RiskResult(risk_type=risk_type, level=chosen["level"], reasons=[chosen["reason"]],
                          evidence=evidence, rule_source=chosen["rule_source"])
