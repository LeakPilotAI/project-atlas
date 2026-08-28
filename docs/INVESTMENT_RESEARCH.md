# Investment research / scoring (Phase 3)

Research layer on top of `InvestmentSnapshot` + `history/{SYMBOL}.jsonl`.
No alerts, no allocation, no orders, no ML.

```
InvestmentSnapshot + OHLCV history
        ↓
drawdown / valuation context / fundamentals / thesis / risk / evidence
        ↓
ordinal Opportunity Score 0–100  (not a probability)
        ↓
classification + explainability
        ↓
append-only data/investment/opportunities.jsonl
```

`scoring_version`: `atlas-invest-3.0`

## Component weights

Missing components are **omitted** from the weighted mean (not scored as 0)
and they lower Evidence Quality. A light haircut applies if very few pillars
are present.

| Component | Weight | Notes |
|---|---|---|
| Valuation | 0.22 | One component; see correlation groups |
| Fundamentals (profitability) | 0.12 | Current snapshot only |
| Cash flow | 0.12 | FCF / OCF |
| Balance sheet | 0.10 | Cash vs debt vs mcap |
| Growth | 0.08 | Always omitted in Phase 3 (no statement history) |
| Drawdown context | 0.14 | Larger drawdown → higher *context* score, not a buy signal |
| Thesis integrity | 0.12 | From current snapshot; trends UNKNOWN |
| Risk | 0.06 | Higher = more acceptable |
| Evidence quality | 0.04 | Mainly a gate, small score weight |

## Correlation groups

Inside **Valuation**, related multiples are averaged *within* a group, then
groups are averaged. They do not each get a full opportunity-score weight.

| Group | Members |
|---|---|
| earnings_multiple | P/E, forward P/E, earnings yield |
| sales_multiple | P/S |
| book_multiple | P/B |
| cashflow_multiple | FCF yield, price/FCF, EV/EBITDA |

Revenue / earnings / EPS *growth* would be grouped if a history existed.
It does not.

## Current vs historical valuation

- **Current valuation** = today's multiples, scored with documented bands.
- **Historical valuation context** = UNKNOWN (Phase 2 does not store a PE/FCF
  time series). Percentiles are **not invented**.
- A low P/E is **not** automatically undervaluation.

## Drawdown method

- Current drawdown = `price / max(available closes) - 1`
- 52-week drawdown = same vs max of the last 252 bars (or the whole sample
  if shorter, labeled)
- Max drawdown = deepest running-peak drawdown in the sample
- Percentile = share of in-sample daily running-peak drawdowns that are
  *shallower* than current. **Sample-relative.** A unique shallow dip in a
  pure uptrend can rank high; classification still requires magnitude.
- Coverage is always labeled. 252 days is ~1 year, not a complete record.
- Percentile is UNKNOWN below 60 bars.

## Thesis logic (current snapshot)

Trends (deteriorating revenue, dilution over time) are UNKNOWN without a
fundamentals history.

| State | Rule of thumb |
|---|---|
| UNKNOWN | < 3 usable fundamental fields (typical ETF/index) |
| STRONG | profitable + cash generation ok + no high leverage, ≥5 fields |
| INTACT | no severe red flags |
| UNDER_PRESSURE | one or more current red flags |
| DAMAGED | earnings and FCF both not positive |
| BROKEN | earnings + FCF collapse **and** leverage or margin stress |

A falling price is **not** thesis damage.

## Evidence quality

HIGH / MEDIUM / LOW / INSUFFICIENT from: price usability, freshness,
fundamental field count, valuation field count, history length, conflicts,
provider failures. ETF/index evidence is capped at MEDIUM.

A high Opportunity Score with LOW / INSUFFICIENT evidence **cannot** become
GENERATIONAL OPPORTUNITY or DEEP VALUE.

## Classification

Order: THESIS BROKEN → generational gate → DEEP VALUE → ACCUMULATION → WATCH → NO ACTION.

**Generational gate (all required):**

- Thesis STRONG or INTACT
- Evidence HIGH or MEDIUM
- Drawdown ≤ −45% from highest available
- In-sample drawdown percentile ≥ 85 (UNKNOWN percentile → fail)
- ≥ 252 bars
- Valuation component ≥ 70
- Fundamentals component ≥ 70
- Balance sheet ≥ 60 if present
- Cash flow ≥ 60 if present
- Risk ≥ 50 if present
- Opportunity score ≥ 75
- Three independent pillars: large drawdown + attractive valuation + intact fundamentals

Drawdown alone never passes. False negatives preferred.

**DEEP VALUE:** thesis intact/strong, evidence HIGH/MEDIUM, valuation ≥ 75,
drawdown ≤ −20%, score ≥ 65, fundamentals ≥ 60.

**ACCUMULATION:** thesis intact/strong, evidence not insufficient, drawdown
≤ −15%, score ≥ 55, fundamentals ≥ 55 if present.

**WATCH:** not damaged/broken, evidence not insufficient, score ≥ 40.

## Storage

Append-only `backend/data/investment/opportunities.jsonl`. Each row keeps
`scoring_version`, timestamp, price, drawdown, components, thesis, evidence,
classification, explainability, and the input snapshot.

## Not in this phase

Discord investment alerts, allocation, limit ladders, paper investment
execution, backtests, ML.
