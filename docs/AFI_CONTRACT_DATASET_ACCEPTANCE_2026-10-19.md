# AFI contract acceptance and dataset-integrity review — October 19, 2026

Decision: **offline synthetic contracts accepted within the scope below; AFI-1 and AFI-2 PENDING; production NO-GO.** No real dataset, trained model, market forecasting performance, calibration, provider permission or activation is accepted.

## Recovered evidence and review scope

Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Reconciled the actual master, AFI register/report/implementation/tests and prior intended-file hashes. Prior evidence supports 262 Python and 21 JavaScript passes. The earlier autonomous report's 727 Python / 21 JavaScript evidence remains historical acceptance, not a new run or whole-project certification. All ten official AFI milestones were and remain PENDING. Current execution began 2026-10-19 14:40:28 UTC (09:40:28 CDT); machine-readable completion time is in result.json.

No live runtime census was performed. No Atlas, Docker, provider, Genesis, PAPER or Discord operation was performed. Isolated tests run from copied backend source with guards against production data/configuration access and live network connections. Native Windows compatibility tests allow only asyncio's internal socketpair setup, not provider connections. No production state, ACL, shortcut, trading authority, cash-scanner behavior or registry changed.

## AFI-1 contract review

| Contract | Finding and verified change | Remaining acceptance |
|---|---|---|
| Asset/session identity | Asset ID must match its explicit class prefix; equity/ETF daily closes use existing 2026–2028 cash calendar, crypto UTC 24/7 closes. Holidays, early close and DST fixtures pass. | Real symbol mappings, unscheduled closures, broader calendars and all other horizon conventions. |
| PIT provenance/revisions | Both observed and available times must be eligible; repeated immutable (asset/source/observed/revision) keys and equally timed conflicts refuse. Late revised records are invisible before publication. | Independent as-published archive truth and custody. |
| Issue/target chronology | Generic declaration validation retained; dataset wrapper binds latest eligible input, declared freshness, 1D next close / 5D fifth close and exact available outcome revision. | 1W/month/year/scenario conventions; actual fitted training history. Unsupported conventions refuse. |
| Versions/fingerprints | Optional manifest hash and dataset version participate in stronger fingerprints and separate cohorts. Legacy absent-field fingerprints remain byte compatible. Code/model hashes remain declarations. | Reproducible model artifacts/seed, real authenticated datasets and execution provenance. |
| Immutable evidence | Inputs are immutable bytes/frozen observations; content and manifest changes detected; existing exclusive holdout publication remains unchanged and regressed. | No durable AFI forecast ledger or independent rollback witness is introduced. Fingerprints alone are not immutable production history. |
| Refusal/corruption | Bounded strict schemas, duplicate JSON keys, invalid/nonfinite values, chronology, hash/count mismatch, malformed nested fields and review substitution refuse. Sparse data is insufficient; real permission declarations stay blocked. | Independent operational acceptance and actual datasets. |

Pre-fix reproducer: three failures demonstrated conflicting asset class acceptance, reused source revision acceptance and absent relative metrics. The original output and before-source copy remain in contract-repro.txt / forecast_evaluation.py.before. All three now pass.

## AFI-2 manifest and technical acceptance

New pure forecast_dataset.py consumes explicit manifest bytes and payload bytes, never opens a dataset path or connects to a provider. Manifest AFI_DATASET_MANIFEST_V1 records dataset ID/version/evidence class; asset/class/currency/timezone/calendar/granularity; source/provider/license ID and hash plus explicit offline permission declaration; acquisition/generation times and observation period; raw content hash/count; append-only revision and as-published availability policy; PIT universe policy; freshness and completeness requirements; price adjustment and dividend convention. Payload AFI_PRICE_RECORDS_V1 contains timestamped raw/value records, explicit LIST/DELIST lifetimes and split/dividend action declarations. Record-level observation/availability dates supply actual time ranges; missingness counts use expected sessions and distinct observations, not revision count.

Bounds: 5,000,000 bytes per input, 10,000 records/actions, 64 assets/universe entries, 10,000 expected observations, 3,660 calendar days, explicit freshness 1–604,800 seconds. No imputation. Histories need at least two observations per asset; declared missing fraction cannot exceed 20%. These are fixture technical bounds, not statistical sufficiency claims.

