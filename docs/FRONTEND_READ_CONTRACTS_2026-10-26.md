# Original frontend data contract inventory — 2026-10-26

Every tracked original HTML page; endpoints extracted from source literals. Dynamic suffixes require their parent API contract. No operational registration implied.

| Page | Required data routes |
|---|---|
| archive.html | `/api/archive/investment-history/`, `/api/archive/investment-history?limit=400`, `/api/archive/investment-paper-v1`, `/api/validation/cross-strategy-checkpoints`, `/api/validation/cross-strategy-scorecard` |
| archive_export.html | `/api/archive/export/download?dataset=`, `/api/archive/export/preview?dataset=`, `/api/archive/export/summary` |
| archive_paper_trades.html | `/api/archive/paper-trades`, `/api/archive/paper-trades/` |
| archive_research.html | `/api/archive/research-archive/`, `/api/archive/research-archive?` |
| archive_snapshots.html | `/api/archive/snapshots/`, `/api/archive/snapshots?` |
| command_center.html | `/api/archive/paper-trades?limit=500`, `/api/command-center/summary`, `/api/live`, `/api/perps/manual/board?limit=8`, `/api/perps/paper-risk`, `/diagnostics/paper-reconciliation`, `/health` |
| command_center_health.html | `/api/archive/export/summary`, `/api/command-center/summary`, `/api/live`, `/api/perps/manual/board?limit=8`, `/api/perps/paper-risk`, `/diagnostics/paper-reconciliation`, `/health` |
| command_center_risk.html | `/api/archive/paper-trades?limit=500`, `/api/live`, `/api/perps/manual/board?limit=25`, `/api/perps/paper-risk`, `/api/perps/paper-risk/kill-switch?enabled=`, `/diagnostics/paper-reconciliation` |
| dashboard.html | `/api/investments/prospective/view`, `/api/live`, `/api/validation/e38-alpha-view`, `/api/validation/e42-alpha-governance`, `/api/validation/edge`, `/api/validation/summary`, `/health` |
| dashboard_hub.html | `/api/investments/quality-dips/view`, `/health` |
| dashboard_shell.html | `/api/observation/hyperliquid`, `/api/perps/candles?symbol=`, `/api/perps/manual`, `/api/perps/manual/alerts/`, `/api/perps/manual/board?limit=25`, `/api/perps/manual/plans/`, `/api/perps/manual/setups/`, `/api/perps/paper-risk`, `/api/perps/paper-risk/kill-switch?enabled=`, `/api/validation/e30-evidence-maturity` |
| future_overview.html | `/api/archive/paper-trades?limit=100`, `/api/command-center/summary`, `/api/investments/quality-dips/view`, `/api/investments/quality-dips?limit=8`, `/api/live`, `/api/perps/candles?symbol=`, `/api/perps/manual/board?limit=10`, `/api/prediction/markets?status=open&limit=6`, `/api/prediction/status` |
| investment.html | `/api/investments/prospective/report`, `/api/investments/quality-dips?limit=50`, `/api/live`, `/api/observation/quality-dips` |
| prediction_paper.html | `/api/prediction/paper/candidates?limit=200`, `/api/prediction/paper/status?limit=100` |
| prospective_research.html | `/api/investments/prospective/compound`, `/api/investments/prospective/report` |
| quality_dips.html | `/api/investments/quality-dips?limit=50`, `/api/observation/quality-dips` |

Observation host connects only health, selected-account explicit UNAVAILABLE, observation history/diagnostics, authenticated QD research read port and retained Hyperliquid metadata read port. All other research/financial API routes refuse. Legacy QD GET can refresh/persist; observation mode never invokes it. Archive/Prediction/portfolio/risk financial data require separately accepted sources. Retained metadata is not current trade/queue/funding-settlement evidence.
