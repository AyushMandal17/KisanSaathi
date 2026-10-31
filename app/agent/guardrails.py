"""Conservative post-checks; failures cause regeneration, then a safe template."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import Recommendation, ToolResult
from app.tools.quality import evidence_gaps


class AdvisoryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_text: str = Field(min_length=1, max_length=1200)
    recommendation: Recommendation
    risk_level: str


BANNED = re.compile(
    r"\b(glyphosate|paraquat|chlorpyrifos|imidacloprid|malathion|monocrotophos|"
    r"carbendazim|acephate|thiamethoxam|cypermethrin|mancozeb|"
    r"ml|mg|ppm|millilit\w*|dosage|mixing\s+ratio)\b|"
    r"ग्लाइफोसेट|पैराक्वाट|क्लोरपायरीफॉस|इमिडाक्लोप्रिड|मोनोक्रोटोफॉस|"
    r"(?:मिली|ग्राम).{0,12}(?:लीटर|पानी)|\d+\s*[:/]\s*\d+", re.IGNORECASE)


def numbers(value: Any) -> set[Decimal]:
    found: set[Decimal] = set()
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, dict):
        for key, child in value.items():
            # Horizon numbers are part of the measured field, not agronomic claims.
            found |= numbers(key)
            found |= numbers(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            found |= numbers(child)
    else:
        text = unicodedata.normalize("NFKC", str(value))
        for token in re.findall(r"(?<!\w)[-+]?\d+(?:\.\d+)?|(?<=_)\d+", text):
            try:
                found.add(Decimal(token))
            except ArithmeticError:
                continue
    return found


def first_sentence(text: str) -> str:
    return re.split(r"[।.!?](?:\s|$)", text, maxsplit=1)[0].strip()


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[।!?])\s+|(?<=\.)\s+(?=\D)", text.strip()) if part.strip()]


def validate_draft(candidate: AdvisoryDraft, seed: AdvisoryDraft,
                   results: dict[str, ToolResult], language: str) -> list[str]:
    failures = []
    if candidate.recommendation != seed.recommendation or candidate.risk_level != seed.risk_level:
        failures.append("decision_changed")
    if first_sentence(candidate.answer_text) != first_sentence(seed.answer_text):
        failures.append("decision_sentence_changed")
    if BANNED.search(candidate.answer_text):
        failures.append("banned_content")
    allowed = numbers({name: result.value for name, result in results.items() if not result.error})
    if numbers(candidate.answer_text) - allowed:
        failures.append("unsupported_number")
    if language == "hi" and not re.search(r"[\u0900-\u097f]", candidate.answer_text):
        failures.append("wrong_language")
    if language == "en" and re.search(r"[\u0900-\u097f]", candidate.answer_text):
        failures.append("wrong_language")
    if len(re.findall(r"[।!?]|\.(?=\s|$)", candidate.answer_text)) > 4:
        failures.append("too_many_sentences")
    if re.search(r"https?://|sources?:|स्रोत:", candidate.answer_text, re.IGNORECASE):
        failures.append("invented_source")
    if "DEMO" in seed.answer_text and "DEMO" not in candidate.answer_text:
        failures.append("missing_demo_label")
    if "डेमो" in seed.answer_text and "डेमो" not in candidate.answer_text:
        failures.append("missing_demo_label")
    if seed.risk_level in {"HIGH", "UNKNOWN", "MEDIUM"}:
        affirmative = r"\b(go ahead|proceed now|you should|you can safely|safe to|definitely|guaranteed)\b|अभी करें|ज़रूर करें|जरूर करें|सुरक्षित है|पक्का"
        if re.search(affirmative, candidate.answer_text, re.IGNORECASE):
            failures.append("firm_action_without_support")
    # Words alone can be rearranged into a contradictory instruction. Only whole
    # reviewed sentences may be selected/reordered, with the decision first and
    # uncertainty/demo disclosure retained. Free-form text always falls back.
    approved, proposed = sentences(seed.answer_text), sentences(candidate.answer_text)
    if any(sentence not in approved for sentence in proposed) or len(proposed) != len(set(proposed)):
        failures.append("unapproved_sentence")
    required = approved[:1] + approved[-(2 if len(approved) >= 4 else 1):]
    if any(sentence not in proposed for sentence in required):
        failures.append("missing_policy_sentence")
    indices = [approved.index(sentence) for sentence in proposed if sentence in approved]
    if indices != sorted(indices):
        failures.append("sentence_order_changed")
    return failures


def data_gaps(results: dict[str, ToolResult], settings: Any,
              now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    gaps = []
    for name, result in results.items():
        gaps.extend(evidence_gaps(result, settings, now))
        gaps.extend(f"{name}: {item}" for item in result.value.get("data_gaps", []))
        gaps.extend(f"{name}: {item}" for item in result.value.get("warnings", []))
    return list(dict.fromkeys(gaps))