States:
- ACCEPTED_SYNTHETIC: consistency/quality of supplied fixture declarations only.
- INSUFFICIENT_EVIDENCE: sparse, empty or insufficiently complete synthetic history; cannot be scored through the dataset wrapper.
- BLOCKED_AUTHORIZATION: every HISTORICAL manifest, including DECLARED/UNKNOWN/DENIED permission, until independently verified rights/provenance exist. DENIED is explicitly recorded. No local label or license hash authenticates permission.
- ForecastEvidenceRefused: malformed, unsupported, contradictory, leaking or substituted evidence.

The wrapper revalidates supplied immutable bytes before use, verifies the exact review, content and manifest hashes/version, input price/times and freshness, issue-time membership, explicit session target and exact available outcome source/revision/price/time. A manifest cannot grant authority. Unadjusted prices must equal raw prices; split adjustments require exactly the effective and known-at actions with declared ratio and 1e-12 relative numeric tolerance. Dividend semantics are price return excluding dividends, never total return. Cross-split forecast intervals refuse until economic-unit reconciliation is accepted. Corporate-action and delisting completeness are source declarations requiring independent real-data audit; filenames, hashes and policy labels do not prove them.

## Evaluation and productive offline continuation

Existing metrics remain: MAE/RMSE, directional accuracy (flat distinct), Brier versus uninformative 0.5, interval coverage/width/proper score, bins/ECE, resolved/pending counts and sample thresholds. Added same-sample no-change RMSE, MAPE (% of positive actual), sMAPE (200*absolute error/(absolute predicted+actual)), and MAE/no-change-MAE ratio. A zero baseline denominator yields null, not infinite skill. No error pooling across asset/horizon/model/data/manifest/version/evidence/interval cohorts. Minimum sample count allows diagnostics only; calibration_established, dataset_authenticated, production_approved and trading_authority remain false.

Added an actual selection/holdout declaration auditor, rather than another design-only milestone: exact unique/disjoint exhaustive partitions, labels available strictly before the model-selection freeze, holdout issue times at/after freeze, valid chronology and no future freeze. Purged/embargoed planner tests remain. Deterministic reordering tests pass. This audits declared partitions and timing, not actual fitter behavior or independently unseen holdout custody. No model was fitted and fixture errors are not market-skill evidence.

## Validation

- Initial defect reproduction: 3 expected pre-fix failures, preserved.
- Final evidence/AFI/holdout/prospective regression run: 176 passed, 0 failed/skipped.
- Native Windows provider/cash/research/startup compatibility: 151 passed, 0 failed/skipped.
- Final dataset suite: 64 passed, 0 failed/skipped; 62 overlap the evidence run, two additional fingerprint/cohort tests are new. **329 unique passing Python cases** across final evidence (176), compatibility (151) and two additions. New contract/dataset tests total 67 (64 + 3 reproducer cases).
- Initial focused runs: 107 then 119 passed; superseded, not added to unique totals.
- Sandboxed async compatibility attempt: interrupted after no output; no pass/fail inferred. Original empty output and interruption record retained; native rerun passed. No production service was stopped.
- Targeted Ruff: zero findings in four changed/new Python files. Thirteen initial local style findings (3 import ordering, 10 fixture dict constructors) were adjudicated and corrected only in new files. No waiver or broad cleanup.
- Matched inherited Ruff scope (backend/app, tests, scripts): 4,048 before and after; no introduced/resolved findings. Broader backend/tests scan sees four additional pre-existing findings in two untouched files (I001 x2, PIE807 x2), 4,052 total. Scope difference is not a regression or lint acceptance.
- Four Python files compiled; dependency check clean; Windows PowerShell 5.1 parsed 18 existing launch/checkpoint scripts with zero errors. Git diff checks and roadmap verification are recorded in result.json.
- Checkpoint exact read-back initially caught a Windows-locale/UTF-8 mismatch. Original history was byte-identical; the bad input/publication and backup were preserved. Explicit UTF-8 input and the approved updater corrected it; final exact verification is required and recorded in result.json.
- Prior 21 JavaScript passes were verified, not rerun; no frontend changes. Full canonical Python suite was not run; results above are focused/appropriate regression suites only.

## Exact intended files

