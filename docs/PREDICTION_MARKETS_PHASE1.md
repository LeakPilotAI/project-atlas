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


## Phase 1.3 — Bounded scanner + mandatory PAPER auto-flat

Implemented on 2026-10-02 after the first live repricing evaluation gate.

### Automatic bounded candidate scanner

Atlas now owns a background Prediction PAPER scanner with these hard bounds:

- discovery limit: 40 public single markets per cycle
- expensive evaluation concurrency: 4 markets
- orderbook depth: 20
- quote-history window: 180 minutes
- default PAPER quantity: 10 contracts
- scanner interval: 60 seconds
- unattended PAPER position opening: disabled

The scanner performs cheap policy/timing/activity rejection before orderbook and
candlestick requests. Surviving markets reuse one orderbook/history acquisition and are
then scored independently for YES and NO through the existing
PRE_EVENT_RECENT_RECLAIM_V1 evaluator. Requested-size executable depth VWAP remains the
authoritative entry price.

Every prefilter rejection, full evaluation, and contained evaluation error is persisted
to the append-only Prediction PAPER candidate journal with explicit reason codes.
A failed/timeout market does not abort the rest of the bounded cycle.

Live public-data acceptance found a provider semantic detail: Kalshi's status=open
discovery request currently returns market rows whose status field is active. Atlas
therefore treats provider status open and active as the same discovery-open state. This
only fixes provider status normalization; no strategy threshold was weakened.

Live scanner acceptance evidence at the corrected gate:

- 40 public open markets discovered
- 39 rejected by cheap prefilter
- 1 market reached full expensive evaluation
- YES evaluated independently: 1
- NO evaluated independently: 1
- scanner errors: 0
- scanner timeouts: 0
- eligible candidates: 0
- PAPER positions opened: 0
- the fully evaluated market was rejected for QUOTE_INSTABILITY and
  NO_RECENT_RECLAIM_EDGE

Zero eligible candidates is a valid scanner outcome.

### Mandatory Prediction PAPER auto-flat worker

A separate runtime worker now monitors only the isolated Prediction PAPER journal.
It does not touch Hyperliquid PAPER state or any authenticated Kalshi/account/order
surface.

At the mandatory flat deadline it attempts one complete PAPER exit through the existing
canonical depth-aware close model:

- sell the held YES/NO side into real executable bid depth
- require the full position quantity
- walk multiple bid levels when necessary
- preserve exit VWAP, fill levels, depth slippage, and estimated fee evidence
- never use midpoint fills, hidden liquidity, partial-fill success, or settlement as a
  manufactured exit

If executable depth is missing/insufficient or the public provider fails, Atlas preserves
the position as open, records an explicit auto-flat blocked safety event, and retries on
the bounded worker cadence while still pre-event. If event start is reached without a
valid exit, Atlas records AUTO_FLAT_DEADLINE_VIOLATION and still does not manufacture a
settlement fill.

The worker is idempotent around already/manual-closed positions and shares the
PredictionPaperJournal as the authoritative position owner.

### Runtime / safety status

Prediction PAPER automation status is exposed through:

- GET /api/prediction/paper/status
- GET /api/prediction/paper/automation/status

The status includes scanner counts, recent errors/timeouts, top eligible candidates,
auto-flat safety state, and configured bounds.

The following remain hard-disabled:

- unattended_paper_open_enabled = false
- automatic_paper_position_opening = false
- live_execution = false
- live_capital_allowed = false
- automatic_real_money_execution = false

Unattended PAPER opening remains blocked until the supported desktop runtime gate is
completed and a genuine eligible PAPER position provides a safe opportunity to validate
the auto-flat worker end-to-end. Filters must not be weakened and rejected candidates
must not be force-opened just to manufacture that evidence.

### Regression evidence

The deterministic Atlas CI gate includes the Prediction automation tests plus the
existing Prediction/Future Overview/Dashboard/frontend-freeze regressions. The corrected
gate reached:

- 96 passed in the existing PAPER/manual-perp suite
- 47 passed in the Prediction/automation/frontend gate
- 0 failures

The live public scanner smoke remains available as:

- python scripts/prediction_paper_live_smoke.py

It is intentionally diagnostic-only rather than part of every CI run so external
provider availability cannot make deterministic repository regression CI flaky.
