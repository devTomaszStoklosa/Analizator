"""Generic tool-use loop shared by every agent role."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from analizator.tools import ToolRegistry

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMClient(Protocol):
    def complete(self, **params: Any) -> Any: ...


class AnthropicLLM:
    """Streams each request (long agent turns) and opts into server-side refusal fallbacks."""

    def __init__(self, client: Any):
        self._client = client

    def complete(self, **params: Any) -> Any:
        with self._client.beta.messages.stream(
            betas=[FALLBACK_BETA], fallbacks="default", **params
        ) as stream:
            return stream.get_final_message()


class AgentError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentSpec:
    name: str
    model: str
    effort: str
    system: str
    server_tools: tuple[dict, ...] = ()
    finish_tool: dict | None = None
    # Parses the finish tool input; raising ValueError sends the error back to the agent.
    finish_parser: Callable[[dict], Any] | None = None


@dataclass(frozen=True)
class AgentResult:
    text: str
    output: Any = None


class AgentRunner:
    def __init__(self, llm: LLMClient, max_turns: int = 30, max_tokens: int = 64_000):
        self._llm = llm
        self._max_turns = max_turns
        self._max_tokens = max_tokens

    def run(self, spec: AgentSpec, task: str, registry: ToolRegistry) -> AgentResult:
        tools = [*registry.definitions, *spec.server_tools]
        if spec.finish_tool:
            tools.append(spec.finish_tool)
        messages: list[dict] = [{"role": "user", "content": task}]

        for _ in range(self._max_turns):
            response = self._llm.complete(
                model=spec.model,
                max_tokens=self._max_tokens,
                system=spec.system,
                tools=tools,
                messages=messages,
                output_config={"effort": spec.effort},
                cache_control={"type": "ephemeral"},
            )
            if response.stop_reason in ("refusal", "max_tokens"):
                raise AgentError(f"{spec.name} stopped early: {response.stop_reason}")
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                # A server-side tool hit its iteration limit; re-sending resumes the turn.
                continue

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                if spec.finish_tool is None:
                    return AgentResult(text=_text(response))
                messages.append(
                    {"role": "user", "content": f"Call {spec.finish_tool['name']} now with your final answer."}
                )
                continue

            results, output, finished = [], None, False
            for block in tool_uses:
                if spec.finish_tool and block.name == spec.finish_tool["name"]:
                    try:
                        output = spec.finish_parser(block.input) if spec.finish_parser else block.input
                        finished = True
                        results.append(_tool_result(block.id, "Received."))
                    except ValueError as error:
                        results.append(_tool_result(block.id, f"Invalid input: {error}", is_error=True))
                else:
                    results.append(_execute(registry, block))
            if finished:
                return AgentResult(text=_text(response), output=output)
            messages.append({"role": "user", "content": results})

        raise AgentError(f"{spec.name} did not finish within {self._max_turns} turns")


def _execute(registry: ToolRegistry, block: Any) -> dict:
    try:
        return _tool_result(block.id, registry.execute(block.name, block.input))
    except (KeyError, ValueError, TypeError) as error:
        return _tool_result(block.id, f"Tool error: {error}", is_error=True)


def _tool_result(tool_use_id: str, content: str, is_error: bool = False) -> dict:
    result = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        result["is_error"] = True
    return result


def _text(response: Any) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()
