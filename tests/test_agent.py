import asyncio
from datetime import timedelta

import pytest

from app.agent.guardrails import AdvisoryDraft
from app.agent.orchestrator import Orchestrator
from app.config import Settings
from app.llm.client import LLMClient, MockLLMClient
from app.schemas import AdvisoryResponse, Intent
from scripts.run_eval import evaluate_case
from tests.fakes import EVAL, FakeTools, demo_profile


@pytest.fixture
def settings():
    return Settings(_env_file=None, data_mode="demo", use_mock_llm=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", EVAL["cases"], ids=lambda case: case["id"])
async def test_evaluation_scenario(case, settings):
    assert await evaluate_case(case, settings) == []


class UnsafeLLM(MockLLMClient):
    def __init__(self, fault):
        self.fault, self.advisory_calls = fault, 0

    async def complete(self, messages, schema=None):
        draft = await super().complete(messages, schema)
        if schema is AdvisoryDraft:
            self.advisory_calls += 1
            if self.fault == "contradiction":
                draft.answer_text += " Proceed with spraying now."
            elif self.fault == "number":
                draft.answer_text = draft.answer_text.replace("28", "999")
            elif self.fault == "chemical":
                draft.answer_text += " Use glyphosate."
            elif self.fault == "unknown_chemical":
                draft.answer_text += " Apply madeupchemical."
            elif self.fault == "risk":
                draft.risk_level, draft.recommendation = "LOW", "do"
        return draft


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["contradiction", "number", "chemical", "unknown_chemical", "risk"])
async def test_unsafe_model_output_regenerates_once_then_safe_template(settings, fault):
    llm = UnsafeLLM(fault)
    result = await Orchestrator(settings, FakeTools(), llm).advise(demo_profile(), "Should I spray soybean?")
    answer = AdvisoryResponse.model_validate(result["response"])
    assert answer.risk_level == "HIGH" and answer.recommendation == "dont"
    assert "Proceed with spraying now" not in answer.answer_text
    assert "999" not in answer.answer_text
    assert "glyphosate" not in answer.answer_text
    assert "madeupchemical" not in answer.answer_text
    assert result["debug"]["safe_template_used"]
    assert llm.advisory_calls == 2


@pytest.mark.asyncio
async def test_question_cannot_override_saved_location(settings):
    tools = FakeTools()
    farmer = demo_profile()
    result = await Orchestrator(settings, tools, MockLLMClient()).advise(
        farmer, "What is the weather in London at latitude 51.5?")
    assert tools.locations == [(farmer.lat, farmer.lon)]
    assert "51.5" not in result["response"].answer_text


@pytest.mark.asyncio
async def test_unexpected_tool_failure_is_isolated(settings):
    result = await Orchestrator(settings, FakeTools(crash="weather"), MockLLMClient()).advise(
        demo_profile(), "Can I harvest soybean?")
    assert result["response"].risk_level == "UNKNOWN"
    assert result["debug"]["tool_results"]["crop_stage"]["error"] is None
    assert result["debug"]["tool_results"]["weather"]["confidence"] == "unknown"


@pytest.mark.asyncio
async def test_missing_live_llm_credentials_uses_honest_safe_template(settings):
    no_keys = settings.model_copy(update={"use_mock_llm": False, "groq_api_key": "", "gemini_api_key": ""})
    result = await Orchestrator(no_keys, FakeTools(), LLMClient(no_keys)).advise(
        demo_profile(), "Should I spray soybean?")
    assert result["response"].risk_level == "HIGH"
    assert result["debug"]["llm_provider"] == "none"
    assert result["debug"]["safe_template_used"]


@pytest.mark.asyncio
async def test_proactive_alerts_cover_all_saved_plots(settings):
    profile = demo_profile("multi")
    alerts = await Orchestrator(settings, FakeTools(), MockLLMClient()).alerts(profile)
    assert {item["debug"]["intent"]["crop"] for item in alerts} == {p.crop for p in profile.crops}
    assert all(item["response"].risk_level in {"MEDIUM", "HIGH"} for item in alerts)
    assert all(item["response"].recommendation != "do" for item in alerts)


@pytest.mark.asyncio
async def test_sample_prices_never_produce_sale_recommendation(settings):
    class SampleTools(FakeTools):
        async def mandi(self, profile, crop):
            result = await super().mandi(profile, crop)
            result.value["sample"] = True
            result.confidence = "low"
            result.source = "SAMPLE mandi records"
            return result
    result = await Orchestrator(settings, SampleTools(), MockLLMClient()).advise(
        demo_profile(), "Should I sell soybean?")
    assert result["response"].risk_level == "UNKNOWN"
    assert result["response"].recommendation == "unknown"
    assert "Sample records" in result["response"].answer_text


@pytest.mark.asyncio
async def test_stale_estimated_stage_is_not_presented_as_current(settings):
    class StaleStage(FakeTools):
        async def crop_stage(self, profile, crop):
            result = await super().crop_stage(profile, crop)
            result.fetched_at -= timedelta(days=3)
            return result
    result = await Orchestrator(settings, StaleStage(), MockLLMClient()).advise(
        demo_profile(), "What is my crop stage?")
    assert "110" not in result["response"].answer_text
    assert result["response"].data_gaps


@pytest.mark.asyncio
async def test_required_tools_are_started_concurrently(settings):
    class CoordinatedTools(FakeTools):
        def __init__(self):
            super().__init__()
            self.weather_started, self.stage_started = asyncio.Event(), asyncio.Event()

        async def weather(self, profile):
            self.weather_started.set()
            await self.stage_started.wait()
            return await super().weather(profile)

        async def crop_stage(self, profile, crop):
            self.stage_started.set()
            await self.weather_started.wait()
            return await super().crop_stage(profile, crop)
    result = await asyncio.wait_for(Orchestrator(settings, CoordinatedTools(), MockLLMClient()).advise(
        demo_profile(), "Can I harvest soybean?"), timeout=2)
    assert result["response"].risk_level == "HIGH"


@pytest.mark.asyncio
async def test_model_cannot_change_deterministic_intent_safety(settings):
    class BadIntent(MockLLMClient):
        async def complete(self, messages, schema=None):
            if schema is Intent:
                return Intent(intent="spray", crop="madeupcrop", language="en", confidence=1)
            return await super().complete(messages, schema)
    tools = FakeTools()
    result = await Orchestrator(settings, tools, BadIntent()).advise(
        demo_profile(), "What is the stock price?")
    assert result["debug"]["intent"]["intent"] == "other"
    assert tools.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["How much pesticide should I spray?",
                                     "What concentration of chemical should I use?",
                                     "Dawa ki matra kya hai?"])
async def test_dosage_variants_never_reach_tools(settings, question):
    tools = FakeTools()
    result = await Orchestrator(settings, tools, MockLLMClient()).advise(demo_profile(), question)
    assert result["response"].refer_to_expert
    assert result["response"].recommendation == "consult_expert"
    assert tools.calls == []
