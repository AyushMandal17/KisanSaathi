"""OpenAI-compatible providers with bounded validation and provider fallback."""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any, Protocol, TypeVar

from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.schemas import Intent

log = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Provider unavailable or repeatedly failed the requested JSON contract."""


class LLM(Protocol):
    @property
    def last_provider(self) -> str: ...

    async def complete(self, messages: list[dict[str, str]],
                       schema: type[ModelT] | None = None) -> ModelT | str: ...


class LLMClient:
    def __init__(self, settings: Any, clients: dict[str, Any] | None = None):
        self.settings = settings
        self.clients = clients or {}
        self._provider: ContextVar[str] = ContextVar("llm_provider", default="none")

    @property
    def last_provider(self) -> str:
        return self._provider.get()

    async def complete(self, messages: list[dict[str, str]],
                       schema: type[ModelT] | None = None) -> ModelT | str:
        self._provider.set("none")
        for provider in ("groq", "gemini"):
            key = getattr(self.settings, f"{provider}_api_key", "")
            key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            if not key and provider not in self.clients:
                continue
            owned = provider not in self.clients
            client = self.clients.get(provider)
            if client is None:
                client = AsyncOpenAI(api_key=key,
                                     base_url=getattr(self.settings, f"{provider}_base_url"),
                                     timeout=self.settings.llm_timeout_seconds,
                                     max_retries=0)
            request_messages = list(messages)
            if schema:
                request_messages.insert(0, {"role": "system", "content":
                    "Return only JSON satisfying this schema: " +
                    json.dumps(schema.model_json_schema(), ensure_ascii=False)})
            try:
                for attempt in range(2):
                    try:
                        kwargs: dict[str, Any] = {}
                        if schema:
                            kwargs["response_format"] = {"type": "json_object"}
                        result = await client.chat.completions.create(
                            model=getattr(self.settings, f"{provider}_model"),
                            messages=request_messages, **kwargs)
                        content = result.choices[0].message.content or ""
                        parsed = schema.model_validate_json(content) if schema else content
                        if not content.strip():
                            raise ValueError("Empty provider response")
                        self._provider.set(provider)
                        log.info("LLM response provider=%s schema=%s", provider,
                                 schema.__name__ if schema else "text")
                        return parsed
                    except (ValidationError, ValueError, IndexError):
                        log.warning("LLM JSON validation failed provider=%s attempt=%s",
                                    provider, attempt + 1)
                        request_messages.append({"role": "system", "content":
                            "The previous output did not satisfy the JSON contract. "
                            "Return a complete valid JSON object with no extra fields."})
                    except APIConnectionError:
                        log.warning("LLM connection unavailable provider=%s", provider)
                        break
                    except APIStatusError as exc:
                        log.warning("LLM API failure provider=%s status=%s", provider,
                                    exc.status_code)
                        if exc.status_code == 429 or exc.status_code >= 500:
                            break
                        raise LLMUnavailable("Provider configuration or request rejected") from None
            finally:
                if owned:
                    await client.close()
        raise LLMUnavailable("No configured provider returned valid output")


class MockLLMClient:
    """Explicit offline mock. It echoes a validated deterministic seed, never a live claim."""
    last_provider = "mock"

    async def complete(self, messages: list[dict[str, str]],
                       schema: type[ModelT] | None = None) -> ModelT | str:
        payload = json.loads(messages[-1]["content"])
        seed = payload.get("seed")
        if schema is Intent:
            return schema.model_validate(seed)
        if schema:
            return schema.model_validate(seed)
        return "KisanSaathi mock provider is ready."


def build_llm(settings: Any) -> LLM:
    return MockLLMClient() if settings.use_mock_llm else LLMClient(settings)
