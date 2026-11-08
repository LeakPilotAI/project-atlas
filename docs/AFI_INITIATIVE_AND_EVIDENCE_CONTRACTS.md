# ATLAS FORECAST INTELLIGENCE — permanent initiative and evidence contracts

Registered October 19, 2026. **All ten official milestones are PENDING; production NO-GO.** Offline scaffolding below is implemented and tested in isolation; it does not complete a model, dataset, immutable production history, calibration acceptance or activation gate.

AFI is Atlas's future evidence-backed multi-market forecasting initiative. Prioritize U.S. equities, then ETFs, then cryptocurrencies. Additional markets require appropriate datasets, rights and validation. It grants no live/PAPER/Discord or automated trading authority. Existing production startup protection and all 21 release decisions remain intact.

Forecast horizons: 1 day, 5 days, 1 week; 1, 3 and 6 months; 1 year and 5 years; conditional scenario milestones through 2030, 2040 and 2050. Long-horizon outputs must be uncertain bull/base/bear scenarios with assumptions and structural-break risk, never precise or guaranteed predictions. Five trading sessions and one calendar week cannot be conflated. Future asset-specific calendar/version policies must define targets, close conventions, holidays, corporate actions and crypto 24/7 semantics. The existing 2026–2028 calendar does not establish dates through 2050. The prototype only validates explicit target chronology and labels its horizon semantics caller-declared/unverified.

## Official milestone register

| ID | Milestone | Status | Minimum acceptance |
|---|---|---|---|
| AFI-1 | Forecast architecture and evidence contracts | PENDING | Reviewed versioned forecast/data/outcome schemas, horizon/calendar conventions, provenance and refusal contracts, threat boundaries and no-trading invariants; independent acceptance required. |
| AFI-2 | Historical datasets and point-in-time integrity | PENDING | Authorized point-in-time source datasets, as-published revisions, splits/dividends/delistings/universe/currency metadata, known-at provenance, hashes, completeness and freshness audits. |
| AFI-3 | Baseline statistical forecasting models | PENDING | Reproducible naive/statistical baselines fitted only to eligible past data, asset/horizon-specific protocols and tests; no inferred entitlement or predictive edge. |
| AFI-4 | Walk-forward backtesting and forecast scoring | PENDING | Purged walk-forward training/validation/untouched holdout, declared embargo, reproducible paired baseline comparisons, missing-outcome accounting and out-of-sample scoring. |
| AFI-5 | Calibrated uncertainty and scenario modeling | PENDING | Calibrated interval coverage, uncertainty/error diagnostics and bull/base/bear scenarios using adequate real out-of-sample evidence; scenario assumptions and failure modes explicit. |
| AFI-6 | Multi-market forecast comparison | PENDING | Separate equity/ETF/crypto and horizon/model/data cohorts, unit-aware normalized comparisons, regime/selection-bias controls and evidence attribution. |
| AFI-7 | Forecast history, accountability, and diagnostics | PENDING | Reuse immutable evidence/versioned artifact infrastructure; durable forecast IDs and fingerprints, actual-versus-predicted outcomes, corrections with provenance, no historical rewriting and independent recovery acceptance. |
| AFI-8 | Frontend forecast dashboard | PENDING | Read-only forecast dashboard with provenance/as-of timestamps, sample-size warnings, interval/scenario displays and unavailable/insufficient-evidence states; no execution controls. |
| AFI-9 | Long-horizon scenario research through 2050 | PENDING | Conditional long-horizon scenarios through 2030/2040/2050 with uncertainty, structural breaks, assumption sensitivity and no false precision or guaranteed prices. |
| AFI-10 | Independent acceptance and controlled activation readiness | PENDING | Independent reproducibility, licensing/security/reliability/model-risk review and controlled activation plan; all existing gates plus explicit operator approval; no automated trading authority. |

Machine-readable source: AFI_MILESTONE_REGISTER.json. Permanent authority: the AFI block in PROJECT_ATLAS_MASTER_ROADMAP.txt. Do not silently promote PENDING from synthetic tests, and do not alter old roadmap decisions.

## Reuse and dependencies

Phase 2 Evidence Engine provides immutable timestamped hypotheses, actual outcomes, replay and leakage/calibration controls. Phase 4 Cross-Market Intelligence provides asset-specific comparison and attribution. Reuse backtest/historical.py, existing holdout build/freeze/evaluation, investment/prospective_evidence.py, prospective outcomes/reporting and established presentation/capability contracts. No parallel collector, registry, database, journal schema or startup service is introduced.

Existing retrospective PAPER replays are not price-forecast outcomes. Existing prospective valuation-band coverage is not a calibrated forecast distribution. Keep semantics distinct while sharing appropriate infrastructure. Actual immutable forecast recording and production durability remain AFI-7 work; a hash alone is not an independently witnessed immutable history.

## Implemented offline groundwork

backend/app/backtest/forecast_evaluation.py is a pure utility with no providers, I/O, startup hooks, trading API or journal writes.

