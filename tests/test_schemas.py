import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import schemas


def test_documented_contract_examples():
    document = (Path(__file__).resolve().parents[1] / "docs/contract.md").read_text(encoding="utf-8")
    sections = re.split(r"^## (\w+)\s*$", document, flags=re.MULTILINE)
    seen = set()
    for index in range(1, len(sections), 2):
        name, content = sections[index:index + 2]
        model = getattr(schemas, name)
        examples = re.findall(r"```json\s*(.*?)```", content, re.DOTALL)
        assert examples, name
        for example in examples:
            model.model_validate(json.loads(example))
        seen.add(name)
    assert seen == {"CropPlot", "FarmerProfile", "ToolResult", "RiskResult", "Intent", "SourceRef", "AdvisoryResponse"}


def test_failed_tool_cannot_claim_confidence():
    with pytest.raises(ValidationError):
        schemas.ToolResult(tool="weather", source="test", fetched_at="2026-10-31T00:00:00Z",
                           error="offline", confidence="high")


def test_contract_rejects_extra_fields():
    with pytest.raises(ValidationError):
        schemas.CropPlot(crop="soybean", sowing_date="2026-07-05", surprise="typo")
