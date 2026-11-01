# Analizator

Multi-agent research pipeline for US stocks: a bull agent and a bear agent argue a case from SEC EDGAR data and web sources, and a judge agent writes a cited pro/con report.

## How it works

1. Fetches XBRL company facts from SEC EDGAR, keeps annual 10-K values and stores them in DuckDB (`data/`).
2. Computes metrics in code (growth, margins, free cash flow, debt/equity, interest coverage). Agents read them through tools and never do the arithmetic themselves.
3. Bull and bear agents (Claude Sonnet 5.5, web search) research independently, then answer each other in one rebuttal round.
4. A judge agent (Claude Opus 5.5, web fetch) checks figures and sources and writes the report to `reports/<TICKER>_<date>.md`.

Output is research support, not investment advice.

## Backends

- `cli` (default): runs each agent as a headless Claude Code session (`claude -p`) on your Claude subscription. No API key and no per-token cost, but runs count against your plan's usage limits. Requires the `claude` CLI installed and logged in. Agents run one at a time to save memory.
- `api`: calls the Claude API with `ANTHROPIC_API_KEY`, billed per token. Agents call the data tools on demand and run in parallel.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env   # then fill in SEC_USER_AGENT (and ANTHROPIC_API_KEY for --backend api)
```

## Usage

```bash
.venv/Scripts/python -m analizator AAPL
.venv/Scripts/python -m analizator AAPL --backend api
```

## Tests

```bash
.venv/Scripts/python -m pytest
```
