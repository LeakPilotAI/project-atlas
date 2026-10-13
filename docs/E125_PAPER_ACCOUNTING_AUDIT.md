# Execution 125 — paper accounting integrity

Initial checkpoint: `f61a1f2282cbb63cb041839f82e712cb97d735d1`, branch `chatgpt/atlas-rebuild-v1`.

Snapshot captured 2026-10-13T11:50:22.923880+00:00 (October 13, 2026, 06:50:22.923880 CDT). Analysis uses a fixed complete-line prefix, not a moving journal. Last close: 2026-10-13T11:30:47.765646+00:00 (06:30:47.765646 CDT).

Prefix: 6724297 bytes; SHA256 `e9aa09eca7b004ed407d06cfcf089accdd471c3a38719b9d1d29639c62612e7e`.

## Root causes and contract

- Ordinary BE/SCRATCH closes previously overwrote net R with zero after modeled cost deduction. Only SESSION_ROLL retains the administrative override; gross movement and existing round-trip cost formula remain unchanged. Shutdown INTERRUPTED uses its existing separate non-performance path.
- Truthiness fallback substituted gross R for valid zero net R. A pure shared reader now treats only absent/null net as eligible for legacy R_multiple fallback. Invalid, boolean, nonfinite, or entirely missing results remain unknown, never fallback wins or invented flats.
- Four research readers handled explicit null differently from missing net. They now share the same contract.
- Administrative closes leaked into outcome/edge research loaders and the E29 scorecard. Shared classification covers result, flags, interrupted status, atlas_shutdown and session_reset; no thresholds or membership decisions change.
- Existing scratch/exit-label semantics remain distinct from economic P&L. A cost-negative BE is still labeled scratch, but contributes negative net R. A genuine zero without a label is classified as scratch by journal tally. The existing live_* eligibility-subset fields are retained; they do not authorize live orders. Their legacy losses field counts nonpositive results, unlike the scratch-separated headline tally.
- Journal stats add invalid_results counts. Archive and research consumers exclude unknown results instead of fabricating zero. Existing archive administrative exclusion and execution-cohort interrupted counts are preserved. No frontend changes.

## Consumer trace

| Consumer | Resolution |
|---|---|
| PaperJournal close, _tally, session/all-time stats, bootstrap | Costs retained; zero authoritative; administrative exclusion; unknown count |
| edge_diagnostics / outcome_research loaders | Administrative and invalid results excluded before downstream metrics |
| paper_validation, cross_strategy_scorecard, challenger_lab, validation_proof, shadow_paper_interactions | Receive corrected production loader cohorts; shadow results remain separate |
| day_trading_cohort_diagnostics, v2_setup_attribution, e26_attribution | Null fallback aligned; direct cohort builders exclude invalid/admin rows |
| E29 scorecard | Exclude administrative/invalid closes without changing frozen open membership or evidence thresholds |
| paper_attribution | Strict net reader and eligible performance cohort |
| archive | Zero-safe reader retained through shared implementation; invalid results no longer become flats |
| paper_risk_window | Existing zero-safe logic unified; reject nonfinite values and administrative aliases; UTC window and risk limits unchanged |
| paper_execution_cohorts | Existing zero/null handling and separate interrupted counts retained; admin aliases recognized |
| Recovery/reconciliation | Identity/event-based, no net fallback; normal close remains idempotent |
| trading_core/replay | Already uses explicit missing/null net handling; separate legacy replay contract unchanged |

Generic research numeric helpers are not broadly rewritten: production paper cohorts are validated at their loaders. Hypothetical shadow/backtest calculations are not converted into journal fills.

## Historical evidence (read-only)

11564 valid rows; 0 malformed; 1286 unique open IDs; 1284 unique close IDs; zero duplicate opens/closes. Administrative exclusions: four SESSION_ROLL and 49 INTERRUPTED.

All-time close window: 2026-08-29T03:32:26.254220Z through 2026-10-13T11:30:47.765646Z. Recent cohort: exit_timestamp strictly after 2026-10-08T14:10:00Z, through the same snapshot. First recent close: 2026-10-08T14:14:41.489273Z.

| Cohort | N | Positive / negative / zero | Scratch labels | Net R | Average R | Profit factor | Realized max DD R |
|---|---:|---|---:|---:|---:|---:|---:|
| Recorded all closes | 1284 | 540 / 599 / 145 | 145 | -122.9494 | -0.095755 | 0.828068 | 196.9301 |
| All administrative-excluded | 1231 | 540 / 599 / 92 | 92 | -122.9494 | -0.099878 | 0.828068 | 196.9301 |
| Recorded recent closes | 100 | 48 / 42 / 10 | 10 | -3.9019 | -0.039019 | 0.849608 | 5.2109 |
| Recent administrative-excluded | 96 | 48 / 42 / 6 | 6 | -3.9019 | -0.040645 | 0.849608 | 5.2109 |
| All cost sensitivity (research only) | 1231 | 540 / 691 / 0 | 92 | -135.2884 | -0.109901 | 0.814022 | 209.1275 |
| Recent cost sensitivity (research only) | 96 | 48 / 48 / 0 | 6 | -4.7859 | -0.049853 | 0.821614 | 5.3525 |

