"""CLI entry point: python -m analizator TICKER"""

from __future__ import annotations

import argparse
import sys

import anthropic

from analizator.agents.runner import AgentRunner, AnthropicLLM
from analizator.config import Settings
from analizator.data.edgar import EdgarClient, make_http_client
from analizator.data.store import FactStore
from analizator.pipeline import Pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bull/bear/judge research report for a US ticker")
    parser.add_argument("ticker")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    with make_http_client(settings.sec_user_agent) as http:
        pipeline = Pipeline(
            edgar=EdgarClient(http, settings.data_dir / "edgar"),
            store=FactStore(settings.data_dir / "facts.duckdb"),
            runner=AgentRunner(AnthropicLLM(anthropic.Anthropic())),
            reports_dir=settings.reports_dir,
        )
        path = pipeline.run(args.ticker)
    print(f"Report written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
