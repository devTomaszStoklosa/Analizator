import json
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def company_facts() -> dict:
    return json.loads((FIXTURES / "companyfacts_sample.json").read_text(encoding="utf-8"))


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def tool_use(block_id: str, name: str, tool_input: dict):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def response(stop_reason: str, *content):
    return SimpleNamespace(stop_reason=stop_reason, content=list(content))


def claim(statement: str, rebuts: str | None = None) -> dict:
    return {
        "statement": statement,
        "evidence": "evidence",
        "source_url": "sec-edgar:0001-25-000001",
        "source_date": "2025-02-15",
        "confidence": "medium",
        "would_change_mind": "a different number",
        "rebuts": rebuts,
    }