1. backend/app/backtest/forecast_evaluation.py — minimal identity/revision/version/metric corrections and selection audit.
2. backend/app/backtest/forecast_dataset.py — new pure manifest and dataset-bound evaluator.
3. tests/test_afi_contract_review.py — retained fault reproducer/regressions.
4. tests/test_afi_dataset_integrity.py — deterministic data, calendar, adjustment, contamination and scoring tests.
5. docs/AFI_MILESTONE_REGISTER.json — verified partial acceptance, blockers and dependencies; all ten PENDING.
6. docs/AFI_INITIATIVE_AND_EVIDENCE_CONTRACTS.md — appended acceptance addendum; original bytes preserved.
7. docs/CONTINUOUS_RUNTIME_ISOLATED_DEVELOPMENT_READINESS_2026-10-19.md — appended current continuity; original bytes preserved.
8. docs/AFI_CONTRACT_DATASET_ACCEPTANCE_2026-10-19.md — this report.
9. PROJECT_ATLAS_MASTER_ROADMAP.txt — managed checkpoint only through approved updater.

Evidence/runner/sandbox/logs, before-copies, manifest of intended hashes and the updater's roadmap backup are retained under logs/diagnostics/afi-contract-20261019 and the recorded backup path. Existing modified/untracked work is preserved. No stage/commit/push/reset/stash/cleanup.

## Existing 21 release decisions — unchanged

| Gate | Existing decision |
|---|---|
| normal_admission | BLOCKED |
| nonclearing_quarantine | PASS |
| full_recovery | BLOCKED |
| backend_current_runtime | BLOCKED |
| complete_shutdown_contract | PASS |
| complete_shutdown_real | NOT_TESTED |
| shortcut_workflow | BLOCKED |
| backup_restore | BLOCKED |
| provider_logical_budget | PASS |
| provider_actual_http_budget | BLOCKED |
| provider_rights | BLOCKED |
| cash_scope | BLOCKED |
| stuck_worker | BLOCKED |
| ruff_disposition | BLOCKED |
| source_artifact | PASS |
| clean_machine | NOT_TESTED |
| gaming_configuration | PASS |
| gaming_performance | NOT_TESTED |
| e136_recovery | BLOCKED |
| discord_delivery | BLOCKED |
| extended_hours_activation | BLOCKED |

The canonical JSON matrix is byte-identical; PASS remains its existing isolated scope, never production activation permission. No gate is reclassified by AFI fixtures. Overall release remains NO-GO.

## AFI roadmap/dependencies and blockers

- AFI-1 PENDING: partial daily-close contracts; broader horizons and independent architecture/provenance/history-contract acceptance remain. Actual model fitting and durable ledger implementation belong to AFI-3 and AFI-7, respectively; they are not circular prerequisites for AFI-1.
- AFI-2 PENDING: manifest validator accepted in isolation; authorized real PIT archives, rights and independently audited universe/actions/quality remain unavailable.
- AFI-3 PENDING: past-only reproducible baseline fitting needs accepted contracts/data; synthetic baseline fitting can be a bounded next workstream.
- AFI-4 PENDING: actual fitting, purged walk-forward, untouched holdout custody and reproducible paired out-of-sample scoring.
- AFI-5 PENDING: sufficient real out-of-sample interval/calibration/scenario evidence; diagnostics are not calibrated acceptance.
- AFI-6 PENDING: asset-specific evidence, units, regimes and comparison following AFI-4/5.
- AFI-7 PENDING: durable immutable forecast/outcome history reusing accepted publication/recovery infrastructure.
- AFI-8 PENDING: read-only dashboard after history/scoring/uncertainty contracts.
- AFI-9 PENDING: long-horizon assumptions, structural-break sensitivity and uncertain bull/base/bear scenarios through 2050; no precise guarantees.
- AFI-10 PENDING: all prior AFI acceptance, independent reproducibility/model risk, existing release gates and explicit activation approval; never automated trading authority.

Real-data acceptance is externally blocked by rights and archive-provenance evidence. No offline implementation can manufacture that evidence. The bounded contract/data/selection/scoring work requested here is complete within synthetic scope. Next safest execution: a small pure past-only no-change/drift baseline fitter using these manifests and actual fit/selection/holdout fault tests on synthetic data; retain real data, calibration and all official milestones PENDING. Do not start another recovery-security framework or activate a service.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

AFI remains permanently registered as Phase 2 Evidence Engine and Phase 4 Cross-Market Intelligence dependent work; all ten milestones are PENDING. The master checkpoint/backup equality, exact read-back and historical-byte verification are in result.json. No fsync/hash/test result is a hardware-failure, full-machine rollback or real-runtime isolation guarantee.