Economic positive/negative/zero counts above are disjoint; scratch labels overlap economic losses after sensitivity adjustment. These figures must not be presented as the dashboard's scratch-separated win/loss categories.

### Strategy cohorts

| Strategy / period | N | Positive / negative / zero | Scratch labels | Net R | Avg R | PF | DD R | Close window UTC |
|---|---:|---|---:|---:|---:|---:|---:|---|
| perp_setup_auto_v1 / all | 16 | 7/9/0 | 0 | -5.3888 | -0.336800 | 0.450761 | 7.3914 | 2026-09-10T14:28:51.498096+00:00 to 2026-09-11T13:28:37.506251+00:00 |
| perp_setup_auto_v1 / adjusted_all | 16 | 7/9/0 | 0 | -5.3888 | -0.336800 | 0.450761 | 7.3914 | 2026-09-10T14:28:51.498096+00:00 to 2026-09-11T13:28:37.506251+00:00 |
| perp_setup_auto_v2_resting_limit / all | 276 | 117/159/0 | 0 | -116.1593 | -0.420867 | 0.492192 | 118.5629 | 2026-09-11T14:14:13.681672+00:00 to 2026-10-13T11:30:47.765646+00:00 |
| perp_setup_auto_v2_resting_limit / recent | 78 | 39/39/0 | 0 | -5.8102 | -0.074490 | 0.741057 | 6.3819 | 2026-10-09T02:21:36.234883+00:00 to 2026-10-13T11:30:47.765646+00:00 |
| perp_setup_auto_v2_resting_limit / adjusted_all | 276 | 117/159/0 | 0 | -116.1593 | -0.420867 | 0.492192 | 118.5629 | 2026-09-11T14:14:13.681672+00:00 to 2026-10-13T11:30:47.765646+00:00 |
| perp_setup_auto_v2_resting_limit / adjusted_recent | 78 | 39/39/0 | 0 | -5.8102 | -0.074490 | 0.741057 | 6.3819 | 2026-10-09T02:21:36.234883+00:00 to 2026-10-13T11:30:47.765646+00:00 |
| rsi_extension_v1 / all | 939 | 416/431/92 | 92 | -1.4013 | -0.001492 | 0.997059 | 79.0501 | 2026-08-29T03:32:26.254220+00:00 to 2026-10-13T11:13:46.359254+00:00 |
| rsi_extension_v1 / recent | 18 | 9/3/6 | 6 | 1.9083 | 0.106017 | 1.544171 | 2.3908 | 2026-10-08T14:14:41.489273+00:00 to 2026-10-13T11:13:46.359254+00:00 |
| rsi_extension_v1 / adjusted_all | 939 | 416/523/0 | 92 | -13.7403 | -0.014633 | 0.971895 | 91.2475 | 2026-08-29T03:32:26.254220+00:00 to 2026-10-13T11:13:46.359254+00:00 |
| rsi_extension_v1 / adjusted_recent | 18 | 9/9/0 | 6 | 1.0243 | 0.056906 | 1.233283 | 3.1332 | 2026-10-08T14:14:41.489273+00:00 to 2026-10-13T11:13:46.359254+00:00 |

### Sensitivity method and limitations

- There are 92 genuine BE closes, six since cutoff, and zero genuine SCRATCH-labeled closes in this snapshot. All 92 have recorded zero net, gross zero and usable cost inputs. Administrative scratch flags are not cost-corrected.
- Recompute BE net using recorded gross minus `(fees_bps + slippage_bps) * 2 / 10000 * actual_entry_price / risk_price`, rounded per trade to four decimals. Leave other recorded results unchanged. This estimates omitted modeled costs: 12.3390R all-time and 0.8840R recent.
- This is an in-memory research sensitivity, NOT a ledger migration. No additional costs are applied to already cost-bearing ordinary closes. No funding assumptions, prices, fills, stop behavior or position sizes are invented.
- Profit factor = sum positive economic net / absolute sum negative net. Drawdown = peak-to-trough cumulative realized net in exit-time order from zero starting equity. No account NAV or portfolio percent return is inferred.
- Deduplicate closes by trade ID, verify duplicate counters, filter administrative aliases and TEST records. Snapshot has no conflicts or malformed rows. The all-time cohort mixes historical execution models and is descriptive, not controlled strategy validation.
- No change to cross-strategy loss guard scope, signal thresholds, E29 evidence requirements, Discord gates, or live authority. Risk-scope consistency remains E126 work.