- Observation records bind asset class/identity, source/revision, observed_at, available_at and value. select_asof admits only records observed and available by the requested cutoff, selects the latest eligible revision and checks explicit max_age. Duplicated identities, equally timed ambiguity, impossible availability or malformed data refuse; missing/future/stale observations return INSUFFICIENT_EVIDENCE. Availability is caller-declared, not authenticated.
- Forecast records include issue/target, declared training/input availability, reference/point, model/version, dataset/code hashes and evidence class. Future training/input declarations, invalid probabilities/intervals and contradictory metadata refuse. Frozen dataclasses and canonical fingerprints enable reproducible identity checks; no storage durability or administrator/rollback protection is implied.
- ReplayWindow and walk_forward_plan produce only expanding chronological train/test IDs. Labels/targets must be strictly earlier than the embargo cutoff; missing label availability never trains. Overlap, duplicate IDs and too-small folds are explicit. Planning is capped at 128 folds; no model is fitted and no production permission follows. This does not prove that a later feature fitter avoids leakage or that a real universe is survivorship-free.
- score_forecasts compares only mature, available, exact-target outcomes. Missing/unavailable outcomes stay pending rather than becoming zero error. Duplicate IDs and repeated logical forecast cases refuse. Asset, asset class, horizon, model/version, dataset/code revision, nominal interval and evidence class remain separate cohorts.
- Diagnostics include MAE/RMSE, paired no-change MAE, directional accuracy, probability Brier score against a 0.5 uninformative baseline, empirical calibration bins/ECE, interval coverage/width/proper interval score and sample counts. The binary event is price strictly above reference; flat outcomes are NOT_UP for Brier and a separate FLAT direction for directional accuracy. These distinct definitions are disclosed.
- Minimum sample count defaults to 20 (configurable integer >=2). Meeting it permits DIAGNOSTIC_ONLY, never calibrated/production-ready. Bin counts and small-sample warnings remain. Synthetic/HISTORICAL/PROSPECTIVE labels are separated, but labels/hashes are declarations and do not authenticate datasets. calibration_established, dataset_authenticated, production_approved and trading_authority remain false.

## Targeted reliability repair

The existing holdout freezer now parses and hashes the same source bytes, rejects malformed/non-finite measured counts/returns, creates output exclusively, preserves conflicting/partial output and does not rewrite identical existing evidence. Existing numeric serialization and legacy Windows CRLF artifacts remain compatible without rewriting old bytes; mixed or conflicting artifact bytes refuse. It reuses core/durable_io.py for full write/flush/fsync and supported parent sync. On Windows replay revalidation needs an r+b descriptor for fsync but performs no data write; denied permissions or sync failure do not acknowledge success.

A failed write may leave partial evidence; it is preserved and a conflicting retry refuses. A complete but previously unsynced artifact can only be reacknowledged after fresh successful sync. This is file durability acknowledgement, not independent recovery authority, database backup, crash-atomic multi-file publication, full-machine rollback resistance or Windows namespace/power-loss certification. External/privileged mutation and filesystem substitution are not solved here.

## Admission and refusal policy

No real provider access, production startup, model deployment, PAPER execution or Discord follows from this initiative. All existing rights/budget, cash scope, recovery, backup/restoration, Gaming resource, packaging, lint and E136 gates remain. Missing point-in-time datasets, adjusted/unadjusted/currency policy, verified target calendars, source authentication, model artifacts/seed, selection-bias audit and independent out-of-sample history are blockers to substantive model acceptance.

## Next bounded execution

Use the authorized dataset manifest/provenance contract and independent AFI-1 review before ingesting or fitting any real historical data. No live-provider request is authorized. AFI-2 needs exact source rights, point-in-time availability/revision and universe/corporate-action coverage. Do not invent them from synthetic fixtures. Continue generic offline source fixes only when a measured defect has a bounded reproducer; avoid broad Ruff cleanup or another recovery-security redesign.


## October 19 contract and dataset acceptance addendum

See AFI_CONTRACT_DATASET_ACCEPTANCE_2026-10-19.md for the current evidence-backed review. The earlier prototype description is historical; its generic scorer still labels calendar semantics unverified. The new forecast_dataset.py wrapper verifies explicit daily-close 1D/5D fixture conventions using the existing cash calendar and a separate UTC crypto calendar. Other horizons and cross-split forecasts refuse. No cash scanner or provider service changed.

Asset-class prefixes and immutable source revision identities now fail closed. Optional manifest SHA-256 and dataset version bind stronger forecast fingerprints and cohorts; legacy fingerprints omit absent optional fields. Relative errors, paired no-change RMSE/MAE ratio and an explicit selection/holdout freeze declaration audit are implemented. None proves fitting provenance, untouched holdout custody, real skill or calibration.

Dataset manifests validate exact bytes, source/license declarations, acquisition/availability, sessions, revisions, explicit universe lifetimes, quality, split/dividend price conventions and bounds. Only synthetic fixtures can be technically accepted. Every historical dataset remains BLOCKED_AUTHORIZATION; declarations and hashes do not authenticate rights or archive truth. Sparse fixtures remain INSUFFICIENT_EVIDENCE. AFI-1 and AFI-2 remain PENDING with exact remaining acceptance in AFI_MILESTONE_REGISTER.json. AFI-3 through AFI-10 remain PENDING. The permanent master, 21 gates and production startup denial retain authority.


## Autonomous offline implementation continuation - October 19

The permanent AUTONOMOUS DEVELOPMENT AND CONTINUATION PROTOCOL now governs eligible offline work between milestones. See AUTONOMOUS_CONTINUATION_2026-10-19.md and its machine-readable session evidence for baseline fitting, actual replay/frozen holdout, interval diagnostics, explicit outcome vintages, exclusive forecast artifacts, comparison/scenarios and standalone dashboard/CLI. All ten official milestones remain PENDING, all 21 production gates unchanged and production NO-GO. These scoped implementations do not establish real-data skill, archive rights, calibrated coverage, immutable production history, independent custody or operational acceptance.
