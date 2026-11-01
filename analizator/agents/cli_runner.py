"""Subscription backend: runs each agent as a headless Claude Code session (`claude -p`).

Uses the Claude login of the local `claude` CLI instead of an API key. The CLI
cannot call our Python tools mid-turn, so their outputs are prefetched into the prompt.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from analizator.agents.runner import AgentError, AgentResult, AgentSpec
from analizator.tools import ToolRegistry

# Server tool name -> Claude Code built-in tool name.
_CLI_TOOLS = {"web_search": "WebSearch", "web_fetch": "WebFetch"}

_TOOL_NOTE = (
    "\n\nThe data tools named above (get_metrics, get_raw_series) are not callable in this "
    "session. Their outputs are included in the user message; treat them as the tool results. "
    "Where you are told to call submit_claims, return its input as your final structured answer instead."
)

# (args, stdin) -> stdout
CommandRunner = Callable[[list[str], str], str]


def find_claude_executable() -> str:
    """Resolve the CLI binary. On Windows npm installs a .cmd shim; call the bundled
    claude.exe behind it directly, because cmd.exe would mangle quoted arguments."""
    found = shutil.which("claude")
    if found is None:
        raise AgentError("claude CLI not found on PATH. Install Claude Code and log in first.")
    path = Path(found)
    if path.suffix.lower() == ".cmd":
        exe = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return found


def run_command(args: list[str], stdin: str) -> str:
    # Empty working directory, so no project CLAUDE.md is picked up.
    with tempfile.TemporaryDirectory() as cwd:
        completed = subprocess.run(
            args,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            timeout=1800,
            check=False,
        )
    if not completed.stdout.strip():
        raise AgentError(f"claude CLI produced no output: {completed.stderr.strip()[:500]}")
    return completed.stdout


class ClaudeCliRunner:
    def __init__(self, executable: str, command: CommandRunner = run_command, attempts: int = 2):
        self._executable = executable
        self._command = command
        self._attempts = attempts

    def run(self, spec: AgentSpec, task: str, registry: ToolRegistry) -> AgentResult:
        prompt = f"{task}\n\n{_tool_outputs(registry)}"
        last_error = ""
        for _ in range(self._attempts):
            stdin = prompt if not last_error else (
                f"{prompt}\n\nYour previous answer was rejected: {last_error}. Answer again."
            )
            stdout = self._command(self._args(spec), stdin)
            try:
                result = json.loads(stdout)
            except json.JSONDecodeError as error:
                raise AgentError(f"{spec.name}: unexpected claude CLI output: {stdout[:500]}") from error
            if result.get("is_error"):
                raise AgentError(f"{spec.name}: claude CLI error: {result.get('result')}")
            text = result.get("result") or ""
            if spec.finish_tool is None:
                return AgentResult(text=text.strip())
            try:
                return AgentResult(text="", output=_parse_output(spec, result))
            except ValueError as error:
                last_error = str(error)[:1000]
        raise AgentError(f"{spec.name}: no valid output after {self._attempts} attempts: {last_error}")

    def _args(self, spec: AgentSpec) -> list[str]:
        tools = [_CLI_TOOLS[t["name"]] for t in spec.server_tools if t["name"] in _CLI_TOOLS]
        args = [
            self._executable,
            "-p",
            "--output-format", "json",
            "--model", spec.model,
            "--effort", spec.effort,
            "--system-prompt", spec.system + _TOOL_NOTE,
            # Only the web tools; skip user settings (hooks, plugins) and MCP servers.
            "--tools", ",".join(tools),
            "--allowedTools", ",".join(tools),
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if spec.finish_tool is not None:
            args += ["--json-schema", json.dumps(spec.finish_tool["input_schema"])]
        return args


def _parse_output(spec: AgentSpec, result: dict) -> Any:
    data = result.get("structured_output")
    if data is None:
        try:
            data = json.loads(result.get("result") or "")
        except json.JSONDecodeError as error:
            raise ValueError(f"output is not valid JSON ({error})") from error
    return spec.finish_parser(data) if spec.finish_parser else data


def _tool_outputs(registry: ToolRegistry) -> str:
    sections = [
        f"### {name}({json.dumps(tool_input)})\n{output}"
        for name, tool_input, output in registry.prefetched()
    ]
    return "## Data tool outputs (SEC EDGAR)\n\n" + "\n\n".join(sections)
