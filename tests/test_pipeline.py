import threading
from datetime import date

from conftest import claim, response, text_block, tool_use

from analizator.agents.runner import AgentRunner
from analizator.data.edgar import Company
from analizator.data.store import FactStore
from analizator.pipeline import Pipeline


class FakeEdgar:
    def __init__(self, company_facts):
        self._facts = company_facts

    def company(self, ticker):
        return Company(cik=1234567, ticker=ticker.upper(), name="Sample Corp")

    def company_facts(self, cik):
        return self._facts


class RoleLLM:
    """Answers by role (read from the system prompt) so parallel calls stay deterministic."""

    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()

    def complete(self, **params):
        with self._lock:
            self.calls.append(params)
        system = params["system"]
        if "You are the judge" in system:
            return response("end_turn", text_block("## Summary\nBalanced view."))
        side = "bull" if "You are the bull analyst" in system else "bear"
        is_rebuttal = "Rebuttal round" in params["messages"][0]["content"]
        rebuts = ("BEAR-1" if side == "bull" else "BULL-1") if is_rebuttal else None
        return response(
            "tool_use",
            tool_use("t1", "submit_claims", {"claims": [claim(f"{side} point", rebuts)]}),
        )


def test_pipeline_writes_report(tmp_path, company_facts):
    llm = RoleLLM()
    pipeline = Pipeline(
        edgar=FakeEdgar(company_facts),
        store=FactStore(),
        runner=AgentRunner(llm),
        reports_dir=tmp_path,
        today=lambda: date(2026, 11, 1),
    )
    path = pipeline.run("smpl")

    assert path.name == "SMPL_2026-11-01.md"
    report = path.read_text(encoding="utf-8")
    assert "# Sample Corp (SMPL): research report" in report
    assert "latest EDGAR filing: 2025-02-15" in report
    assert "## Summary\nBalanced view." in report
    for row in ("| BULL-1 |", "| BEAR-1 |", "| BULL-R-1 | BEAR-1 |", "| BEAR-R-1 | BULL-1 |"):
        assert row in report

    judge_call = next(c for c in llm.calls if "You are the judge" in c["system"])
    assert judge_call["model"] == "claude-opus-5-5"
    assert "BEAR-R-1" in judge_call["messages"][0]["content"]


def test_opening_round_is_blind(tmp_path, company_facts):
    llm = RoleLLM()
    Pipeline(FakeEdgar(company_facts), FactStore(), AgentRunner(llm), tmp_path).run("SMPL")
    openings = [c for c in llm.calls if "You are the judge" not in c["system"]
                and "Rebuttal" not in c["messages"][0]["content"]]
    assert len(openings) == 2
    assert all("point" not in c["messages"][0]["content"] for c in openings)
