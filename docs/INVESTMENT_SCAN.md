# Investment research scan (Phase 5)

Opt-in pipeline on top of Phase 1–4. **No real brokerage. No ML. No alpha claim.**

`scan_version`: `atlas-scan-5.0`

```
Universe.json
    → price / fundamentals / valuation / incremental history
    → score (bars with session_date ≤ T only)
    → observation (qualified AND rejected)
    → alert state / paper plan (Phase 4)
```

Default **off**. Set `INVESTMENT_SCAN_ENABLED=true` or run
`scripts/investment_scan.py` once. The scanner is **not** inside the
Hyperliquid trading scan loop. A crash is logged; trading continues.

## Look-ahead protection (mandatory)

At timestamp **T**:

- Score, classification, thesis, alert, and allocation may use **only**
  information available at T.
- OHLCV bars with `session_date > T` are dropped before scoring.
- `outcomes.*` on the observation are **NULL** at evaluation time.
- Later prices are written by a **separate** process to
  `data/investment/outcomes.jsonl`. That file never overwrites
  `observations.jsonl`. Enrichment is never imported by `scoring.py`.

## Cadence (Yahoo-respectful)

| Kind | Typical refresh |
|---|---|
| Price | 15 min while `MARKET_OPEN`; skip live quotes when `MARKET_CLOSED` if a prior snapshot exists |
| Fundamentals | 24 h |
| Valuation | 24 h |
| History | incremental from last stored date; 24 h refresh |

Inter-symbol delay default 0.75 s. Retry with backoff on `RATE_LIMIT` /
`TIMEOUT`. Provider failure → `NO_ACTION` / `UNKNOWN`, never fake values.

Weekend = `MARKET_CLOSED` ≠ `SYSTEM_OFFLINE`. Last session prints may be
used, labeled STALE/FRESH by TTL. Paper fills wait for `MARKET_OPEN`.

## Observation record

Append-only `data/investment/observations.jsonl`. Every name, every scan:

- symbol, as_of, price, drawdown, components, thesis, evidence,
  classification, opportunity score, field quality (FRESH/STALE/MISSING/…),
  data-source status, blocking_reason (first), blocking_factors,
  provider failures, `outcomes` (all NULL at T), `look_ahead_protected: true`

Rejected / `NO_ACTION` rows are required. They answer:
“Why didn’t Atlas call this generational?”

## Universe

Operator file `data/investment/universe.json`. Missing file is bootstrapped
from the **example** (test/research names, not recommendations). Add/remove
symbols without code changes. Engine has no compiled ticker list.

## Discord

Existing investment DM layer. Title `ATLAS INVESTMENT — {CLASS}`.
No new slash commands. Not mixed with `/paper` stats.

## Not in this phase

Live brokerage, threshold optimization, ML, probability claims,
performance dashboards, mixed trading/investment stats.
