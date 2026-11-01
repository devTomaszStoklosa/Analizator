import httpx
import pytest

from analizator.data.edgar import EdgarClient, TickerNotFoundError

TICKERS = {"0": {"cik_str": 1234567, "ticker": "SMPL", "title": "Sample Corp"}}


def make_client(tmp_path, company_facts, calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.headers["User-Agent"] == "Test test@example.com"
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS)
        if request.url.path.endswith("CIK0001234567.json"):
            return httpx.Response(200, json=company_facts)
        return httpx.Response(404)

    http = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": "Test test@example.com"}
    )
    return EdgarClient(http, tmp_path)


def test_company_lookup_is_case_insensitive(tmp_path, company_facts):
    client = make_client(tmp_path, company_facts, [])
    company = client.company("smpl")
    assert (company.cik, company.ticker, company.name) == (1234567, "SMPL", "Sample Corp")


def test_unknown_ticker(tmp_path, company_facts):
    with pytest.raises(TickerNotFoundError):
        make_client(tmp_path, company_facts, []).company("NOPE")


def test_responses_are_cached(tmp_path, company_facts):
    calls = []
    client = make_client(tmp_path, company_facts, calls)
    client.company_facts(1234567)
    assert client.company_facts(1234567)["entityName"] == "Sample Corp"
    assert len(calls) == 1