### Unmatched opens at capture

- `1f94fe77-cb4`: ETH SHORT, entered 2026-10-13T11:22:43.819985+00:00, perp_setup_auto_v2_resting_limit; no close in the captured prefix. Not counted as realized P&L.
- `95fb1f42-930`: BTC SHORT, entered 2026-10-13T11:23:04.332775+00:00, perp_setup_auto_v2_resting_limit; no close in the captured prefix. Not counted as realized P&L.

## Implementation files

- `backend/app/api/archive.py`
- `backend/app/services/day_trading_cohort_diagnostics.py`
- `backend/app/services/e26_attribution.py`
- `backend/app/services/e29_forward_scorecard.py`
- `backend/app/services/edge_diagnostics.py`
- `backend/app/services/outcome_research.py`
- `backend/app/services/paper_attribution.py`
- `backend/app/services/paper_execution_cohorts.py`
- `backend/app/services/paper_journal.py`
- `backend/app/services/paper_risk_window.py`
- `backend/app/services/v2_setup_attribution.py`
- `tests/test_quality_dips_v2_operational_closure.py`
- `tests/test_windows_desktop_integration_scripts.py`
- `backend/app/services/paper_accounting.py`
- `tests/test_e125_paper_accounting.py`

## Validation and runtime

Validation results and final runtime/prefix verification are appended below after gates complete. Tests execute in a separate tracked-source copy, without .env or production data. A Python audit hook denies production evidence/credential access and service socket connections; only Python's internal Windows socketpair is permitted. Node source-contract tests run against the copied files.

Initial focused run: 46 failed / 55 passed (test-harness internal socket restriction plus an attribution variable regression, both corrected). A sandboxed rerun stalled on Windows sockets; only the two verified audit test runners were stopped. A later collection check caught an import placement error, corrected before final validation.

First full run: 1691 passed / 2 failed. Both failing lifecycle assertions reproduced on byte-equivalent f61a1f22 checkpoint tests/scripts. They required removed destructive Compose teardown. Tests now enforce exact Atlas dependency names, exact-name lookup, preservation of containers/volumes, and existing Genesis/process-ownership boundaries. Production Windows scripts are unchanged.

Final focused run: 121 passed, zero failed, two dependency deprecation warnings. New accounting helper and test module pass Ruff. No frontend build is necessary because frontend files were unchanged; existing frontend runtime/source contracts remain in the full Python suite.

The running process is NOT hot-upgraded by these source edits. A future operator-controlled Atlas-only restart is required; no restart is performed here.

Final full regression: **1693 passed, zero failed**, two dependency warnings, 43.60 seconds. Tests cover the complete root tests and backend/tests paths. Ruff critical correctness checks (E9/F63/F7/F82) pass across all modified Python files; full configured Ruff passes for the new helper and test module. Existing legacy files were not globally reformatted.

At 2026-10-13T12:04:50.762960Z (07:04:50.762960 CDT), /health returned ok; PID 35616 and run_id 63e6113d-5a6c-4e1f-baf7-4c45d5585388 remained unchanged. The process was created 05:55:36.830009 CDT and has no --reload flag. The 6,724,297-byte historical prefix SHA256 still matched exactly. Journal length grew naturally to 6,726,518 bytes. Both unmatched IDs still had no close recorded. No performance was inferred for them.

No lifecycle script, Docker mutation, Genesis operation, database write, production journal write, or runtime restart was performed. Only audit-owned stalled test runners were terminated. Original journals are untouched; test-generated files are isolated and never staged.

Coverage maps A–E to parametrized ordinary/BE/SCRATCH cost tests; F–H to zero/missing/null tests; I–J to all administrative aliases across consumers and real creation paths; K–M to repeated close, reload/reconciliation and byte-prefix preservation; N to economic totals versus scratch labels; O to isolated strategy aggregation. Additional invalid-string/boolean/NaN/Inf and lifecycle-baseline tests protect the discovered gaps.

**Verdict: E125 implementation GREEN; runtime activation pending a future controlled Atlas-only restart. This is accounting correctness, not profitable-strategy readiness.**

Next: E126 — audit and explicitly define cross-strategy paper risk boundaries and fail-closed behavior for unavailable/invalid accounting evidence, without tuning strategies or rewriting history. The existing UTC-day reader still excludes invalid rows rather than treating them as losses; policy for an incomplete risk window belongs in that execution.
