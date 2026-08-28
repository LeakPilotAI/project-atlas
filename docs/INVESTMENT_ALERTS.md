# Investment alerts + accumulation (Phase 4)

Builds on Phase 3 research records. **No real brokerage. No ML.**

`allocation_version`: `atlas-alloc-4.0`

## Alert state machine

Persisted per symbol in `data/investment/alert_state.json`.

| Transition | Alert? |
|---|---|
| first observation of WATCH+ | yes |
| WATCH → ACCUMULATION | yes |
| ACCUMULATION → ACCUMULATION (identical) | **no** (dedup) |
| ACCUMULATION → DEEP_VALUE | yes |
| ANY → THESIS_BROKEN | **yes, HIGH** |
| THESIS_BROKEN → THESIS_BROKEN | no |
| same class + material score/price/drawdown after cooldown | yes |

Cooldowns: WATCH 24h · ACCUMULATION 12h · DEEP_VALUE 6h · GENERATIONAL/THESIS_BROKEN 0.

Material: score ±8, price ±8%, drawdown ±5pp.

Generational alerts re-run the Phase 3 gate. Drawdown alone never fires GENERATIONAL.

## Allocation formula

Personalized plans require `provided` portfolio **and** `minimum_cash_reserve`.

```
usable = available_cash − reserve
headroom = max_position − existing_position
sector_headroom = sector_cap − sector_value   (if a sector cap is configured)

cap = min(usable, headroom, sector_headroom)
      × score_mult × evidence_mult × thesis_mult × vol_mult × risk_tolerance_mult
```

| score | × |
|---|---|
| ≥ 85 | 0.70 |
| ≥ 70 | 0.50 |
| ≥ 55 | 0.35 |
| else | 0 |

Evidence: HIGH 1.00 · MEDIUM 0.75 · else 0 (pause).
Thesis: STRONG 1.00 · INTACT 0.85 · UNDER_PRESSURE 0.40 · else 0.
Vol: <35% 1.00 · <50% 0.75 · else 0.50 (missing vol 0.80).
Risk tolerance: CONSERVATIVE 0.60 · MODERATE 0.85 · AGGRESSIVE 1.00 · UNKNOWN 0.70.

Never spends the reserve. Never exceeds max position or sector cap.
Price falling without score/thesis improvement **does not increase** the cap.

WATCH / NO_ACTION / missing portfolio → research-only, no plan.

## Limit prices

Not a fixed 5% grid. Spacing = `clip(0.75 × monthly vol, 3%, 12%)`.
If vol is missing, spacing from |drawdown|. Each tier is 0.5× / 1.5× / 2.75× / 4× that step below last price.

Shares = floor(allocation / limit) unless `allow_fractional_shares`.
Leftover cents stay in remaining reserve. Starting cash = spent + remaining (exact).

## Paper book

`data/investment/paper_account.json` + `paper_investment_ledger.jsonl`.
Simulates plan limits. Fills **only** while `MARKET_OPEN`. Weekend = `MARKET_CLOSED`, not `SYSTEM_OFFLINE`.
`execute_broker_order` still raises. SPY benchmark is tracked; **no alpha claim**.

## Discord

Investment DMs use a distinct body (`ATLAS INVESTMENT OPPORTUNITY`).
Transport reuses the existing bot. **No new slash commands. No /paper stats.**
