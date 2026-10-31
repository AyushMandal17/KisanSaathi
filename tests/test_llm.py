from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from app.config import Settings
from app.llm.client import LLMClient, LLMUnavailable, MockLLMClient
from app.schemas import Intent


def sdk(*items):
    responses = [item if isinstance(item, Exception) else SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=item))]) for item in items]
    create = AsyncMock(side_effect=responses)
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


VALID = '{"intent":"spray","crop":"soybean","language":"en","confidence":0.9}'


@pytest.mark.asyncio
async def test_invalid_json_retried_once():
    primary = sdk("not json", VALID)
    client = LLMClient(Settings(_env_file=None), {"groq": primary})
    result = await client.complete([{"role": "user", "content": "classify"}], Intent)
    assert result.intent == "spray"
    assert primary.chat.completions.create.await_count == 2
    assert client.last_provider == "groq"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", 429, 503])
async def test_transient_failure_uses_gemini(failure):
    request = httpx.Request("POST", "https://provider.invalid/chat/completions")
    error = (APITimeoutError(request=request) if failure == "timeout" else
             APIStatusError("failure", response=httpx.Response(failure, request=request), body={}))
    primary, fallback = sdk(error), sdk(VALID)
    client = LLMClient(Settings(_env_file=None), {"groq": primary, "gemini": fallback})
    assert isinstance(await client.complete([], Intent), Intent)
    assert client.last_provider == "gemini"
    assert fallback.chat.completions.create.await_count == 1


@pytest.mark.asyncio
async def test_validation_failure_can_fall_back_without_looping():
    primary, fallback = sdk("{}", "{}"), sdk(VALID)
    client = LLMClient(Settings(_env_file=None), {"groq": primary, "gemini": fallback})
    assert (await client.complete([], Intent)).intent == "spray"
    assert primary.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_no_configured_provider_is_controlled():
    settings = Settings(_env_file=None, groq_api_key="", gemini_api_key="")
    with pytest.raises(LLMUnavailable):
        await LLMClient(settings).complete([])


@pytest.mark.asyncio
async def test_mock_returns_shared_contract():
    result = await MockLLMClient().complete([{"role": "user", "content": '{"seed":' + VALID + '}'}], Intent)
    assert isinstance(result, Intent)
