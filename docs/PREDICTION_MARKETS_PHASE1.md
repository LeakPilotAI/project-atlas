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


## Permanent single-market policy

Atlas prediction-market research now has a permanent provider-independent guardrail:

- single market only
- maximum one open prediction position at a time
- combos banned
- parlays banned
- multivariate-event markets banned
- stacking / pyramiding banned
- pre-event entries only
- mandatory exit before the event starts
- no holding through event start
- no holding to settlement
- live execution disabled

Kalshi discovery always sends `mve_filter=exclude`, and Atlas independently rejects
rows that contain `mve_collection_ticker` or non-empty `mve_selected_legs`. The
second guard remains in place even if a provider-side filter changes or regresses.

## Planned paper strategy: pre-event repricing

The next PAPER phase will test a pre-event repricing strategy, not an outcome-settlement
strategy. Atlas will estimate the executable price available before event start and will
only simulate an entry when the expected pre-event exit bid exceeds the executable entry
ask by enough to cover spread, fees, modeled slippage and the required research margin.

The paper engine must use executable orderbook prices and available size; it must never
credit a fill from midpoint-only or chart-only movement.


## Phase 1.1 — Executable depth + pre-event price history

Atlas now reads two additional public Kalshi market-data surfaces for realistic PAPER
research:

- GET /api/prediction/markets/{ticker}/orderbook?depth=N
- GET /api/prediction/markets/{ticker}/candlesticks

Provider basis:

- Kalshi market orderbook:
  GET /markets/{ticker}/orderbook
- Kalshi market candlesticks:
  GET /series/{series_ticker}/markets/{ticker}/candlesticks

### Orderbook handling

Kalshi returns YES and NO bids only. Atlas therefore derives executable asks from the
opposite-side bids using the binary-market complement relation:

- YES ask = 1.0000 - best NO bid
- NO ask = 1.0000 - best YES bid

The corresponding provider quantity is preserved at each derived ask level. Atlas sorts
bids best-first and asks cheapest-first, and reports the executable spread for each side.

Every orderbook read first passes through Atlas's single-market detail check, so a
multivariate/combo market is blocked before its depth can enter PAPER research.

Orderbook depth is bounded to 0..100 provider levels.

### Candlestick handling

Supported intervals match the public provider contract:

- 1 minute
- 60 minutes
- 1440 minutes

Atlas bounds any one request to at most 1,000 requested periods. Returned candles retain:

- YES bid OHLC
- YES ask OHLC
- trade/price OHLC
- mean / previous / min / max price
- fixed-point volume
- fixed-point open interest

The normalized market timing contract also now retains occurrence_datetime so the
future PAPER engine can enforce the mandatory pre-event flat deadline.

### PAPER realism contract

These reads are data acquisition only. They do not place orders.

The planned PAPER engine must use:

- executable ask + available size for entry
- executable bid + available size for exit
- actual spread
- modeled fees/slippage
- pre-event timing

It may not credit midpoint-only or chart-touch-only fills.


### Automatic series resolution

Callers do not need to know Kalshi's series ticker in advance.

When series_ticker is omitted from the Atlas candlestick route, Atlas:

1. loads the permitted single market,
2. reads its event_ticker,
3. calls the public Kalshi GET /events/{event_ticker} endpoint,
4. reads event.series_ticker,
5. requests the market candlesticks from that resolved series.

This keeps the browser/PAPER layer market-ticker driven while preserving the provider's
required series path parameter. The response records series_resolution as CALLER or
EVENT_LOOKUP.


## Phase 1.2 — Prediction PAPER repricing engine

Atlas now has an isolated append-only prediction PAPER engine. It is separate from
the Hyperliquid PAPER journal and does not use authenticated Kalshi account or order
surfaces.

### PAPER storage

- backend/data/prediction/paper_candidates.jsonl
- backend/data/prediction/paper_trades.jsonl

### PAPER API

- GET /api/prediction/paper/status
- POST /api/prediction/paper/evaluate/{ticker}
- POST /api/prediction/paper/open/{ticker}
- POST /api/prediction/paper/close

These endpoints mutate Atlas PAPER evidence only. They do not create, cancel, amend,
or query live Kalshi orders or positions.

### Strategy model

Version:
- prediction-paper-reprice-v1

Initial scorer:
- PRE_EVENT_RECENT_RECLAIM_V1

The scorer is deliberately conservative. It does not predict final settlement probability.
Its projected pre-event exit is the highest recently observed executable bid from the
selected side's recent quote history.

Candidate inputs include:

- single-market policy status
- occurrence_datetime
- time remaining to the mandatory flat deadline
- executable entry depth
- current executable spread
- 24h volume
- open interest
- recent bid/ask quote history
- recent quote instability
- recent executable reclaim level
- estimated entry/exit fees
- estimated net edge per contract

Default rejection conditions include:

- combo / multivariate market
- missing occurrence time
- too close to event start
- mandatory flat window reached
- insufficient executable depth
- missing executable quote
- spread wider than $0.08
- 24h volume below 20 contracts
- open interest below 20 contracts
- fewer than 5 usable quote-history bars
- quote jump greater than $0.20
- no recent reclaim edge
- net PAPER edge below $0.02 per contract after estimated fees

These defaults are PAPER research settings, not live trading authorization.

### Fill realism

PAPER entry:
- BUY the selected YES/NO side
- consume real ask depth cheapest-first
- require complete fill
- store level-by-level quantity and price
- store VWAP
- store depth slippage versus best ask

PAPER exit:
- SELL the same side
- consume real bid depth best-first
- require complete fill
- store VWAP and level-by-level fill evidence

No midpoint fill, chart-touch fill, hidden liquidity assumption, stacking, averaging down,
or multi-position prediction exposure is permitted.

### Fees

The PAPER engine currently uses a conservative general taker fee estimator based on the
published Kalshi prediction-market formula:

fee = round up to the next cent of 0.07 * contracts * price * (1 - price)

Atlas computes the estimate per consumed depth level and sums the result. Kalshi can use
different schedules for some products, so this PAPER fee model is explicitly versioned
and is not treated as an exact promise of a future live fee.

Fee model version:
- kalshi-general-taker-conservative-v1

### Position policy

- maximum one open prediction PAPER position
- one side only
- no stacking / pyramiding
- no combos / parlays / multivariate markets
- mandatory exit before event start
- no settlement holding
- counts_for_live = false

### UI status

Prediction PAPER backend functionality now exists, but the dedicated Prediction Paper
Trades frontend remains intentionally disabled / COMING SOON until the backend validation
gate is complete.
