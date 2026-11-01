"""CLI entry point: python -m analizator TICKER [--backend cli|api]"""

from __future__ import annotations

import argparse
import sys

from analizator.agents.cli_runner import ClaudeCliRunner, find_claude_executable
from analizator.agents.runner import AgentBackend, AgentRunner, AnthropicLLM
from analizator.config import Settings
from analizator.data.edgar import EdgarClient, make_http_client
from analizator.data.store import FactStore
from analizator.pipeline import Pipeline


def make_backend(name: str) -> tuple[AgentBackend, int]:
    """Return the agent backend and how many agents may run at once."""
    if name == "api":
        import anthropic

        return AgentRunner(AnthropicLLM(anthropic.Anthropic())), 2
    # Each claude CLI process uses a few hundred MB, so run agents one at a time.
    return ClaudeCliRunner(find_claude_executable()), 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bull/bear/judge research report for a US ticker")
    parser.add_argument("ticker")
    parser.add_argument(
        "--backend",
        choices=("cli", "api"),
        default="cli",
        help="cli: your Claude subscription via the claude CLI (default); api: ANTHROPIC_API_KEY, billed per token",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    runner, max_workers = make_backend(args.backend)
    with make_http_client(settings.sec_user_agent) as http:
        pipeline = Pipeline(
            edgar=EdgarClient(http, settings.data_dir / "edgar"),
            store=FactStore(settings.data_dir / "facts.duckdb"),
            runner=runner,
            reports_dir=settings.reports_dir,
            max_workers=max_workers,
        )
        path = pipeline.run(args.ticker)
    print(f"Report written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
