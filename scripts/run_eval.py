"""Offline scenario regression evaluation, not a measured agronomic accuracy claim."""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.agent.orchestrator import Orchestrator
from app.config import Settings
from app.llm.client import MockLLMClient
from app.schemas import AdvisoryResponse
from tests.fakes import EVAL, FakeTools, demo_profile

log = logging.getLogger("kisansaathi.eval")


async def evaluate_case(case: dict, settings: Settings) -> list[str]:
    tools = FakeTools(case["scenario"])
    app = Orchestrator(settings, tools=tools, llm=MockLLMClient())
    bundle = await app.advise(demo_profile(case.get("profile", "single")), case["question"])
    answer = AdvisoryResponse.model_validate(bundle["response"])
    debug = bundle["debug"]
    failures = []
    for key, actual in [("intent", debug["intent"]["intent"]), ("risk", answer.risk_level),
                        ("recommendation", answer.recommendation), ("language", answer.language)]:
        if actual != case[key]:
            failures.append(f"{key}: expected {case[key]}, got {actual}")
    if set(tools.calls) != set(case["tools"]):
        failures.append("required-tool selection differs")
    for part in case.get("contains", []):
        if part.casefold() not in answer.answer_text.casefold():
            failures.append(f"missing expected text: {part}")
    for part in case.get("absent", []):
        if part.casefold() in answer.answer_text.casefold():
            failures.append(f"unexpected text: {part}")
    if case.get("gap") and not answer.data_gaps:
        failures.append("missing data gap")
    if case.get("expert") and not answer.refer_to_expert:
        failures.append("missing expert referral")
    if answer.risk_level == "HIGH" and answer.recommendation == "do":
        failures.append("unsafe high-risk recommendation")
    if tools.calls and not answer.sources and not answer.data_gaps:
        failures.append("neither source provenance nor error explanation")
    return failures


async def run(output: Path) -> int:
    settings = Settings(_env_file=None, use_mock_llm=True, data_mode="demo")
    rows = []
    for case in EVAL["cases"]:
        try:
            failures = await evaluate_case(case, settings)
        except Exception as exc:
            failures = [f"unhandled {type(exc).__name__}"]
        rows.append((case["id"], not failures, "; ".join(failures) or "All assertions passed"))
    passed = sum(ok for _, ok, _ in rows)
    text = ["# KisanSaathi evaluation report", "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}", "",
            f"**{passed}/{len(rows)} passed ({100 * passed / len(rows):.1f}%).**", "",
            "Synthetic scenario regression with MockLLMClient and injected tools. "
            "This does not verify live providers, market accuracy, language fluency with "
            "real farmers, or agronomic validity. Every threshold remains a demo rule.", "",
            "| Case | Result | Evidence |", "| --- | --- | --- |"]
    text.extend(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail.replace('|', '/')} |"
                for name, ok, detail in rows)
    text.extend(["", "## Failures", ""] +
                ([f"- {name}: {detail}" for name, ok, detail in rows if not ok] or ["None in this run."]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(text) + "\n", encoding="utf-8")
    log.info("Evaluation %s/%s passed; report=%s", passed, len(rows), output)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("eval_report.md"))
    raise SystemExit(asyncio.run(run(parser.parse_args().output)))
