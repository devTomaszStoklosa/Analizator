"""Render the final Markdown report."""

from __future__ import annotations

from datetime import date

from analizator.agents.schema import Claim
from analizator.data.edgar import Company


def render_report(
    company: Company,
    today: date,
    latest_filing: date | None,
    judge_text: str,
    claims: list[Claim],
) -> str:
    lines = [
        f"# {company.name} ({company.ticker}): research report",
        "",
        f"Generated {today.isoformat()} · latest EDGAR filing: "
        f"{latest_filing.isoformat() if latest_filing else 'n/a'}",
        "",
        "> Research support only, not investment advice. Verify sources before acting.",
        "",
        judge_text,
        "",
        "## Appendix: all claims",
        "",
        "| id | rebuts | confidence | statement | source | date |",
        "|---|---|---|---|---|---|",
    ]
    for c in claims:
        lines.append(
            f"| {c.id} | {c.rebuts or ''} | {c.confidence} | {_cell(c.statement)} "
            f"| {_cell(c.source_url)} | {c.source_date} |"
        )
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
