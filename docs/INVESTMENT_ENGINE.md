# Atlas Trading Engine vs Investment Engine

Phase 1 foundation. No scoring, no dip detection, no brokerage, no ML.

## Two engines

```
ATLAS TRADING ENGINE                         ATLAS INVESTMENT ENGINE
Hyperliquid perps                            Stocks / ETFs / indexes (future)
A+ scanner, micro coach                      Models + provider interfaces only
Paper journal  data/paper_journal.jsonl      Paper investment  data/investment/
Shadow research                              Thesis / alert *states* (no detector)
Discord /paper /research                     Future Discord (not wired)
```

They share process, logging (`structlog`), config style, and Discord *client* later.
They do **not** share paper PnL, journals, gates, or position sizing.

## Responsibilities

| | Trading | Investment |
|---|---|---|
| Job | Short-horizon perp setups | Long-horizon capital research |
| Output | Paper TRIGGER / WAIT | Future WATCH / ACCUMULATION / … |
| Execution | None (manual) | None (manual / paper book) |
| Scores | Setup quality, R:R | Opportunity / confidence / evidence (not P(profit)) |

## Data ownership

- Trading: `backend/data/paper_journal.jsonl`, `shadow_*.jsonl`, `funnel*.jsonl`
- Investment: `backend/data/investment/` only
- Postgres `opportunities` / `paper_trades` tables are **trading**. Do not write investment rows there in Phase 1.

## Statistics ownership

- `/paper` and `/research` = Hyperliquid paper + shadow **only**
- Investment paper book (cash, shares, dividends, SPY benchmark) is a **different ledger**
- Mixing those numbers is a bug

## Reused from Atlas (do not duplicate)

- `structlog` logging
- Pydantic settings pattern (investment settings stay in this package later)
- Discord DM transport (later phase; do not add slash commands yet)
- `yfinance` already a dependency (quality-dip). Investment providers may use it **later**
- `quality_dip_scanner` / `robinhood_brief` are **related research feeds**, not this engine. Do not merge scoring.

## Not reused

- Hyperliquid adapter (perps, not cash equities)
- RSI 28/72, extension 1.4%, R:R 1.8
- `PaperJournal` / `ShadowResearch` / `PaperPipeline`

## Future interfaces (Phase 1 = Protocols only)

- Price / fundamental / valuation / news / macro providers
- Return `MeasuredValue` with `quality ∈ {FRESH, STALE, MISSING, CONFLICTING, UNKNOWN}`
- Missing → `MISSING` / `UNKNOWN`. Never invent fundamentals.

## Failure behavior

- High-conviction states blocked if critical evidence is missing
- Allocation blocked without portfolio value + cash
- `PaperInvestmentAccount.execute_broker_order` always raises
- Engine crash must not stop the trading API (not started in `main.py` yet)

## Phase 2 (this layer)

Universe ingest, Yahoo price / fundamental / valuation adapters behind the
provider interfaces, isolated historical storage, freshness, validation,
snapshots, quality report. **Still no scoring algorithm.**

See `docs/INVESTMENT_DATA.md`.

## Phase 3 (this layer)

Research/scoring on `InvestmentSnapshot` + OHLCV history: drawdown, valuation
context, fundamental quality, thesis, risk, evidence, ordinal opportunity
score, explainable classification. **No alerts, allocation, orders, or ML.**

See `docs/INVESTMENT_RESEARCH.md`.

