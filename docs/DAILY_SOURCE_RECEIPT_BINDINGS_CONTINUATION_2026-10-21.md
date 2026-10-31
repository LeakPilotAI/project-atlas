# Daily source receipt bindings — continuation

## Milestone

Extended the offline daily bridge and AFI dataset validator so source receipt commitments remain attached to individual normalized price observations and corporate-action events consumed by forecasting and evaluation. The versioned AFI payload's legacy rows remain supported.

## Implementation

- Daily price observations now carry the exact SHA-256 of the chart snapshot that supplied their first retained value, alongside the existing caller-received `available_at`, dataset source ID, and revision.
- Price revision identities now commit to the observation timestamp, receipt timestamp, retained value, and source-snapshot hash. `review_dataset` validates the content-addressed revision for rows that supply this commitment, so changing the source hash, receipt or normalized value without a matching revision refuses.
- Corporate-action dataset rows now carry the source ID/hash, explicit economic unit, effective time, first receipt availability, and amount. The shared validator checks source identity shape, source hash, split/dividend units, action chronology, and rejects actions outside declared listing/delisting membership.
- Legacy AFI dataset records/actions without the new optional provenance fields remain accepted under the pre-existing schema. Optional provenance is all-or-none for action rows.
- Source hashes are consistency commitments only. The daily export reconstructs the exact source artifacts; neither hashes nor caller-declared receipts authenticate a vendor, publication time, completeness, licensing, or truth.
- No forecast or outcome artifacts were changed. Baseline, dataset scoring, and existing dashboard publication continue to bind the updated AFI content hash and manifest. Production and authority flags remain false.

## Validation

- Final focused bridge/export/dataset-integrity/baseline/probability/protocol/clean-extraction run: **201 passed**.
- Targeted Ruff and Python compilation passed.
- Earlier intermediate runs exposed expected test-contract adjustments while adding mandatory provenance for newly bound rows; the fixtures and validator were aligned. One malformed pytest selector (`tests\daily*`) exited before running tests; the corrected explicit suite above passed.
- No provider or external financial service was contacted; no dependency was installed.

## Files

- `backend/app/backtest/forecast_dataset.py`
- `scripts/observation_runtime/daily_afi_bridge.py`
- `tests/test_afi_dataset_integrity.py`
- `tests/test_daily_afi_bridge.py`
- Related previous increment: `scripts/observation_runtime/daily_afi_export.py`, `tests/test_daily_afi_export.py`, and `tests/test_daily_export_packaging.py`.

Existing unrelated dirty/untracked work was preserved. No Git stage, commit, push, reset, clean, or stash was performed.

## Readiness and restrictions

AFI-1 independent review and AFI-2 authorized historical evidence acceptance remain unavailable. The implementation admits deterministic synthetic fixtures only and does not validate licensed historical data or real-market forecasting skill. Offline forecasting/dashboard checks establish byte consistency, not predictive value.

Production remains **NO-GO**; all **21 release decisions** are preserved. No provider, Atlas, Genesis, Docker, Discord, PAPER or live-trading service was activated.

## Next action

Improve the existing offline accountability dashboard to display the issue-time input observation's source/receipt provenance from the reviewed dataset, preserving compatibility for legacy reports and avoiding new persistence or live services. Then continue another feasible offline roadmap task. Keep the external AFI acceptance blockers explicit.
