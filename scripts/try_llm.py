"""Run an explicit provider check; no credentials means a controlled unavailable result."""
import argparse
import asyncio
import logging

from app.config import get_settings
from app.llm.client import LLMClient, LLMUnavailable, MockLLMClient
from app.schemas import Intent

log = logging.getLogger("kisansaathi.provider_check")


async def run(provider: str) -> int:
    settings = get_settings().model_copy()
    if provider == "mock":
        client = MockLLMClient()
    else:
        if provider == "groq":
            settings.gemini_api_key = ""
        elif provider == "gemini":
            settings.groq_api_key = ""
        client = LLMClient(settings)
    seed = Intent(intent="weather", crop=None, language="en", confidence=1)
    messages = [{"role": "system", "content": "Classify the farming question as Intent JSON."},
                {"role": "user", "content": '{"question":"What is the weather forecast?","seed":' + seed.model_dump_json() + '}'}]
    try:
        result = await client.complete(messages, Intent)
        log.info("provider=%s result=%s", client.last_provider, result.model_dump_json())
        return 0
    except LLMUnavailable:
        log.error("Provider check unavailable: verify API key, endpoint, model access and quota.")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["mock", "groq", "gemini", "fallback"], default="mock")
    raise SystemExit(asyncio.run(run(parser.parse_args().provider)))
