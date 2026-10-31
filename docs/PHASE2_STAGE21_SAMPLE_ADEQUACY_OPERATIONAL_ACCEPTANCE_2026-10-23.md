# Stage 21 — sample adequacy, statistical intervals, and offline storage gate

Decision: **Phase 2 HOLD; Phase 3 blocked; production NO-GO.** All 21 release decisions and the production startup lock remain unchanged. AFI-1 through AFI-10 remain officially PENDING. No real forecast skill, calibration, provider entitlement, database backup, restoration, or production runtime acceptance is established.

## Bounded adequacy contract

`forecast_sample_adequacy.assess_holdout_sample` consumes the Stage 20 committed offline holdout plan without changing V1/V2 report bytes. It validates the plan commitment, exact partition membership and counts, freeze/issue chronology, forecast identity, asset/source/model/dataset cohort fields, window/outcome state, and mature-case count. It refuses duplicate forecast identities and repeated asset/source/target observations even across models and horizons. It counts eligible, excluded and distinct observations; records exclusion reasons, source/asset/horizon/model concentration, and overlapping issue-to-target windows for each asset/source. It does **not** derive an effective independent sample size from these counts. It reports `effective_sample_n: null`, `independent_samples_established: false`, `sample_minimum_approved: false`, and zero authoritative scores. No binding sample threshold was found in the AFI acceptance contract; existing 20-case scoring defaults are descriptive software gates, not approved statistical adequacy criteria.

An optional exact mapping of eligible forecast identities to synthetic Boolean outcomes produces a conventional Wilson 95% **assumption-bound sensitivity interval** only with at least two cases, at least two assets, one exact horizon/source/model/version/configuration/dataset stratum, and no structurally overlapping windows. Empty/tiny, single-asset, cross-stratum or overlapping sets receive no interval. Even when calculated, the interval does not prove Bernoulli independence: common market shocks, correlation across assets, revisions, adaptive selection and unobserved source dependence remain untested. This is neither a calibration interval nor a significance test. Fixed ten-bin probability diagnostics and paired interval score/coverage already exist in `forecast_report.py`; binomial intervals on sparse calibration bins or naive case-level bootstrap would imply unsupported precision. Cluster/block resampling, bin uncertainty, significance and nominal interval coverage acceptance require a frozen analysis protocol and independently witnessed out-of-sample outcomes. Missing, partial, contradictory, future-dated or unauthenticated cases never enter the optional denominator.

Synthetic adversarial coverage includes empty and tiny eligible sets, overlapping same-asset windows, repeated targets, single-asset dominance, missing outcomes, cohort/horizon separation, invalid source or partition, non-Boolean/nonfinite hit declarations, commitment mismatch and deterministic interval reconstruction. The Stage 20 real plan shape is exercised directly. Initial syntax/indentation and status-contract failures were corrected before the final regression; original command output remains in this task record.

## Windows-local operational acceptance

The highest-priority safe storage action available without service or payload authorization was an independent **read-only checkpoint-backup integrity check**. The Stage 20 `roadmap-before.bin` and updater `.bak` both SHA-256 `61207d0b33c013c19f184b7633479c45f33ac1466cdab6e32256042c309d9536`; current roadmap before Stage 21 SHA-256 was `34c347921391c2c96e2cf6343cb79658e1ad3687b383cf0873de2faa98e9e87d`. Existing checkpoint evidence records exact managed readback and byte-identical content outside that section. This only verifies the roadmap copy, not a PostgreSQL/Redis or host-evidence backup.

The existing R7E46W synthetic cold-backup contract was rerun without touching production storage: **21 passed, one Windows hard-link marker case failed** with the previously documented sandbox `WinError 5 AccessDenied`; a scoped rerun excluding that case passed **21 with one deselected**. The failure is retained, not waived. The synthetic marker never constituted a usable real backup. The 21-gate `backup_restore` decision remains BLOCKED: exact source-volume coverage, maintained writer exclusion, protected destination/encryption/key custody, archive hashes, independently verified manifest and separately approved disposable restoration are still required. No real database contents, volumes, backup payloads or protected journals were accessed.

## AFI closure state

| Initiative | Implementation and local test | Independent witness / external dependency | Official status |
|---|---|---|---|
| AFI-1 contracts | Source/time/refusal, holdout and bounded sample contract tested | Independent evidence/security review | PENDING |
| AFI-2 PIT data | Synthetic manifests and issue-time controls tested | Licensed vintages, rights, provider publication/receipt witness, universe/actions completeness | PENDING |
| AFI-3 baselines | Deterministic synthetic baselines tested | Frozen model protocol on authorized untouched data | PENDING |
| AFI-4 walk-forward | Replay, exclusions and holdout adequacy diagnostics tested | Independent unseen holdout, approved minimum and skill review | PENDING |
| AFI-5 uncertainty | Nominal intervals, descriptive coverage and assumption-bound Wilson sensitivity tested | Approved cohort-specific method and witnessed calibration/coverage | PENDING |
| AFI-6 multi-market | Equity/ETF/crypto synthetic cohort isolation tested | Comparable licensed sources and independent samples | PENDING |
| AFI-7 history | Immutable local ancestry and correction chronology tested | Independently witnessed completeness and corrections | PENDING |
| AFI-8 viewer | Scriptless/offline read-only exports and retained V1 bytes tested | Native browser acceptance and display rights | PENDING |
| AFI-9 long horizon | Scenario research contract present | Reviewed assumptions, regimes and uncertainty | PENDING |
| AFI-10 acceptance | Startup denial and release matrix retained | All preceding plus runtime, storage, PAPER policy and operator decisions | PENDING |

No milestone has an independent witness or formal acceptance here. The next safe Phase 2 action is to obtain an authorized, independently witnessed PIT vintage and correction/receipt chain for AFI-2/7, then validate its declared chronology and rights with a separately trusted verifier. If unavailable, continue narrowly scoped offline failure-mode and packaging work without scoring an unwitnessed holdout. Phase 3 entry remains blocked.
