# Analizator

Multi-agent research pipeline for US stocks: a bull agent and a bear agent argue a case from SEC EDGAR data and web sources, and a judge agent writes a cited pro/con report.

## How it works

1. Fetches XBRL company facts from SEC EDGAR, keeps annual 10-K values and stores them in DuckDB (`data/`).
2. Computes metrics in code (growth, margins, free cash flow, debt/equity, interest coverage). Agents read them through tools and never do the arithmetic themselves.
3. Bull and bear agents (Claude Sonnet 5.5, web search) research independently, then answer each other in one rebuttal round.
4. A judge agent (Claude Opus 5.5, web fetch) checks figures and sources and writes the report to `reports/<TICKER>_<date>.md`.

Output is research support, not investment advice.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env   # then fill in ANTHROPIC_API_KEY and SEC_USER_AGENT
```

## Usage

```bash
.venv/Scripts/python -m analizator AAPL
```

## Tests

```bash
.venv/Scripts/python -m pytest
```
