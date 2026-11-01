import pytest
from conftest import claim, response, text_block, tool_use

from analizator.agents.runner import AgentError, AgentRunner, AgentSpec
from analizator.agents.schema import SUBMIT_CLAIMS_TOOL, ClaimSet
from analizator.tools import Tool, ToolRegistry


class ScriptedLLM:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, **params):
        # Snapshot: the runner keeps appending to the same messages list.
        self.calls.append({**params, "messages": list(params["messages"])})
        return self._responses.pop(0)


SPEC = AgentSpec(
    name="bull",
    model="claude-sonnet-5-5",
    effort="medium",
    system="system",
    finish_tool=SUBMIT_CLAIMS_TOOL,
    finish_parser=ClaimSet.model_validate,
)

REGISTRY = ToolRegistry(
    [
        Tool(
            definition={"name": "get_metrics", "input_schema": {"type": "object"}},
            handler=lambda _: "metrics table",
        )
    ]
)


def tool_results(call):
    return call["messages"][-1]["content"]


def test_runs_tools_then_returns_parsed_claims():
    llm = ScriptedLLM(
        response("tool_use", tool_use("t1", "get_metrics", {})),
        response("tool_use", tool_use("t2", "submit_claims", {"claims": [claim("margins expand")]})),
    )
    result = AgentRunner(llm).run(SPEC, "task", REGISTRY)

    assert [c.statement for c in result.output.claims] == ["margins expand"]
    assert tool_results(llm.calls[1]) == [
        {"type": "tool_result", "tool_use_id": "t1", "content": "metrics table"}
    ]
    assert {t["name"] for t in llm.calls[0]["tools"]} == {"get_metrics", "submit_claims"}


def test_pause_turn_resends_without_new_user_message():
    llm = ScriptedLLM(
        response("pause_turn", text_block("searching")),
        response("tool_use", tool_use("t1", "submit_claims", {"claims": [claim("x")]})),
    )
    AgentRunner(llm).run(SPEC, "task", REGISTRY)
    assert llm.calls[1]["messages"][-1]["role"] == "assistant"


def test_invalid_finish_input_is_returned_as_error():
    llm = ScriptedLLM(
        response("tool_use", tool_use("t1", "submit_claims", {"claims": [{"statement": "x"}]})),
        response("tool_use", tool_use("t2", "submit_claims", {"claims": [claim("x")]})),
    )
    result = AgentRunner(llm).run(SPEC, "task", REGISTRY)
    error = tool_results(llm.calls[1])[0]
    assert error["is_error"] is True and error["tool_use_id"] == "t1"
    assert len(result.output.claims) == 1


def test_unknown_tool_is_reported_to_agent():
    llm = ScriptedLLM(
        response("tool_use", tool_use("t1", "nope", {})),
        response("tool_use", tool_use("t2", "submit_claims", {"claims": [claim("x")]})),
    )
    AgentRunner(llm).run(SPEC, "task", REGISTRY)
    assert tool_results(llm.calls[1])[0]["is_error"] is True


def test_end_turn_without_finish_tool_gets_a_nudge():
    llm = ScriptedLLM(
        response("end_turn", text_block("done")),
        response("tool_use", tool_use("t1", "submit_claims", {"claims": [claim("x")]})),
    )
    AgentRunner(llm).run(SPEC, "task", REGISTRY)
    assert "submit_claims" in llm.calls[1]["messages"][-1]["content"]


def test_text_agent_returns_on_end_turn():
    spec = AgentSpec(name="judge", model="claude-opus-5-5", effort="high", system="s")
    llm = ScriptedLLM(response("end_turn", text_block("# Report")))
    assert AgentRunner(llm).run(spec, "task", REGISTRY).text == "# Report"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_early_stop_raises(stop_reason):
    llm = ScriptedLLM(response(stop_reason, text_block("")))
    with pytest.raises(AgentError):
        AgentRunner(llm).run(SPEC, "task", REGISTRY)


def test_gives_up_after_max_turns():
    llm = ScriptedLLM(*[response("end_turn", text_block("no")) for _ in range(3)])
    with pytest.raises(AgentError):
        AgentRunner(llm, max_turns=3).run(SPEC, "task", REGISTRY)
