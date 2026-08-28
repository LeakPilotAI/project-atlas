# Investment data architecture (Phase 2)

Data foundation only. No scoring, alerts, or allocation.

## Flow

```
universe.json  →  providers (Price / Fundamental / Valuation)
                         ↓
              validate + freshness
                         ↓
         data/investment/history/{SYMBOL}.jsonl
                         ↓
                   InvestmentSnapshot
                         ↓
                 quality report text
```

Trading journals (`paper_journal.jsonl`, shadow files) are never written.

## Providers

All Yahoo I/O goes through `YFinanceClient`. Do not import `yfinance` elsewhere
in this package except that file.

| Interface | Implementation | Notes |
|---|---|---|
| `PriceDataProvider` | `YahooPriceProvider` | latest price + daily OHLCV (date range supported) |
| `FundamentalDataProvider` | `YahooFundamentalProvider` | revenue, earnings, EPS, FCF, OCF, margins, debt, cash, shares, mcap |
| `ValuationDataProvider` | `YahooValuationProvider` | PE, forward PE, P/S, P/B, EV/EBITDA; yields only if both inputs exist |
| News / macro | `NullProvider` | still MISSING |

Provider failures become `ProviderFailure` records (`TIMEOUT`, `RATE_LIMIT`,
`MISSING_TICKER`, `EMPTY`, `PROVIDER_ERROR`, `DEPENDENCY`). Atlas does not
crash. No fallback financial values are invented.

## Universe

Configurable JSON. Engine has **no compiled ticker list**.

- Operator file: `backend/data/investment/universe.json`
- Tracked template: `backend/app/investment/universe.example.json`
- Missing / empty file → empty universe

Each entry: `symbol`, `name`, `asset_type`, `exchange`, `currency`, `sector`,
`industry`, `active`.

`asset_type` ∈ `STOCK` · `ETF` · `INDEX` · `SECTOR_ETF` · `OTHER` · `UNKNOWN`

The example mix is representative (broad ETFs, sector ETFs, an index, a few
stocks). It is not a recommendation list and does not bake mega-cap names into
the engine.

## Normalized models

`MeasuredValue` is the unit of research data:

| Field | Meaning |
|---|---|
| `value` | number or `None` |
| `source` | provider name (`yfinance`, `yfinance+derived`, `null`, `none`) |
| `retrieved_at` | when Atlas fetched it |
| `effective_timestamp` | as-of time of the observation |
| `quality` | `FRESH` / `STALE` / `MISSING` / `CONFLICTING` / `UNKNOWN` |
| `notes` | flags, derivation formula, or failure detail |

`timestamp` is an alias of `effective_timestamp` (Phase 1 compatibility).

Missing data: `quality=MISSING`, `value=None`. Never `0`, never estimated.

## Freshness rules (independent TTLs)

| Kind | Fresh window |
|---|---|
| `price` | 15 minutes |
| `daily_bar` | 36 hours |
| `fundamental` | 45 days |
| `valuation` | 7 days |
| `macro` | 7 days |

Override via `FreshnessRules`. Future-dated timestamps → `UNKNOWN`, not `FRESH`.
Yahoo `info` fundamentals/valuation use retrieve time as effective time because
the payload does not include a statement date.

## Data-quality states

`FRESH` · `STALE` · `MISSING` · `CONFLICTING` · `UNKNOWN`

- Impossible OHLC → `CONFLICTING` (stored, **not** repaired)
- Suspicious zeros / inconsistent share counts → flagged on the row
- Missing field → `MISSING` with `value=None`

## Historical storage

`backend/data/investment/history/{SYMBOL}.jsonl`

Fields: `date`, `open`, `high`, `low`, `close`, `volume`, `adjusted_close`,
`source`, `retrieved_at`, `effective_timestamp`, `quality`, `issues`.

Key = session date. Duplicates skipped. Validation issues stored on the row.
Default history window for ingest is 5 years of daily bars.

Snapshots append to `backend/data/investment/snapshots.jsonl`.

## Investment snapshot

Per asset:

- Asset identity (from universe)
- Price (`MeasuredValue`)
- Latest daily bar
- Fundamentals map
- Valuation map
- Failures
- Data timestamp / retrieved_at
- History rows stored this run

This is the input to later scoring. Phase 2 does **not** score it.

## Data-quality report

```
Assets requested: N
Price:        Fresh / Stale / Missing / Conflicting / Unknown
Fundamentals: Fresh / Stale / Missing / Conflicting / Unknown
Valuation:    Fresh / Stale / Missing / Conflicting / Unknown
Provider errors: N
```

## Failure behavior

| Condition | Result |
|---|---|
| timeout | `TIMEOUT`, retryable, values MISSING |
| rate limit | `RATE_LIMIT`, retryable, values MISSING |
| missing ticker | `MISSING_TICKER`, not retryable, values MISSING |
| empty payload | `EMPTY`, values MISSING (price may use last **real** daily close, labeled) |
| provider / network error | `PROVIDER_ERROR`, retryable, values MISSING |
| yfinance not installed | `DEPENDENCY`, values MISSING |

The trading API is not started from this package. Ingest is opt-in
(`InvestmentIngest`). A live probe is `scripts/investment_live_probe.py`.

## Known Yahoo limits

- `info` fields vary by ETF vs stock vs index; many ETF/index fundamentals will be MISSING.
- Datacenter IPs often get Yahoo crumb `401` / `429` on `Ticker.info`. Atlas rejects the
  `{trailingPegRatio: None}` stub and falls back to `fast_info` (price, market cap, shares)
  plus daily history. Income-statement fields stay MISSING rather than invented.
- Intraday last price can lag; daily bars are EOD.
- No paid fundamentals feed in Phase 2. Statement dates are not on `info` / `fast_info`.
- Derived yields (`fcf_yield`, `earnings_yield`, `price_to_fcf`) are computed
  only when both inputs exist and the denominator is non-zero.
