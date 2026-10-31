# R7E46P whole-artifact Ruff inventory

Current: 3998; preserved O baseline: 4005; committed HEAD: 3982. P introduced 0, resolved 7.

These review categories are audit labels, not official Ruff severity or proof of a vulnerability. Inherited findings remain open; no blanket waiver. Six pre-P cash-calendar style findings remain untouched pending scope review.

| File | Count | Rules | Review categories |
|---|---:|---|---|
| backend/app/adapters/base.py | 1 | F401:1 | correctness_review |
| backend/app/adapters/hyperliquid.py | 8 | BLE001:2, UP045:6 | policy_review, style_maintainability |
| backend/app/adapters/hyperliquid_cache.py | 16 | B023:3, BLE001:5, PLW0602:1, S110:1, UP006:5, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/adapters/registry.py | 6 | BLE001:3, F401:2, UP045:1 | correctness_review, policy_review, style_maintainability |
| backend/app/alerts/chart_generator.py | 14 | BLE001:1, C408:1, SIM210:1, UP006:6, UP035:1, UP045:4 | correctness_review, policy_review, style_maintainability |
| backend/app/alerts/discord.py | 11 | BLE001:3, G201:1, UP006:4, UP035:2, UP045:1 | policy_review, style_maintainability |
| backend/app/alerts/dispatcher.py | 3 | BLE001:2, UP045:1 | policy_review, style_maintainability |
| backend/app/analytics/__init__.py | 2 | I001:1, RUF022:1 | style_maintainability |
| backend/app/analytics/anomaly.py | 7 | BLE001:1, UP045:6 | policy_review, style_maintainability |
| backend/app/analytics/atr_breakout.py | 18 | UP035:1, UP045:17 | style_maintainability |
| backend/app/analytics/bollinger_squeeze.py | 5 | I001:1, UP035:1, UP045:3 | style_maintainability |
| backend/app/analytics/decision_engine.py | 14 | F841:1, UP045:13 | correctness_review, style_maintainability |
| backend/app/analytics/events.py | 9 | I001:1, UP006:2, UP017:1, UP035:1, UP045:4 | style_maintainability |
| backend/app/analytics/indicators.py | 19 | UP035:1, UP045:18 | style_maintainability |
| backend/app/analytics/performance.py | 2 | F401:1, UP017:1 | correctness_review, style_maintainability |
| backend/app/analytics/profiles.py | 2 | UP006:1, UP035:1 | style_maintainability |
| backend/app/analytics/regime.py | 11 | UP035:1, UP045:10 | style_maintainability |
| backend/app/analytics/risk.py | 1 | UP045:1 | style_maintainability |
| backend/app/analytics/whale.py | 10 | BLE001:2, I001:1, UP006:2, UP017:2, UP035:1, UP045:2 | policy_review, style_maintainability |
| backend/app/api/archive.py | 46 | BLE001:8, FURB162:4, I001:1, S112:4, UP006:12, UP017:16, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/api/command_center.py | 12 | BLE001:1, S110:1, UP006:6, UP035:1, UP041:1, UP045:2 | correctness_review, policy_review, style_maintainability |
| backend/app/api/crypto_quality_dips_research.py | 1 | I001:1 | style_maintainability |
| backend/app/api/diagnostics.py | 20 | BLE001:1, F401:1, I001:2, S110:1, UP006:10, UP017:1, UP035:1, UP041:1, UP045:2 | correctness_review, policy_review, style_maintainability |
| backend/app/api/investment_board.py | 11 | BLE001:1, F401:1, I001:2, UP006:6, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/api/live.py | 30 | BLE001:8, I001:2, UP006:16, UP017:1, UP035:2, UP045:1 | policy_review, style_maintainability |
| backend/app/api/perp_manual.py | 12 | BLE001:1, I001:1, UP006:9, UP035:1 | policy_review, style_maintainability |
| backend/app/api/prediction.py | 17 | F401:1, FURB157:1, I001:1, UP006:12, UP017:1, UP035:1 | correctness_review, style_maintainability |
| backend/app/api/prospective_research.py | 2 | I001:2 | style_maintainability |
| backend/app/api/runtime_diagnostics.py | 5 | BLE001:1, UP006:3, UP035:1 | policy_review, style_maintainability |
| backend/app/api/validation.py | 44 | BLE001:33, F841:1, I001:6, UP006:3, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/api/validation_proof.py | 2 | UP006:1, UP035:1 | style_maintainability |
| backend/app/backtest/__init__.py | 1 | RUF022:1 | style_maintainability |
| backend/app/backtest/binance_public_acquire.py | 5 | BLE001:2, FURB162:1, UP017:2 | correctness_review, policy_review, style_maintainability |
| backend/app/backtest/binance_public_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/binance_public_htf_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/binance_public_htf_context.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/binance_public_inspect.py | 4 | I001:1, RUF007:2, UP017:1 | style_maintainability |
| backend/app/backtest/binance_public_metrics.py | 6 | BLE001:2, FURB162:1, I001:1, UP017:2 | correctness_review, policy_review, style_maintainability |
| backend/app/backtest/binance_public_metrics_batch.py | 4 | FURB162:1, I001:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/backtest/binance_public_metrics_inspect.py | 7 | FURB162:1, I001:1, RUF007:2, UP017:3 | correctness_review, style_maintainability |
| backend/app/backtest/binance_public_metrics_normalize.py | 6 | FURB162:1, I001:1, RUF007:1, UP017:3 | correctness_review, style_maintainability |
| backend/app/backtest/binance_public_normalize.py | 3 | I001:1, UP017:2 | style_maintainability |
| backend/app/backtest/binance_public_rolling_volume.py | 4 | FURB162:1, I001:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/backtest/binance_public_rolling_volume_batch.py | 3 | FURB162:1, I001:1, UP017:1 | correctness_review, style_maintainability |
| backend/app/backtest/binance_public_rolling_volume_probe.py | 4 | F841:1, FURB162:1, I001:1, UP017:1 | correctness_review, style_maintainability |
| backend/app/backtest/canonical_assemble.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/canonical_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/cli.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/development_decision_freeze.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/engine.py | 18 | I001:1, UP006:13, UP035:1, UP045:3 | style_maintainability |
| backend/app/backtest/funding_pit_merge.py | 5 | FURB162:1, I001:1, PERF402:1, RUF007:1, UP017:1 | correctness_review, style_maintainability |
| backend/app/backtest/funding_pit_merge_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/historical.py | 3 | B008:1, I001:1, UP035:1 | correctness_review, style_maintainability |
| backend/app/backtest/holdout_build_plan.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/holdout_candle_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/holdout_canonical_audit.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/holdout_evaluation.py | 2 | I001:1, TRY004:1 | style_maintainability |
| backend/app/backtest/holdout_evidence_freeze.py | 2 | I001:1, TRY004:1 | style_maintainability |
| backend/app/backtest/holdout_funding_merge_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/holdout_oi_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/holdout_prepare_plan.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/holdout_volume_htf_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/htf_context.py | 5 | FURB162:1, I001:1, UP017:2, UP035:1 | correctness_review, style_maintainability |
| backend/app/backtest/hyperliquid_acquire.py | 6 | FURB162:1, I001:1, TRY004:2, UP017:2 | correctness_review, style_maintainability |
| backend/app/backtest/hyperliquid_archive.py | 4 | FURB162:1, I001:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/backtest/hyperliquid_archive_inspect.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/hyperliquid_funding_batch.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/hyperliquid_funding_history.py | 6 | FURB162:1, I001:1, TRY004:2, UP017:2 | correctness_review, style_maintainability |
| backend/app/backtest/hyperliquid_import.py | 3 | I001:1, UP017:1, UP035:1 | style_maintainability |
| backend/app/backtest/import_cli.py | 2 | I001:1, TRY004:1 | style_maintainability |
| backend/app/backtest/io.py | 2 | TRY004:1, UP035:1 | style_maintainability |
| backend/app/backtest/locked_development_baseline.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/locked_development_baseline_run.py | 2 | B008:1, I001:1 | correctness_review, style_maintainability |
| backend/app/backtest/manifest.py | 2 | I001:1, TRY004:1 | style_maintainability |
| backend/app/backtest/perp_micro_baseline.py | 3 | I001:1, UP035:1, UP037:1 | style_maintainability |
| backend/app/backtest/provider_normalize.py | 7 | F401:1, FURB162:1, I001:1, TRY004:1, UP017:2, UP035:1 | correctness_review, style_maintainability |
| backend/app/backtest/representative_windows.py | 1 | I001:1 | style_maintainability |
| backend/app/backtest/source_audit.py | 3 | BLE001:1, I001:1, UP035:1 | policy_review, style_maintainability |
| backend/app/backtest/source_plan.py | 2 | I001:1, UP035:1 | style_maintainability |
| backend/app/core/config.py | 15 | BLE001:1, S110:1, UP006:12, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/core/market_freshness.py | 2 | UP017:2 | style_maintainability |
| backend/app/core/redis.py | 6 | BLE001:3, F401:1, PLW0602:1, S110:1 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/__init__.py | 1 | RUF022:1 | style_maintainability |
| backend/app/investment/accumulation_ladder.py | 4 | BLE001:1, PLR0124:1, UP017:1, UP035:1 | policy_review, style_maintainability |
| backend/app/investment/adaptive_valuation.py | 3 | I001:1, UP017:2 | style_maintainability |
| backend/app/investment/alerts.py | 28 | BLE001:2, F401:2, FURB162:1, I001:1, SIM102:3, UP006:1, UP017:1, UP035:2, UP045:15 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/allocation.py | 45 | BLE001:3, F401:1, FURB157:19, S110:1, S112:1, UP006:10, UP017:2, UP035:2, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/bars.py | 14 | UP006:3, UP035:2, UP045:9 | style_maintainability |
| backend/app/investment/benchmark_research.py | 1 | RUF007:1 | style_maintainability |
| backend/app/investment/blocking.py | 7 | UP006:5, UP035:2 | style_maintainability |
| backend/app/investment/board.py | 1 | UP035:1 | style_maintainability |
| backend/app/investment/buy_prep.py | 29 | SIM103:1, UP006:10, UP035:2, UP045:16 | correctness_review, style_maintainability |
| backend/app/investment/cause.py | 28 | BLE001:3, FURB162:1, UP006:13, UP017:3, UP035:2, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/completeness.py | 13 | UP006:7, UP035:3, UP045:3 | style_maintainability |
| backend/app/investment/daily_research_plan.py | 4 | F401:1, I001:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/investment/dataset.py | 12 | F401:1, UP006:6, UP035:2, UP045:3 | correctness_review, style_maintainability |
| backend/app/investment/diagnostics.py | 17 | BLE001:1, F401:3, F841:1, UP006:5, UP035:2, UP045:5 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/drawdown.py | 31 | PLR1730:2, UP006:11, UP035:3, UP045:15 | style_maintainability |
| backend/app/investment/engine.py | 15 | F401:3, UP017:1, UP035:2, UP045:9 | correctness_review, style_maintainability |
| backend/app/investment/etf_local_research.py | 2 | I001:1, UP017:1 | style_maintainability |
| backend/app/investment/evaluation.py | 11 | F401:1, I001:1, UP006:4, UP035:4, UP045:1 | correctness_review, style_maintainability |
| backend/app/investment/evidence_lifecycle.py | 3 | FURB162:1, I001:1, UP017:1 | correctness_review, style_maintainability |
| backend/app/investment/freshness.py | 9 | UP006:2, UP017:2, UP035:1, UP045:4 | style_maintainability |
| backend/app/investment/freshness_proof.py | 2 | I001:1, UP035:1 | style_maintainability |
| backend/app/investment/high_conviction.py | 8 | UP006:5, UP035:1, UP045:2 | style_maintainability |
| backend/app/investment/historical_validation.py | 6 | BLE001:1, FURB162:1, UP017:3, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/history.py | 18 | BLE001:3, FURB162:1, S112:2, UP006:7, UP035:4, UP045:1 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/ingest.py | 15 | BLE001:4, UP006:3, UP035:1, UP045:7 | policy_review, style_maintainability |
| backend/app/investment/integrity.py | 14 | BLE001:1, FURB162:1, UP006:4, UP017:2, UP035:2, UP045:4 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/intelligence.py | 5 | UP006:1, UP035:2, UP045:2 | style_maintainability |
| backend/app/investment/latest_index.py | 1 | I001:1 | style_maintainability |
| backend/app/investment/lookahead.py | 6 | UP006:2, UP017:2, UP035:2 | style_maintainability |
| backend/app/investment/market_hours.py | 10 | UP017:5, UP045:5 | style_maintainability |
| backend/app/investment/models.py | 62 | UP006:23, UP017:1, UP035:2, UP037:2, UP045:34 | style_maintainability |
| backend/app/investment/monitor.py | 9 | F401:1, UP006:2, UP035:2, UP045:4 | correctness_review, style_maintainability |
| backend/app/investment/move_store.py | 8 | F401:1, UP006:3, UP017:1, UP035:1, UP045:2 | correctness_review, style_maintainability |
| backend/app/investment/moves.py | 57 | RUF046:1, SIM102:2, SIM103:1, UP006:7, UP035:3, UP045:43 | correctness_review, style_maintainability |
| backend/app/investment/notify.py | 12 | BLE001:2, S112:1, UP006:2, UP035:1, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/outcomes.py | 28 | BLE001:2, FURB162:1, S112:1, UP006:7, UP017:3, UP035:3, UP045:11 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/paper_book.py | 23 | BLE001:1, F401:1, PLR1730:1, UP006:8, UP017:1, UP035:2, UP037:1, UP045:8 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/policy_research.py | 4 | F401:3, I001:1 | correctness_review, style_maintainability |
| backend/app/investment/portfolio.py | 14 | BLE001:1, UP006:4, UP035:2, UP045:7 | policy_review, style_maintainability |
| backend/app/investment/prospective_evidence.py | 5 | FURB162:1, I001:1, SIM102:1, SIM117:1, UP017:1 | correctness_review, style_maintainability |
| backend/app/investment/prospective_outcomes.py | 2 | I001:1, UP017:1 | style_maintainability |
| backend/app/investment/prospective_report.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| backend/app/investment/provider_health.py | 14 | BLE001:1, F401:1, I001:1, UP006:2, UP017:1, UP035:1, UP037:1, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/providers.py | 3 | UP017:1, UP045:2 | style_maintainability |
| backend/app/investment/quality.py | 11 | UP006:7, UP035:2, UP045:2 | style_maintainability |
| backend/app/investment/quality_dip_quotes.py | 13 | BLE001:6, FURB162:1, PLR0124:1, UP017:4, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/quality_dips_crypto_evidence.py | 4 | FURB162:1, I001:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/investment/quality_dips_crypto_ingestion.py | 1 | I001:1 | style_maintainability |
| backend/app/investment/quality_dips_crypto_store.py | 1 | I001:1 | style_maintainability |
| backend/app/investment/quality_dips_paper.py | 39 | BLE001:1, FURB162:2, I001:1, SIM117:1, UP006:25, UP017:1, UP035:2, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/quality_dips_paper_exit_policy.py | 3 | UP006:2, UP035:1 | style_maintainability |
| backend/app/investment/quality_dips_paper_marking.py | 3 | UP006:1, UP035:1, UP045:1 | style_maintainability |
| backend/app/investment/quality_dips_paper_terminal.py | 11 | I001:1, UP006:7, UP035:2, UP045:1 | style_maintainability |
| backend/app/investment/quality_dips_research_envelope.py | 1 | I001:1 | style_maintainability |
| backend/app/investment/quality_dips_v2.py | 11 | I001:1, UP045:10 | style_maintainability |
| backend/app/investment/quality_dips_v2_alert_store.py | 13 | BLE001:1, UP006:7, UP017:1, UP035:1, UP045:3 | policy_review, style_maintainability |
| backend/app/investment/quality_dips_v2_alerts.py | 24 | BLE001:1, FURB162:1, I001:1, SIM102:1, UP006:8, UP017:3, UP035:1, UP045:8 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/quality_dips_v2_board.py | 2 | I001:1, UP035:1 | style_maintainability |
| backend/app/investment/quality_dips_v2_entries.py | 11 | UP006:5, UP017:1, UP035:1, UP045:4 | style_maintainability |
| backend/app/investment/quality_dips_v2_evidence.py | 15 | UP006:10, UP035:1, UP045:4 | style_maintainability |
| backend/app/investment/quality_dips_v2_freeze.py | 3 | F401:1, I001:1, UP035:1 | correctness_review, style_maintainability |
| backend/app/investment/quality_dips_v2_gate.py | 14 | BLE001:1, FURB162:1, UP006:2, UP017:5, UP035:1, UP045:4 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/quality_dips_v2_position_monitor.py | 9 | UP006:6, UP035:1, UP045:2 | style_maintainability |
| backend/app/investment/quality_dips_v2_runtime.py | 1 | PLR0124:1 | style_maintainability |
| backend/app/investment/quality_dips_v2_target_cache.py | 11 | BLE001:4, FURB162:1, PLR0124:1, S110:1, UP017:3, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/quality_dips_v2_validation.py | 8 | I001:1, UP035:1, UP045:6 | style_maintainability |
| backend/app/investment/quality_dips_v2_valuation.py | 7 | I001:1, UP035:1, UP045:5 | style_maintainability |
| backend/app/investment/quality_dips_v3.py | 7 | PLR0124:1, UP006:3, UP035:1, UP045:2 | style_maintainability |
| backend/app/investment/quality_dips_v3_alerts.py | 1 | UP017:1 | style_maintainability |
| backend/app/investment/quality_dips_v3_delivery.py | 3 | BLE001:1, I001:1, UP035:1 | policy_review, style_maintainability |
| backend/app/investment/quality_dips_v3_development.py | 2 | I001:1, UP035:1 | style_maintainability |
| backend/app/investment/quality_dips_v3_forward_readiness.py | 6 | BLE001:3, FURB162:1, S112:2 | correctness_review, policy_review |
| backend/app/investment/quality_dips_v3_forward_store.py | 1 | UP017:1 | style_maintainability |
| backend/app/investment/quality_dips_v3_pit_store.py | 2 | BLE001:1, S112:1 | correctness_review, policy_review |
| backend/app/investment/quality_dips_v3_state.py | 3 | BLE001:1, UP017:2 | policy_review, style_maintainability |
| backend/app/investment/quality_dips_v3_validation.py | 1 | UP035:1 | style_maintainability |
| backend/app/investment/quality_report.py | 3 | UP006:1, UP035:2 | style_maintainability |
| backend/app/investment/readiness.py | 14 | F401:1, RUF059:1, UP006:6, UP035:3, UP045:3 | correctness_review, style_maintainability |
| backend/app/investment/relative.py | 22 | UP006:3, UP035:3, UP045:16 | style_maintainability |
| backend/app/investment/research.py | 49 | RUF046:1, SIM114:1, UP006:28, UP035:4, UP045:15 | correctness_review, style_maintainability |
| backend/app/investment/research_math.py | 3 | FURB162:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/investment/research_models.py | 35 | UP006:20, UP017:1, UP035:2, UP045:12 | style_maintainability |
| backend/app/investment/research_store.py | 7 | BLE001:1, S112:1, UP006:2, UP035:1, UP045:2 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/review_levels.py | 14 | UP006:3, UP035:2, UP045:9 | style_maintainability |
| backend/app/investment/robinhood_discovery_research.py | 1 | BLE001:1 | policy_review |
| backend/app/investment/robinhood_equity_quotes.py | 9 | BLE001:3, FURB162:1, PLR0124:1, RUF100:1, UP017:1, UP041:2 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/robinhood_universe_discovery.py | 1 | RUF100:1 | style_maintainability |
| backend/app/investment/robinhood_universe_registry.py | 3 | BLE001:1, UP017:1, UP035:1 | policy_review, style_maintainability |
| backend/app/investment/safety.py | 4 | UP006:2, UP035:2 | style_maintainability |
| backend/app/investment/scan.py | 132 | BLE001:21, F401:2, F811:54, FURB162:2, I001:1, ISC004:1, S110:5, S112:2, UP006:12, UP017:2, UP035:3, UP045:27 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/scan_models.py | 21 | UP006:14, UP017:1, UP035:2, UP045:4 | style_maintainability |
| backend/app/investment/scan_settings.py | 2 | BLE001:1, UP037:1 | policy_review, style_maintainability |
| backend/app/investment/scan_store.py | 8 | BLE001:1, S112:1, UP006:2, UP035:1, UP045:3 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/scoring.py | 44 | F401:1, RUF046:1, UP006:26, UP035:4, UP045:12 | correctness_review, style_maintainability |
| backend/app/investment/snapshot.py | 30 | BLE001:2, FURB162:1, UP006:13, UP035:2, UP045:12 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/tape.py | 17 | UP006:12, UP017:1, UP035:2, UP045:2 | style_maintainability |
| backend/app/investment/thesis_trend.py | 12 | UP006:6, UP035:3, UP045:3 | style_maintainability |
| backend/app/investment/universe.py | 22 | BLE001:2, UP006:12, UP035:3, UP045:5 | policy_review, style_maintainability |
| backend/app/investment/validate.py | 16 | BLE001:1, UP006:10, UP035:4, UP045:1 | policy_review, style_maintainability |
| backend/app/investment/yahoo_fundamentals.py | 18 | BLE001:2, F841:1, I001:1, UP006:6, UP035:2, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/investment/yahoo_price.py | 17 | BLE001:3, UP006:3, UP017:3, UP035:1, UP045:7 | policy_review, style_maintainability |
| backend/app/investment/yfinance_client.py | 14 | BLE001:2, S110:1, UP006:5, UP017:1, UP035:1, UP041:2, UP045:2 | correctness_review, policy_review, style_maintainability |
| backend/app/main.py | 32 | BLE001:17, F401:1, I001:2, RUF100:1, S110:4, UP006:6, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/models/alert.py | 2 | UP045:2 | style_maintainability |
| backend/app/models/base.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| backend/app/models/candle.py | 1 | UP045:1 | style_maintainability |
| backend/app/models/market.py | 6 | UP045:6 | style_maintainability |
| backend/app/models/opportunity.py | 9 | F401:1, UP045:8 | correctness_review, style_maintainability |
| backend/app/models/paper_trade.py | 10 | UP045:10 | style_maintainability |
| backend/app/prediction/eligible_alerts.py | 5 | BLE001:2, FLY002:1, I001:1, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/prediction/kalshi_public.py | 2 | FURB157:2 | correctness_review |
| backend/app/prediction/paper_engine.py | 41 | BLE001:3, FURB157:28, FURB162:1, I001:1, RUF007:1, S112:2, SIM117:1, UP017:4 | correctness_review, policy_review, style_maintainability |
| backend/app/prediction/prediction_paper_automation.py | 14 | BLE001:6, FURB157:3, S110:3, UP017:1, UP041:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/accumulation_ladder.py | 45 | BLE001:12, I001:1, RUF046:2, S110:1, S112:1, UP006:22, UP035:3, UP045:3 | correctness_review, policy_review, style_maintainability |
| backend/app/services/alpha_extract.py | 5 | FURB162:1, I001:1, UP017:3 | correctness_review, style_maintainability |
| backend/app/services/alpha_fetch.py | 11 | BLE001:3, F401:2, I001:1, S112:1, SIM117:1, UP017:2, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/alpha_ingestion.py | 9 | BLE001:2, F401:1, I001:1, S112:2, UP017:2, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/alpha_intelligence.py | 7 | FURB162:1, I001:1, UP017:4, UP035:1 | correctness_review, style_maintainability |
| backend/app/services/alpha_manual.py | 2 | I001:1, UP017:1 | style_maintainability |
| backend/app/services/alpha_operator.py | 4 | BLE001:1, I001:1, S112:1, UP017:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/alpha_pipeline.py | 3 | I001:1, UP017:2 | style_maintainability |
| backend/app/services/alpha_presentation.py | 10 | BLE001:4, FURB162:1, I001:1, UP017:4 | correctness_review, policy_review, style_maintainability |
| backend/app/services/auto_ladder.py | 39 | BLE001:7, F541:3, I001:1, S110:1, UP006:17, UP035:3, UP045:7 | correctness_review, policy_review, style_maintainability |
| backend/app/services/btc_accumulation.py | 23 | BLE001:9, I001:1, RUF046:2, S110:1, UP006:6, UP035:2, UP045:2 | correctness_review, policy_review, style_maintainability |
| backend/app/services/candle_service.py | 4 | I001:1, UP006:1, UP017:1, UP035:1 | style_maintainability |
| backend/app/services/challenger_exit_replay.py | 20 | UP006:15, UP035:2, UP045:3 | style_maintainability |
| backend/app/services/challenger_lab.py | 16 | UP006:10, UP035:2, UP045:4 | style_maintainability |
| backend/app/services/challenger_prospective.py | 27 | BLE001:1, F401:1, FURB162:1, S110:1, UP006:12, UP017:5, UP035:2, UP045:4 | correctness_review, policy_review, style_maintainability |
| backend/app/services/command_center.py | 5 | BLE001:2, I001:1, UP045:2 | policy_review, style_maintainability |
| backend/app/services/command_center_summary.py | 3 | F401:1, I001:1, UP035:1 | correctness_review, style_maintainability |
| backend/app/services/cross_strategy_scorecard.py | 39 | BLE001:3, FURB162:1, I001:1, TRY004:1, UP006:19, UP017:4, UP035:2, UP045:8 | correctness_review, policy_review, style_maintainability |
| backend/app/services/daily_paper_recap.py | 7 | BLE001:1, I001:1, ISC004:2, UP017:1, UP045:2 | policy_review, style_maintainability |
| backend/app/services/day_trade_assistant.py | 10 | BLE001:6, S110:1, SIM102:1, UP045:2 | correctness_review, policy_review, style_maintainability |
| backend/app/services/day_trading_cohort_diagnostics.py | 12 | I001:1, UP006:9, UP035:2 | style_maintainability |
| backend/app/services/e26_attribution.py | 25 | BLE001:1, FURB162:1, I001:1, UP006:20, UP035:2 | correctness_review, policy_review, style_maintainability |
| backend/app/services/e27_preregistration.py | 4 | UP006:3, UP035:1 | style_maintainability |
| backend/app/services/e28_challenger_workbench.py | 13 | F401:1, UP006:9, UP035:3 | correctness_review, style_maintainability |
| backend/app/services/e29_forward_scorecard.py | 6 | F401:1, FURB162:1, I001:1, UP006:1, UP035:2 | correctness_review, style_maintainability |
| backend/app/services/e30_evidence_maturity.py | 2 | BLE001:1, I001:1 | policy_review, style_maintainability |
| backend/app/services/e42_alpha_health.py | 6 | BLE001:1, FURB162:1, I001:1, UP017:3 | correctness_review, policy_review, style_maintainability |
| backend/app/services/e43_cadence_store.py | 3 | BLE001:1, I001:1, UP017:1 | policy_review, style_maintainability |
| backend/app/services/e45_cadence_window.py | 9 | BLE001:2, FURB162:1, I001:1, S112:1, UP017:4 | correctness_review, policy_review, style_maintainability |
| backend/app/services/e46_corroboration.py | 5 | BLE001:1, FURB162:1, I001:1, UP017:2 | correctness_review, policy_review, style_maintainability |
| backend/app/services/e48_discord_events.py | 7 | BLE001:3, I001:1, UP017:2, UP035:1 | policy_review, style_maintainability |
| backend/app/services/edge_diagnostics.py | 95 | BLE001:6, F401:2, I001:2, UP006:72, UP035:4, UP045:9 | correctness_review, policy_review, style_maintainability |
| backend/app/services/equity_daytrade_paper_mirror.py | 4 | BLE001:1, S112:1, UP017:1, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/evidence_checkpoint_history.py | 49 | FURB162:1, I001:1, UP006:32, UP017:6, UP035:1, UP045:8 | correctness_review, style_maintainability |
| backend/app/services/funnel_research.py | 42 | BLE001:5, F401:2, F541:1, F841:1, FURB162:1, I001:1, PLR0124:1, RUF046:1, S112:1, UP006:20, UP017:1, UP035:4, UP045:3 | correctness_review, policy_review, style_maintainability |
| backend/app/services/micro_heartbeat.py | 11 | BLE001:3, I001:1, S110:1, UP017:3, UP045:3 | correctness_review, policy_review, style_maintainability |
| backend/app/services/morning_command_center.py | 11 | BLE001:3, F401:1, F541:1, I001:1, UP045:5 | correctness_review, policy_review, style_maintainability |
| backend/app/services/oos_cost_validation.py | 4 | BLE001:1, F841:1, RUF046:1, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/opportunity_tracker.py | 8 | BLE001:1, I001:1, RUF059:1, UP017:4, UP045:1 | policy_review, style_maintainability |
| backend/app/services/outcome_research.py | 59 | BLE001:2, F401:3, F841:1, FURB162:1, I001:1, ISC004:2, UP006:38, UP035:4, UP045:7 | correctness_review, policy_review, style_maintainability |
| backend/app/services/paper_adaptive_exit.py | 5 | BLE001:1, FURB162:1, UP017:3 | correctness_review, policy_review, style_maintainability |
| backend/app/services/paper_attribution.py | 33 | F401:1, FURB162:1, I001:1, PLR0124:1, UP006:23, UP035:3, UP045:3 | correctness_review, style_maintainability |
| backend/app/services/paper_execution_cohorts.py | 4 | FURB162:1, I001:1, UP017:2 | correctness_review, style_maintainability |
| backend/app/services/paper_journal.py | 62 | BLE001:2, FURB162:1, I001:1, RET501:1, S110:1, UP006:41, UP017:1, UP035:2, UP045:12 | correctness_review, policy_review, style_maintainability |
| backend/app/services/paper_pipeline.py | 45 | BLE001:6, FURB162:3, I001:1, S110:1, UP006:17, UP017:1, UP035:4, UP045:12 | correctness_review, policy_review, style_maintainability |
| backend/app/services/paper_pipeline_hooks.py | 10 | BLE001:2, F401:1, F841:1, I001:2, UP017:4 | correctness_review, policy_review, style_maintainability |
| backend/app/services/paper_reconciliation_alert.py | 4 | I001:1, UP017:2, UP035:1 | style_maintainability |
| backend/app/services/paper_risk_controls.py | 2 | BLE001:2 | policy_review |
| backend/app/services/paper_trade_tracker.py | 6 | UP006:3, UP035:2, UP045:1 | style_maintainability |
| backend/app/services/paper_try_symbol.py | 12 | BLE001:4, I001:1, S110:1, UP017:5, UP045:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/paper_validation.py | 102 | BLE001:1, FURB162:1, RUF046:2, SIM102:1, UP006:84, UP035:4, UP045:9 | correctness_review, policy_review, style_maintainability |
| backend/app/services/performance.py | 2 | BLE001:1, UP045:1 | policy_review, style_maintainability |
| backend/app/services/performance_service.py | 5 | B009:1, BLE001:2, F401:1, SIM102:1 | correctness_review, policy_review |
| backend/app/services/perp_alert_delivery.py | 31 | BLE001:9, I001:1, RUF046:2, S110:1, UP006:13, UP035:2, UP045:3 | correctness_review, policy_review, style_maintainability |
| backend/app/services/perp_manual_service.py | 30 | BLE001:6, S110:2, UP006:12, UP017:3, UP035:1, UP045:6 | correctness_review, policy_review, style_maintainability |
| backend/app/services/perp_micro_coach.py | 116 | BLE001:20, F841:1, FURB162:1, I001:2, S110:10, UP006:59, UP017:12, UP035:4, UP045:7 | correctness_review, policy_review, style_maintainability |
| backend/app/services/perp_paper_observability.py | 8 | BLE001:1, FURB162:1, I001:1, S110:1, UP017:3, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/perp_setup_paper_mirror.py | 12 | BLE001:4, F841:1, FURB162:1, I001:1, RUF010:1, UP017:4 | correctness_review, policy_review, style_maintainability |
| backend/app/services/quality_dip_scanner.py | 27 | BLE001:8, FURB162:1, UP006:10, UP017:1, UP035:2, UP045:5 | correctness_review, policy_review, style_maintainability |
| backend/app/services/replay.py | 10 | DTZ004:1, I001:1, UP006:5, UP035:2, UP045:1 | style_maintainability |
| backend/app/services/robinhood_brief.py | 14 | BLE001:5, I001:1, UP006:4, UP035:2, UP045:2 | policy_review, style_maintainability |
| backend/app/services/robinhood_universe_research.py | 3 | BLE001:1, UP017:2 | policy_review, style_maintainability |
| backend/app/services/runtime_hardening.py | 9 | BLE001:4, S110:3, UP017:2 | correctness_review, policy_review, style_maintainability |
| backend/app/services/runtime_snapshot.py | 2 | BLE001:1, UP041:1 | policy_review, style_maintainability |
| backend/app/services/scanner.py | 25 | BLE001:7, S110:3, UP006:9, UP017:2, UP035:3, UP045:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/shadow_paper_interactions.py | 17 | UP006:10, UP035:2, UP045:5 | style_maintainability |
| backend/app/services/shadow_research.py | 50 | BLE001:4, F841:1, FURB162:1, I001:1, SIM102:1, UP006:30, UP017:1, UP035:4, UP045:7 | correctness_review, policy_review, style_maintainability |
| backend/app/services/v2_setup_attribution.py | 19 | I001:1, UP006:16, UP035:2 | style_maintainability |
| backend/app/services/v4_journal_observer.py | 7 | BLE001:4, UP006:2, UP035:1 | policy_review, style_maintainability |
| backend/app/services/v4_shadow_bridge.py | 6 | BLE001:2, S110:2, UP006:1, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/v5_challenger.py | 5 | BLE001:1, FURB162:1, UP017:2, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/v5_research.py | 1 | UP035:1 | style_maintainability |
| backend/app/services/v6_candidate_comparison.py | 7 | F841:1, I001:1, UP006:4, UP035:1 | correctness_review, style_maintainability |
| backend/app/services/v6_confirmation_sequences.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_consistency_changes.py | 4 | I001:1, RUF007:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_diversity_trends.py | 4 | I001:1, PLC3002:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_evidence_maturity.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_evidence_sufficiency_gaps.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_evidence_trends.py | 9 | I001:1, RUF007:2, UP006:4, UP034:1, UP035:1 | style_maintainability |
| backend/app/services/v6_fixed_window_diversity.py | 4 | I001:1, UP006:2, UP035:1 | style_maintainability |
| backend/app/services/v6_forward_monitor.py | 18 | I001:2, UP006:14, UP017:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_confirmation_sequences.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_sequence_run_boundaries.py | 4 | I001:1, RUF007:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_sequence_run_boundary_recurrence.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_sequence_run_lengths.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_sequence_stability.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_transition_persistence.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_maturity_transitions.py | 4 | I001:1, RUF007:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_multi_window_history.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_readiness_scorecard.py | 9 | I001:2, UP006:6, UP035:1 | style_maintainability |
| backend/app/services/v6_research_evidence_ui.py | 1 | I001:1 | style_maintainability |
| backend/app/services/v6_research_status.py | 4 | BLE001:1, I001:1, UP045:2 | policy_review, style_maintainability |
| backend/app/services/v6_stability.py | 9 | BLE001:1, FURB162:1, I001:1, UP006:4, UP034:1, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/v6_transition_persistence.py | 3 | I001:1, UP006:1, UP035:1 | style_maintainability |
| backend/app/services/v6_window_diversity.py | 9 | BLE001:1, FURB162:1, I001:1, UP006:2, UP017:2, UP034:1, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/validation_proof.py | 9 | BLE001:2, FURB162:1, S112:1, UP017:4, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/services/weekly_summary.py | 8 | BLE001:3, F401:1, I001:1, UP017:2, UP045:1 | correctness_review, policy_review, style_maintainability |
| backend/app/trading_core/__init__.py | 1 | RUF022:1 | style_maintainability |
| backend/app/trading_core/domains.py | 4 | I001:1, UP006:1, UP035:2 | style_maintainability |
| backend/app/trading_core/event_store.py | 11 | I001:1, UP006:5, UP035:3, UP045:2 | style_maintainability |
| backend/app/trading_core/events.py | 9 | FURB162:1, UP006:5, UP017:1, UP035:1, UP037:1 | correctness_review, style_maintainability |
| backend/app/trading_core/live_shadow_hooks.py | 4 | UP006:3, UP035:1 | style_maintainability |
| backend/app/trading_core/models.py | 11 | UP017:1, UP037:1, UP045:9 | style_maintainability |
| backend/app/trading_core/paper_engine.py | 3 | UP006:1, UP035:2 | style_maintainability |
| backend/app/trading_core/perp_board.py | 2 | I001:1, UP035:1 | style_maintainability |
| backend/app/trading_core/perp_discovery.py | 2 | SIM114:1, UP035:1 | correctness_review, style_maintainability |
| backend/app/trading_core/perp_manual_planner.py | 3 | UP006:1, UP035:2 | style_maintainability |
| backend/app/trading_core/perp_manual_state_store.py | 2 | I001:1, UP035:1 | style_maintainability |
| backend/app/trading_core/perp_manual_trade_lifecycle.py | 3 | UP017:3 | style_maintainability |
| backend/app/trading_core/perp_order_sanity.py | 2 | UP006:1, UP035:1 | style_maintainability |
| backend/app/trading_core/perp_setup_lifecycle.py | 8 | BLE001:1, FURB162:1, S110:1, UP017:4, UP035:1 | correctness_review, policy_review, style_maintainability |
| backend/app/trading_core/persistent_runtime.py | 7 | F401:2, UP006:3, UP035:2 | correctness_review, style_maintainability |
| backend/app/trading_core/position_book.py | 15 | UP006:8, UP035:3, UP037:2, UP045:2 | style_maintainability |
| backend/app/trading_core/replay.py | 13 | I001:1, UP006:9, UP035:3 | style_maintainability |
| backend/app/trading_core/runtime.py | 9 | FURB162:1, UP006:3, UP017:2, UP035:1, UP045:2 | correctness_review, style_maintainability |
| backend/app/trading_core/shadow_coordinator.py | 15 | BLE001:4, I001:1, UP006:3, UP017:2, UP035:1, UP045:4 | policy_review, style_maintainability |
| backend/app/trading_core/shadow_operational_checkpoint.py | 1 | I001:1 | style_maintainability |
| scripts/atlas_watchdog.py | 6 | BLE001:4, S110:2 | correctness_review, policy_review |
| scripts/investment_health.py | 8 | I001:1, RUF100:7 | style_maintainability |
| scripts/investment_live_probe.py | 5 | FURB105:1, RUF100:4 | correctness_review, style_maintainability |
| scripts/investment_research_probe.py | 6 | I001:1, RUF100:5 | style_maintainability |
| scripts/investment_scan.py | 5 | I001:1, RUF100:4 | style_maintainability |
| scripts/runtime_recovery_soak.py | 3 | BLE001:2, I001:1 | policy_review, style_maintainability |
| scripts/runtime_recovery_summary.py | 1 | I001:1 | style_maintainability |
| tests/test_a23_background_recovery_hardening.py | 1 | I001:1 | style_maintainability |
| tests/test_a23_passive_background_gui.py | 1 | I001:1 | style_maintainability |
| tests/test_a23_stop_worker_failure.py | 2 | F841:1, I001:1 | correctness_review, style_maintainability |
| tests/test_accumulation_ladder_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_alpha_extract.py | 1 | I001:1 | style_maintainability |
| tests/test_alpha_fetch.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_alpha_ingestion.py | 1 | I001:1 | style_maintainability |
| tests/test_alpha_intelligence.py | 1 | I001:1 | style_maintainability |
| tests/test_alpha_manual.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_alpha_operator.py | 1 | I001:1 | style_maintainability |
| tests/test_alpha_pipeline.py | 1 | I001:1 | style_maintainability |
| tests/test_alpha_presentation.py | 2 | I001:2 | style_maintainability |
| tests/test_api_nonblocking_operational_surfaces.py | 5 | I001:3, PIE807:2 | style_maintainability |
| tests/test_archive_export_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_archive_investment_history_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_archive_paper_trades_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_archive_research_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_archive_snapshots_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_backtest_binance_public_batch.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_htf_batch.py | 2 | I001:2 | style_maintainability |
| tests/test_backtest_binance_public_htf_context.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_inspect.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_metrics.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_metrics_batch.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_metrics_inspect.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_metrics_normalize.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_normalize.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_rolling_volume.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_rolling_volume_batch.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_binance_public_rolling_volume_probe.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_canonical_assemble.py | 2 | I001:1, RUF015:1 | style_maintainability |
| tests/test_backtest_canonical_batch.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_context_v2.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_development_decision_freeze.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_funding_events.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_funding_pit_merge.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_funding_pit_merge_batch.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_holdout_build_plan.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_holdout_candle_batch.py | 1 | F401:1 | correctness_review |
| tests/test_backtest_holdout_evaluation.py | 3 | F401:2, I001:1 | correctness_review, style_maintainability |
| tests/test_backtest_holdout_evaluation_execution.py | 1 | F401:1 | correctness_review |
| tests/test_backtest_holdout_evidence_freeze.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_holdout_oi_batch.py | 1 | F401:1 | correctness_review |
| tests/test_backtest_htf_context.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_hyperliquid_acquire.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_hyperliquid_archive.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_hyperliquid_archive_inspect.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_hyperliquid_funding_batch.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_hyperliquid_funding_history.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_backtest_import_cli.py | 2 | I001:1, RUF059:1 | style_maintainability |
| tests/test_backtest_locked_development_baseline.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_backtest_locked_development_baseline_run.py | 5 | F401:4, I001:1 | correctness_review, style_maintainability |
| tests/test_backtest_manifest.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_provider_normalize.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_representative_windows.py | 2 | I001:1, RUF007:1 | style_maintainability |
| tests/test_backtest_smoke_reconciliation.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_source_audit.py | 1 | I001:1 | style_maintainability |
| tests/test_backtest_source_plan.py | 1 | I001:1 | style_maintainability |
| tests/test_command_center_api_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_command_center_health_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_command_center_overview_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_command_center_risk_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_daily_research_plan.py | 2 | I001:2 | style_maintainability |
| tests/test_dashboard_hub_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_day_trade_assistant.py | 1 | I001:1 | style_maintainability |
| tests/test_day_trading_cohort_diagnostics.py | 1 | I001:1 | style_maintainability |
| tests/test_e112_compact_label_semantics.py | 1 | I001:1 | style_maintainability |
| tests/test_e120_runtime_configuration.py | 1 | I001:1 | style_maintainability |
| tests/test_e26_attribution.py | 1 | I001:1 | style_maintainability |
| tests/test_e29_forward_scorecard.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_e30_evidence_maturity.py | 1 | I001:1 | style_maintainability |
| tests/test_e37_alpha_endpoint.py | 1 | I001:1 | style_maintainability |
| tests/test_e42_alpha_policy.py | 1 | I001:1 | style_maintainability |
| tests/test_e43_cadence_store.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_e44_time_health.py | 1 | I001:1 | style_maintainability |
| tests/test_e45_cadence_window.py | 1 | I001:1 | style_maintainability |
| tests/test_e46_corroboration.py | 1 | I001:1 | style_maintainability |
| tests/test_e47_alpha_operator_surface.py | 2 | C405:1, I001:1 | style_maintainability |
| tests/test_e48_discord_events.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_e49_discord_migration.py | 4 | F401:3, I001:1 | correctness_review, style_maintainability |
| tests/test_e50_discord_perp_system_migration.py | 1 | I001:1 | style_maintainability |
| tests/test_e51_discord_observability.py | 1 | I001:1 | style_maintainability |
| tests/test_e51_discord_observability_inventory.py | 1 | I001:1 | style_maintainability |
| tests/test_e52_system_summary_discord.py | 4 | F401:1, I001:1, PIE807:1, PLR0402:1 | correctness_review, style_maintainability |
| tests/test_e53_discord_observability_api.py | 1 | I001:1 | style_maintainability |
| tests/test_e54_robinhood_brief_discord.py | 2 | I001:1, PLR0402:1 | style_maintainability |
| tests/test_e55_stateful_discord_contracts.py | 2 | I001:1, PLR0402:1 | style_maintainability |
| tests/test_e57_auto_ladder_typed_discord.py | 2 | I001:1, PLR0402:1 | style_maintainability |
| tests/test_e58_startup_discord_contract.py | 3 | I001:1, PLR0402:2 | style_maintainability |
| tests/test_e59_typed_attachment_contract.py | 1 | I001:1 | style_maintainability |
| tests/test_e60_crypto_quality_dips_scaffold.py | 1 | I001:1 | style_maintainability |
| tests/test_e61_research_contract.py | 3 | F401:2, I001:1 | correctness_review, style_maintainability |
| tests/test_e62_research_store.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_e63_crypto_quality_dips_api.py | 1 | I001:1 | style_maintainability |
| tests/test_e64_crypto_ingestion.py | 1 | F401:1 | correctness_review |
| tests/test_e65_operator_integrity.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_e66_identity_audit.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_e67_chain_integrity.py | 1 | I001:1 | style_maintainability |
| tests/test_e68_chain_head_states.py | 1 | I001:1 | style_maintainability |
| tests/test_e69_integrity_diagnostics_api.py | 1 | I001:1 | style_maintainability |
| tests/test_e70_evidence_lifecycle.py | 1 | I001:1 | style_maintainability |
| tests/test_e71_operator_presentation.py | 1 | I001:1 | style_maintainability |
| tests/test_e72_crypto_quality_dips_public_contract.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_e73_crypto_quality_dips_frontend_consumer.py | 1 | I001:1 | style_maintainability |
| tests/test_e74_crypto_quality_dips_frontend_panel.py | 1 | I001:1 | style_maintainability |
| tests/test_edge_diagnostics.py | 3 | F401:1, I001:2 | correctness_review, style_maintainability |
| tests/test_edge_http.py | 1 | I001:1 | style_maintainability |
| tests/test_evidence_checkpoint_history.py | 3 | I001:3 | style_maintainability |
| tests/test_evidence_lifecycle.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_frontend_freeze_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_frontend_runtime_contract.py | 1 | PLW1510:1 | style_maintainability |
| tests/test_funnel_research.py | 3 | F401:3 | correctness_review |
| tests/test_future_overview_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_historical_backtest_foundation.py | 1 | I001:1 | style_maintainability |
| tests/test_hyperliquid_historical_import.py | 1 | I001:1 | style_maintainability |
| tests/test_investment_action_gate_v4.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_investment_architecture.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_investment_board_api_v4.py | 3 | I001:1, PIE807:2 | style_maintainability |
| tests/test_investment_collection.py | 4 | F401:3, F841:1 | correctness_review |
| tests/test_investment_dashboard_v4.py | 2 | I001:1, PLW1510:1 | style_maintainability |
| tests/test_investment_data.py | 2 | I001:2 | style_maintainability |
| tests/test_investment_engine_action_gate_v4.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_investment_phase4.py | 3 | F401:1, I001:1, RUF059:1 | correctness_review, style_maintainability |
| tests/test_investment_phase5.py | 7 | F401:2, I001:5 | correctness_review, style_maintainability |
| tests/test_investment_phase51.py | 3 | F401:1, I001:1, RUF059:1 | correctness_review, style_maintainability |
| tests/test_investment_research.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_investment_research_math.py | 1 | I001:1 | style_maintainability |
| tests/test_major_moves.py | 7 | F401:3, I001:2, RUF059:2 | correctness_review, style_maintainability |
| tests/test_outcome_research.py | 2 | F401:1, F811:1 | correctness_review |
| tests/test_paper_execution_model.py | 2 | I001:2 | style_maintainability |
| tests/test_paper_exit_execution_model.py | 1 | I001:1 | style_maintainability |
| tests/test_paper_pipeline.py | 6 | I001:2, RUF012:2, UP006:1, UP035:1 | style_maintainability |
| tests/test_paper_risk_api.py | 1 | I001:1 | style_maintainability |
| tests/test_paper_risk_control_store.py | 1 | F401:1 | correctness_review |
| tests/test_paper_session.py | 4 | F401:3, I001:1 | correctness_review, style_maintainability |
| tests/test_paper_validation.py | 2 | I001:2 | style_maintainability |
| tests/test_pass16_reconciliation_status_and_execution_version.py | 2 | I001:2 | style_maintainability |
| tests/test_perp_alert_delivery_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_dashboard_shell_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_discovery_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_board_api_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_discovery_service_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_entry_service_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_persistence_service_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_service_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_state_store_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_manual_trade_lifecycle_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_micro_baseline_backtest.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_setup_lifecycle_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_setup_paper_mirror_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_perp_setup_state_v4.py | 4 | C408:4 | style_maintainability |
| tests/test_post994_responsiveness.py | 1 | I001:1 | style_maintainability |
| tests/test_prediction_markets_phase1.py | 5 | BLE001:1, FURB157:3, I001:1 | correctness_review, policy_review, style_maintainability |
| tests/test_prediction_paper_automation.py | 2 | FURB157:1, I001:1 | correctness_review, style_maintainability |
| tests/test_prospective_evidence.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_prospective_outcomes.py | 1 | I001:1 | style_maintainability |
| tests/test_prospective_research_api.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dip_paper.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dip_quotes_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_paper_exit_policy.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_paper_marking.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_quality_dips_paper_v1.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_v2_entries.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_v2_policy.py | 1 | C408:1 | style_maintainability |
| tests/test_quality_dips_v2_runtime.py | 2 | I001:2 | style_maintainability |
| tests/test_quality_dips_v2_valuation.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_v3.py | 2 | C408:1, I001:1 | style_maintainability |
| tests/test_quality_dips_v3_alerts.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_v3_forward_readiness.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_v3_forward_store.py | 1 | F401:1 | correctness_review |
| tests/test_quality_dips_v3_state.py | 1 | I001:1 | style_maintainability |
| tests/test_quality_dips_visual_runtime.py | 1 | PLW1510:1 | style_maintainability |
| tests/test_r7e44g_data_reliability.py | 2 | I001:2 | style_maintainability |
| tests/test_r7e46g_collector_lock_acceptance.py | 2 | BLE001:1, I001:1 | policy_review, style_maintainability |
| tests/test_r7e46g_crash_recovery.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_r7e46g_extended_hours_concurrency.py | 1 | I001:1 | style_maintainability |
| tests/test_r7e46g_windows_lock_contract.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_r7e46h_extended_hours_service.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_runtime_hardening_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_runtime_snapshot.py | 1 | I001:1 | style_maintainability |
| tests/test_runtime_watchdog.py | 1 | ASYNC251:1 | style_maintainability |
| tests/test_scalp_exit.py | 1 | I001:1 | style_maintainability |
| tests/test_shadow_research.py | 4 | F401:2, F841:1, I001:1 | correctness_review, style_maintainability |
| tests/test_trading_core_domains_and_manual_perps.py | 1 | I001:1 | style_maintainability |
| tests/test_trading_core_event_store_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_trading_core_live_shadow_v4.py | 1 | F401:1 | correctness_review |
| tests/test_trading_core_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_trading_shadow_operational_checkpoint.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_v3_forward_diagnostics_and_paper_reconciliation.py | 3 | F401:3 | correctness_review |
| tests/test_v4_journal_installation.py | 4 | I001:1, UP006:2, UP035:1 | style_maintainability |
| tests/test_v6_candidate_comparison.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_confirmation_sequences.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_consistency_changes.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_diversity_trends.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_evidence_maturity.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_evidence_sufficiency_gaps.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_evidence_trends.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_fixed_window_diversity.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_forward_monitor.py | 2 | F401:1, I001:1 | correctness_review, style_maintainability |
| tests/test_v6_maturity_confirmation_sequences.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_maturity_sequence_run_boundaries.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_maturity_sequence_run_boundary_recurrence.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_maturity_sequence_run_lengths.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_maturity_sequence_stability.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_maturity_transition_persistence.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_maturity_transitions.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_multi_window_history.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_readiness_scorecard.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_research_evidence_ui.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_research_status_command_center.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_risk_stability.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_stability.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_transition_persistence.py | 1 | I001:1 | style_maintainability |
| tests/test_v6_window_diversity.py | 1 | I001:1 | style_maintainability |
| tests/test_validation_proof_api_v4.py | 1 | I001:1 | style_maintainability |
| tests/test_validation_proof_v4.py | 2 | F601:1, I001:1 | correctness_review, style_maintainability |

