# Daily corporate-action receipts — continuation

## Milestone

Implemented bounded, explicit corporate-action receipt handling in the existing synthetic equity/ETF daily bridge and export workflow. This increment does not contact providers, infer source truth, authorize any service, or change price adjustment policy.

## Implementation

- `scripts/observation_runtime/daily_afi_bridge.py` accepts optional separate action snapshots with exact content hashes, caller-declared source IDs, receipt times, and the existing AFI asset identity.
- Receipt clocks must be ordered and no later than the declared evidence cutoff. Action receipts are bounded to 64 snapshots, 2 MB per snapshot, and 8 MB combined with price-source bytes. Total action rows are bounded. Same-source same-time content conflicts, duplicate-ID changes/corrections, unsupported kinds, ambiguous units, malformed amounts, digest mismatches, and future receipts refuse explicitly.
- Only `SPLIT` with `NEW_SHARES_PER_OLD_SHARE` and `DIVIDEND` with `USD_PER_SHARE` are accepted. Exact retries preserve the first `available_at`; action provenance records the first source hash, source ID, and receipt time, while the audit retains supplied receipt chronology.
- Action rows reuse the existing AFI action schema. Prices remain explicitly `UNADJUSTED`; dividends remain excluded from price returns; split-adjusted prices, dividend reinvestment, and action reconciliation are not implied or accepted. Existing split-crossing forecast refusal remains in force.
- `scripts/observation_runtime/daily_afi_export.py` optionally accepts content-addressed action-source references. Request, exact source files, dataset, audit, and binding are reconstructed during verification. Existing requests without action snapshots remain compatible.
- Added direct regressions and a clean-extracted CLI case for action receipt binding and reconstruction.
- Added positive split and dividend fixtures; dividends are retained as explicitly USD/share actions without reinvestment or addition to price returns.

## Validation

- Focused bridge, export, and clean-extraction suites: **82 passed**.
- Downstream AFI dataset-integrity, baseline, daily-probability replay, and protocol suites: **118 passed**.
- Combined focused and downstream run: **200 passed**.
- After expanding the clean-extracted export fixture to include both a split and a dividend: **1 passed, 8 deselected** in the targeted packaging case.
- Targeted Ruff: passed.
- Targeted Python compilation: passed.
- `git diff --check` for task files: passed.
- The first focused run exposed two incorrect test expectations (lookback omitted the split boundary; extracted-workflow success was classified as failure). The tests were corrected; all final runs above passed. No product test remains failing in these runs.
- No dependencies were installed. No provider or external financial service was contacted. No live-data, licensing, production, or trading readiness is established.

## Files

- `scripts/observation_runtime/daily_afi_bridge.py`
- `scripts/observation_runtime/daily_afi_export.py`
- `tests/test_daily_afi_bridge.py`
- `tests/test_daily_afi_export.py`
- `tests/test_daily_export_packaging.py`
- `docs/DAILY_CORPORATE_ACTION_RECEIPTS_CONTINUATION_2026-10-21.md`

The worktree contains extensive unrelated pre-existing changes. No unrelated files were modified or reverted. No Git staging, commit, push, reset, clean, or stash was performed.

## Readiness and restrictions

Offline dashboard/backtesting remains usable only with explicit synthetic fixtures and source receipts. Corporate-action consistency is caller-declared and not independently authenticated. Live-data/provider rights and request-budget authorization remain blocked. PAPER and live trading remain unauthorized. Production remains **NO-GO**; all **21 release decisions** are preserved; AFI-1 through AFI-10 remain PENDING; all seven roadmap phases remain incomplete.

No Atlas, Genesis, Docker, Discord, provider, browser workaround, or trading service was activated.

## Roadmap checkpoint

The approved `scripts/windows/Atlas-Roadmap-Checkpoint.ps1` updater recorded this milestone. Its generated backup was verified byte-identical to the pre-update roadmap; the updated managed checkpoint was read back exactly, and all bytes outside the managed checkpoint were verified unchanged.

## Next action

Continue the AFI-1 contract consistency review and AFI-2 point-in-time dataset-manifest acceptance offline. Do not claim independent acceptance or use real historical data without an independent reviewer and authorized source rights/evidence. If those dependencies block progress, continue another feasible synthetic accountability/frontend integration task. Preserve all restrictions above; do not infer provider authorization or activate protected services.
