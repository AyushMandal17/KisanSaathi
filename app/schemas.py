"""Shared data contract for the farmer advisory system.

Every module (tools, risk engine, agent, API, dashboard) exchanges data using
these models. Do not change field names or types without telling the whole team.

Pydantic v2 is required (``pip install "pydantic>=2"``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------
# Shared type aliases
# --------------------------------------------------------------------------
Confidence = Literal["high", "medium", "low", "unknown"]
RiskType = Literal["spray", "harvest", "irrigation", "sowing", "sell"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
IntentName = Literal[
    "spray",
    "irrigation",
    "harvest",
    "sowing",
    "sell",
    "price",
    "weather",
    "crop_stage",
    "other",
]
QuestionLanguage = Literal["hi", "en", "hinglish"]
Recommendation = Literal["do", "dont", "wait", "unknown", "consult_expert"]


class _Base(BaseModel):
    """Common config: reject unknown fields so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# 1. Farmer profile
# --------------------------------------------------------------------------
class CropPlot(_Base):
    """One crop planted by a farmer (a farmer can have several).

    Attributes:
        crop: Crop name in lowercase English, e.g. ``"soybean"``.
        sowing_date: Date the crop was sown. Used to estimate the crop stage.
        area_acres: Plot area in acres, or ``None`` if unknown.
    """

    crop: str = Field(min_length=1)
    sowing_date: date
    area_acres: float | None = Field(default=None, gt=0)


class FarmerProfile(_Base):
    """Saved profile of a farmer. Location is stored here, not asked per query.

    Attributes:
        farmer_id: Unique id, e.g. ``"F001"``.
        name: Farmer's name.
        village / district / state: Location text.
        lat / lon: Coordinates passed to weather and nearest-mandi tools.
        language: Preferred reply language code. Defaults to ``"hi"`` (Hindi).
        crops: Crops currently planted. May be empty for a new farmer.
    """

    farmer_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    village: str
    district: str
    state: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    language: str = "hi"
    crops: list[CropPlot] = Field(default_factory=list)


# --------------------------------------------------------------------------
# 2. Tool result
# --------------------------------------------------------------------------
class ToolResult(_Base):
    """Standard output of every data tool (weather, mandi, soil, crop stage).

    Attributes:
        tool: Tool name, e.g. ``"weather"``.
        value: The data payload. May be empty when ``error`` is set.
        source: Human-readable data source, e.g. ``"Open-Meteo"``.
        fetched_at: When the data was fetched (use timezone-aware datetimes).
        is_cached: True if this came from the cache, not a live call.
        confidence: ``"high" | "medium" | "low" | "unknown"``.
        error: Error message if the tool failed, otherwise ``None``.

    Rule:
        If ``error`` is set, ``confidence`` must be ``"unknown"`` and ``value``
        may be empty. A failed tool must never look like a trusted result.
    """

    tool: str = Field(min_length=1)
    value: dict[str, Any] = Field(default_factory=dict)
    source: str
    fetched_at: datetime
    is_cached: bool = False
    confidence: Confidence = "unknown"
    error: str | None = None

    @model_validator(mode="after")
    def _error_implies_unknown_confidence(self) -> "ToolResult":
        if self.error is not None and self.confidence != "unknown":
            raise ValueError(
                "confidence must be 'unknown' when error is set "
                f"(got {self.confidence!r})"
            )
        return self


# --------------------------------------------------------------------------
# 3. Risk result
# --------------------------------------------------------------------------
class RiskResult(_Base):
    """Output of the rule-based risk engine. The LLM must never override it.

    Attributes:
        risk_type: Which decision was evaluated.
        level: ``LOW | MEDIUM | HIGH | UNKNOWN``. Use ``UNKNOWN`` when the
            evidence is insufficient.
        reasons: Short human-readable reasons for the level.
        evidence: The numbers/facts the rule used, e.g. ``{"rain_48h_mm": 28}``.
        rule_source: Where the rule came from (e.g. KVK/ICAR document name).
    """

    risk_type: RiskType
    level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    rule_source: str


# --------------------------------------------------------------------------
# 4. Intent
# --------------------------------------------------------------------------
class Intent(_Base):
    """Structured meaning of a farmer's question.

    Attributes:
        intent: What the farmer wants to know. ``"other"`` means out of scope.
        crop: Crop the question is about, or ``None`` if not determined.
        language: Language the farmer wrote in.
        missing_fields: Fields needed to answer but not known, e.g. ``["crop"]``.
        confidence: Extraction confidence between 0 and 1.
    """

    intent: IntentName
    crop: str | None = None
    language: QuestionLanguage
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# --------------------------------------------------------------------------
# 5. Source reference
# --------------------------------------------------------------------------
class SourceRef(_Base):
    """A data source cited in an answer. Filled in code, never by the LLM.

    Attributes:
        name: Source name, e.g. ``"Open-Meteo"``.
        fetched_at: When that data was fetched.
        is_cached: Whether the data came from the cache.
    """

    name: str = Field(min_length=1)
    fetched_at: datetime
    is_cached: bool = False


# --------------------------------------------------------------------------
# 6. Advisory response
# --------------------------------------------------------------------------
class AdvisoryResponse(_Base):
    """Final answer sent to the farmer (and shown on the dashboard).

    Attributes:
        answer_text: The reply text in the farmer's language.
        language: Language code of ``answer_text``, e.g. ``"hi"``.
        recommendation: ``do | dont | wait | unknown | consult_expert``.
        risk_level: Risk level string taken from the risk engine
            (``"LOW"``, ``"MEDIUM"``, ``"HIGH"``, ``"UNKNOWN"``), or
            ``"UNKNOWN"`` when no risk was evaluated.
        sources: Sources used, with their fetch times.
        uncertainty_note: Plain-language note about forecast/data uncertainty.
        data_gaps: Missing or stale data that limited the answer.
        refer_to_expert: True when the farmer should consult KVK/agri officer.
    """

    answer_text: str = Field(min_length=1)
    language: str
    recommendation: Recommendation
    risk_level: str = "UNKNOWN"
    sources: list[SourceRef] = Field(default_factory=list)
    uncertainty_note: str = ""
    data_gaps: list[str] = Field(default_factory=list)
    refer_to_expert: bool = False