## Rules

| Rule | Count |
|---|---:|
| ASYNC251 | 1 |
| B008 | 2 |
| B009 | 1 |
| B023 | 3 |
| BLE001 | 399 |
| C405 | 1 |
| C408 | 14 |
| DTZ004 | 1 |
| F401 | 116 |
| F541 | 5 |
| F601 | 1 |
| F811 | 55 |
| F841 | 16 |
| FLY002 | 1 |
| FURB105 | 1 |
| FURB157 | 57 |
| FURB162 | 73 |
| G201 | 1 |
| I001 | 409 |
| ISC004 | 5 |
| PERF402 | 1 |
| PIE807 | 5 |
| PLC3002 | 1 |
| PLR0124 | 8 |
| PLR0402 | 6 |
| PLR1730 | 3 |
| PLW0602 | 2 |
| PLW1510 | 12 |
| RET501 | 1 |
| RUF007 | 14 |
| RUF010 | 1 |
| RUF012 | 2 |
| RUF015 | 1 |
| RUF022 | 4 |
| RUF046 | 13 |
| RUF059 | 7 |
| RUF100 | 23 |
| S110 | 54 |
| S112 | 27 |
| SIM102 | 11 |
| SIM103 | 2 |
| SIM114 | 2 |
| SIM117 | 4 |
| SIM210 | 1 |
| TRY004 | 11 |
| UP006 | 1296 |
| UP017 | 265 |
| UP034 | 3 |
| UP035 | 310 |
| UP037 | 10 |
| UP041 | 8 |
| UP045 | 728 |
