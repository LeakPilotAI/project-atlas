# Project Atlas — Closed Historical Experiment

Closed: 2026-09-17
Status: FAILED_NEGATIVE

## Scope

This record closes the frozen Project Atlas historical experiment that used DEVELOPMENT window `dev-2024-h2` and untouched HOLDOUT window `holdout-2025-h2`.

The completed experiment is immutable evidence. Its DEVELOPMENT/HOLDOUT datasets, thresholds, run identities, summaries, and evidence freezes must not be relabeled or retuned in place. Any future strategy research must use a separately identified research cycle and a new untouched holdout.

## Frozen configuration

- minimum open interest: 75,000 USD
- minimum rolling 24h volume: 150,000 USD
- RSI long maximum: 28
- RSI short minimum: 72
- minimum extension: 1.4%
- maximum extension: 3.5%
- minimum R:R: 1.8
- extension lookback: 20 bars
- RSI period: 14
- HTF alignment: enabled

## DEVELOPMENT evidence

- trades: 659
- total R: -117.21753020091131
- expectancy R/trade: -0.17787182124569242
- result: FAILED_NEGATIVE

## Untouched HOLDOUT evidence

Independent source audit: GREEN
Source audit id: `951dbc0f46516bcf97eb`

Aggregate:
- trades: 546
- total R: -26.72350715657114
- expectancy R/trade: -0.048944152301412344
- result: FAILED_NEGATIVE

Per symbol:
- BTC: 67 trades; -8.79051149035033R; expectancy -0.13120166403507955R; PF 0.8151646776263058; run `36a8b36242e9cc1c708c`
- ETH: 192 trades; -21.54704556954468R; expectancy -0.11222419567471187R; PF 0.8401063289638052; run `bc9c8c61cf356cf09fa7`
- SOL: 287 trades; +3.614049903323867R; expectancy +0.012592508373950756R; PF 1.0192535094387052; run `5d83c5d3284696739eb2`

Evidence freeze SHA-256 of HOLDOUT summary:
`ee6b28c5042414e70534f04e120ae439b8e765dc156f9b20e1fa2c0873149d72`

## Closure controls

- `stable_positive_edge_established=false`
- `threshold_retuning_allowed=false`
- `same_window_optimization_allowed=false`
- `next_cycle_must_be_isolated=true`
- `production_strategy_modified=false`
- `live_capital_allowed=false`
- `automatic_real_money_execution=false`

## Interpretation

The research pipeline completed its intended job: it preserved point-in-time inputs, froze DEVELOPMENT decisions before HOLDOUT evaluation, independently audited HOLDOUT sources, evaluated the untouched HOLDOUT under the exact frozen configuration, and preserved the resulting negative evidence without retuning.

This experiment does not establish a stable positive edge. It is closed and must remain available as failed-experiment evidence.

PAPER/SHADOW operation is a separate engineering/evidence checkpoint and must not be used to rewrite this historical result. Live capital remains locked.
