# Prediction Markets Phase 1 — Kalshi Public Research

Status: **research-only feature phase**

Certified rollback baseline before this phase:
`54d4c1d69e796f66b25addc25b651b71448f7cc8`

## Purpose

Phase 1 adds public prediction-market discovery to Atlas without account access or
order execution.

The implementation is based on Kalshi's public Trade API documentation:

- Public market data is available without authentication.
- Production public market-data base URL:
  `https://external-api.kalshi.com/trade-api/v2`
- Market discovery:
  `GET /markets`
- Single-market metadata:
  `GET /markets/{ticker}`
- Kalshi documents cursor-based pagination for market discovery.

Official documentation:
- https://docs.kalshi.com/getting_started/quick_start_market_data
- https://docs.kalshi.com/api-reference/market/get-markets

## Atlas surfaces

### API

- `GET /api/prediction/status`
- `GET /api/prediction/markets`
- `GET /api/prediction/markets/{ticker}`

### UI

`/dashboard/future` now surfaces a bounded page of real public Kalshi markets when
the provider request succeeds.

## Normalized market contract

Atlas preserves provider values rather than inventing missing fields:

- ticker / event ticker
- market type
- title / subtitle
- status / result
- YES bid / ask / midpoint
- NO bid / ask
- last / previous price
- total and 24-hour volume
- open interest
- liquidity
- open / close / expiration / settlement timestamps
- settlement metadata
- primary / secondary rules

Fixed-point provider price/quantity fields remain decimal strings in the normalized
response so research surfaces do not silently lose provider precision.

## Safety boundary

Phase 1 has no:

- API key loading
- authenticated Kalshi request signing
- portfolio or balance access
- position access
- order creation
- order cancellation
- order amendment
- transfer/deposit/withdrawal access
- live execution
- automatic real-money execution

The API explicitly reports:

- `mode = RESEARCH_ONLY`
- `execution = DISABLED`
- `live_capital_allowed = false`
- `automatic_real_money_execution = false`

## Next prediction-market gates

1. Persisted research snapshot/archive
2. PAPER outcome ledger
3. Resolution/settlement verification
4. Calibration and evidence reporting
5. Prediction Hub dashboard
6. Only then consider whether a separate authenticated provider-read phase is useful

Real-money prediction-market execution is not part of this phase and requires a
separate explicit future gate.
