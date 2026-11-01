"""Client-side tools the agents can call, plus server-side tool definitions."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from analizator.data.facts import CONCEPTS
from analizator.data.metrics import compute_metrics, to_markdown
from analizator.data.store import FactStore

WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}
WEB_FETCH = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 10}


@dataclass(frozen=True)
class Tool:
    definition: dict
    handler: Callable[[dict], str]


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools = {t.definition["name"]: t for t in tools}

    @property
    def definitions(self) -> list[dict]:
        return [t.definition for t in self._tools.values()]

    def execute(self, name: str, tool_input: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool.handler(tool_input)


def financial_tools(store: FactStore, ticker: str) -> list[Tool]:
    def get_metrics(_: dict) -> str:
        return to_markdown(compute_metrics(store.series(ticker)))

    def get_raw_series(tool_input: dict) -> str:
        concept = tool_input["concept"]
        if concept not in CONCEPTS:
            return f"Unknown concept {concept!r}. Valid: {', '.join(CONCEPTS)}"
        return json.dumps(store.raw(ticker, concept), default=str)

    return [
        Tool(
            definition={
                "name": "get_metrics",
                "description": (
                    f"Annual financial metrics for {ticker} computed from SEC EDGAR 10-K filings: "
                    "base values (USD) and derived ratios for the last 5 fiscal years. "
                    "Use this for every company figure you cite; 'n/a' means the data is missing."
                ),
                "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            handler=get_metrics,
        ),
        Tool(
            definition={
                "name": "get_raw_series",
                "description": (
                    "Raw annual values for one concept, with the XBRL tag, filing date and "
                    "accession number. Use it to cite the exact filing behind a number."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {"concept": {"type": "string", "enum": list(CONCEPTS)}},
                    "required": ["concept"],
                    "additionalProperties": False,
                },
            },
            handler=get_raw_series,
        ),
    ]
