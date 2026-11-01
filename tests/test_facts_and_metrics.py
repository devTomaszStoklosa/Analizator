from datetime import date

import pytest

from analizator.data.facts import extract_annual_facts
from analizator.data.metrics import compute_metrics, to_markdown
from analizator.data.store import FactStore

Y22, Y23, Y24 = date(2022, 12, 31), date(2023, 12, 31), date(2024, 12, 31)


def revenue_facts(company_facts):
    return {f.period_end: f for f in extract_annual_facts(company_facts) if f.concept == "revenue"}


def test_revenue_keeps_only_annual_10k_values(company_facts):
    assert set(revenue_facts(company_facts)) == {Y22, Y23, Y24}


def test_restated_value_uses_latest_filing(company_facts):
    assert revenue_facts(company_facts)[Y23].value == 1_150_000_000


def test_fallback_tag_only_fills_missing_years(company_facts):
    facts = revenue_facts(company_facts)
    assert facts[Y23].tag == "Revenues"
    assert facts[Y24].tag == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert facts[Y24].value == 1_380_000_000


@pytest.fixture
def table(company_facts):
    store = FactStore()
    store.replace("SMPL", extract_annual_facts(company_facts))
    return compute_metrics(store.series("SMPL"))


def test_derived_metrics(table):
    assert table["revenue_growth"][Y24] == pytest.approx(1_380 / 1_150 - 1)
    assert table["revenue_growth"][Y22] is None
    assert table["gross_margin"][Y24] == pytest.approx(0.40)
    assert table["operating_margin"][Y24] == pytest.approx(0.20)
    assert table["net_margin"][Y24] == pytest.approx(0.10)
    assert table["free_cash_flow"][Y24] == 200_000_000
    assert table["debt_to_equity"][Y24] == pytest.approx(0.5)
    assert table["interest_coverage"][Y24] == pytest.approx(12.0)


def test_missing_inputs_give_none(table):
    assert table["gross_margin"][Y23] is None
    assert table["free_cash_flow"][Y23] is None


def test_markdown_formats_values(table):
    md = to_markdown(table)
    assert "| revenue | 1,000M | 1,150M | 1,380M |" in md
    assert "| gross_margin | n/a | n/a | 40.0% |" in md
    assert "| interest_coverage | n/a | n/a | 12.00x |" in md


def test_latest_filed(company_facts):
    store = FactStore()
    store.replace("SMPL", extract_annual_facts(company_facts))
    assert store.latest_filed("SMPL") == date(2025, 2, 15)
