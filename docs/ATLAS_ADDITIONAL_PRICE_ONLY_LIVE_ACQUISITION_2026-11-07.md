# Additional live prices-only research acquisition — 2026-11-07

Ran `python -B -m scripts.observation_runtime.qd_free_research_acquisition --prices-only --symbol SYMBOL` against the configured Alpaca provider, individually for QQQ, IWM, and AVGO.

| Symbol | Completed daily bars | Provider receipts | Exit code |
|---|---:|---:|---:|
| QQQ | 1,257 | 6 | 0 |
| IWM | 1,257 | 6 | 0 |
| AVGO | 1,257 | 6 | 0 |

All three outputs explicitly reported `fundamentals_available=false`, `independent_analyst_targets_verified=false`, `operational_source_accepted=false`, `paper_fill_authorized=false`, and `live_order_authorized=false`.

These results verify historical read-only acquisition for the listed symbols only. They do not establish all Robinhood instruments, independent valuation targets, executable quotes, financial custody, rights, or PAPER commissioning. The six receipts per symbol were reported by the provider workflow; no independent receipt audit is asserted here.
