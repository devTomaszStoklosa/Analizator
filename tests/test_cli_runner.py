import json

import pytest
from conftest import claim

from analizator.agents.cli_runner import ClaudeCliRunner
from analizator.agents.runner import AgentError, AgentSpec
from analizator.agents.schema import SUBMIT_CLAIMS_TOOL, ClaimSet
from analizator.tools import WEB_FETCH, WEB_SEARCH, Tool, ToolRegistry


class FakeCommand:
    def __init__(self, *outputs: dict):
        self._outputs = list(outputs)
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, args: list[str], stdin: str) -> str:
        self.calls.append((args, stdin))
        return json.dumps(self._outputs.pop(0))


ANALYST = AgentSpec(
    name="bull",
    model="claude-sonnet-5-5",
    effort="medium",
    system="You are the bull analyst.",
    server_tools=(WEB_SEARCH,),
    finish_tool=SUBMIT_CLAIMS_TOOL,
    finish_parser=ClaimSet.model_validate,
)
JUDGE = AgentSpec(
    name="judge", model="claude-opus-5-5", effort="high", system="You are the judge.",
    server_tools=(WEB_FETCH,),
)
REGISTRY = ToolRegistry(
    [
        Tool(
            definition={"name": "get_metrics", "input_schema": {"type": "object"}},
            handler=lambda _: "| revenue | 1,000M |",
            prefetch=({},),
        )
    ]
)


def arg(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def test_analyst_uses_structured_output_and_web_search():
    command = FakeCommand({"is_error": False, "structured_output": {"claims": [claim("growth")]}})
    result = ClaudeCliRunner("claude", command).run(ANALYST, "Research.", REGISTRY)

    assert [c.statement for c in result.output.claims] == ["growth"]
    args, stdin = command.calls[0]
    assert arg(args, "--model") == "claude-sonnet-5-5"
    assert arg(args, "--effort") == "medium"
    assert arg(args, "--tools") == "WebSearch"
    assert arg(args, "--setting-sources") == ""
    assert arg(args, "--system-prompt").startswith("You are the bull analyst.")
    assert json.loads(arg(args, "--json-schema")) == SUBMIT_CLAIMS_TOOL["input_schema"]
    assert stdin.startswith("Research.")
    assert '### get_metrics({})\n| revenue | 1,000M |' in stdin


def test_falls_back_to_json_in_result_text():
    command = FakeCommand({"is_error": False, "result": json.dumps({"claims": [claim("x")]})})
    result = ClaudeCliRunner("claude", command).run(ANALYST, "Research.", REGISTRY)
    assert len(result.output.claims) == 1


def test_invalid_output_is_retried_with_the_error():
    command = FakeCommand(
        {"is_error": False, "result": "not json"},
        {"is_error": False, "structured_output": {"claims": [claim("x")]}},
    )
    ClaudeCliRunner("claude", command).run(ANALYST, "Research.", REGISTRY)
    assert "previous answer was rejected" in command.calls[1][1]


def test_gives_up_after_attempts():
    command = FakeCommand(*[{"is_error": False, "result": "nope"}] * 2)
    with pytest.raises(AgentError):
        ClaudeCliRunner("claude", command).run(ANALYST, "Research.", REGISTRY)


def test_cli_error_raises():
    command = FakeCommand({"is_error": True, "result": "Failed to authenticate"})
    with pytest.raises(AgentError, match="Failed to authenticate"):
        ClaudeCliRunner("claude", command).run(ANALYST, "Research.", REGISTRY)


def test_judge_returns_text_without_schema():
    command = FakeCommand({"is_error": False, "result": "  ## Summary\nOk.  "})
    result = ClaudeCliRunner("claude", command).run(JUDGE, "Check.", REGISTRY)
    assert result.text == "## Summary\nOk."
    args, _ = command.calls[0]
    assert "--json-schema" not in args
    assert arg(args, "--tools") == "WebFetch"
