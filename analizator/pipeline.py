"""End-to-end flow: EDGAR data -> blind bull/bear -> rebuttals -> judge -> report."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from importlib.resources import files
from pathlib import Path

from analizator.agents.runner import AgentRunner, AgentSpec
from analizator.agents.schema import SUBMIT_CLAIMS_TOOL, Claim, ClaimSet
from analizator.config import ANALYST_MODEL, JUDGE_MODEL
from analizator.data.edgar import EdgarClient
from analizator.data.facts import extract_annual_facts
from analizator.data.store import FactStore
from analizator.report import render_report
from analizator.tools import WEB_FETCH, WEB_SEARCH, ToolRegistry, financial_tools

OPENING_TASK = "Research the company and submit your opening claims."


class Pipeline:
    def __init__(
        self,
        edgar: EdgarClient,
        store: FactStore,
        runner: AgentRunner,
        reports_dir: Path,
        today: Callable[[], date] = date.today,
    ):
        self._edgar = edgar
        self._store = store
        self._runner = runner
        self._reports_dir = reports_dir
        self._today = today

    def run(self, ticker: str) -> Path:
        company = self._edgar.company(ticker)
        facts = extract_annual_facts(self._edgar.company_facts(company.cik))
        if not facts:
            raise ValueError(f"No annual 10-K facts found for {company.ticker}")
        self._store.replace(company.ticker, facts)
        registry = ToolRegistry(financial_tools(self._store, company.ticker))

        today = self._today()
        context = {"company": company.name, "ticker": company.ticker, "today": today.isoformat()}
        bull, bear = _analyst_spec("bull", context), _analyst_spec("bear", context)

        # Opening round runs blind: neither side sees the other's claims.
        bull_open, bear_open = self._run_pair(
            (bull, OPENING_TASK), (bear, OPENING_TASK), registry, ("BULL", "BEAR")
        )
        bull_reply, bear_reply = self._run_pair(
            (bull, _rebuttal_task(bull_open, bear_open)),
            (bear, _rebuttal_task(bear_open, bull_open)),
            registry,
            ("BULL-R", "BEAR-R"),
        )

        all_claims = [*bull_open, *bear_open, *bull_reply, *bear_reply]
        latest_filing = self._store.latest_filed(company.ticker)
        judge = self._runner.run(
            AgentSpec(
                name="judge",
                model=JUDGE_MODEL,
                effort="high",
                system=_prompt("judge", context),
                server_tools=(WEB_FETCH,),
            ),
            _judge_task(all_claims, latest_filing),
            registry,
        )

        report = render_report(company, today, latest_filing, judge.text, all_claims)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        path = self._reports_dir / f"{company.ticker}_{today.isoformat()}.md"
        path.write_text(report, encoding="utf-8")
        return path

    def _run_pair(self, first, second, registry, prefixes) -> tuple[list[Claim], list[Claim]]:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._runner.run, spec, task, registry) for spec, task in (first, second)]
            results = [f.result().output for f in futures]
        return tuple(_label(r.claims, p) for r, p in zip(results, prefixes))


def _analyst_spec(role: str, context: dict) -> AgentSpec:
    return AgentSpec(
        name=role,
        model=ANALYST_MODEL,
        effort="medium",
        system=_prompt(role, context),
        server_tools=(WEB_SEARCH,),
        finish_tool=SUBMIT_CLAIMS_TOOL,
        finish_parser=ClaimSet.model_validate,
    )


def _prompt(role: str, context: dict) -> str:
    template = files("analizator.agents").joinpath(f"prompts/{role}.md").read_text(encoding="utf-8")
    return template.format(**context)


def _label(claims: list[Claim], prefix: str) -> list[Claim]:
    return [c.model_copy(update={"id": f"{prefix}-{i}"}) for i, c in enumerate(claims, start=1)]


def _dump(claims: list[Claim]) -> str:
    return json.dumps([c.model_dump() for c in claims], indent=2)


def _rebuttal_task(own: list[Claim], opponent: list[Claim]) -> str:
    return (
        "Rebuttal round. Your opening claims:\n"
        f"{_dump(own)}\n\nThe opposing analyst's claims:\n{_dump(opponent)}\n\n"
        "Answer the opponent's strongest claims with evidence. Where they are right, "
        "concede or narrow your position instead of repeating it. Submit 2-5 claims, each "
        "with rebuts set to the opponent claim id it answers."
    )


def _judge_task(claims: list[Claim], latest_filing: date | None) -> str:
    filing = latest_filing.isoformat() if latest_filing else "unknown"
    return (
        f"Latest EDGAR filing date: {filing}.\n\n"
        f"Claims from both analysts (ids starting with BULL are for, BEAR against; "
        f"-R marks rebuttals):\n{_dump(claims)}\n\nCheck them and write the report."
    )
