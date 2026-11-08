# R7E46V — Complete Shutdown inspection compatibility repair

**Isolated repair and read-only inspection compatibility VERIFIED; production release NO-GO. No real lifecycle acceptance or production activation.** October 18, 2026 America/Chicago (CDT UTC−05). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0 unchanged. Read permanent master checkpoint and T/U ownership, shutdown/recovery and backup contracts; preserve all historical evidence.

## Root causes and minimal repair

1. Docker Go templates use missing-key failure semantics for direct .Config.StopSignal. Redis legitimately omits this optional image/container field. The unchanged production template failed with map has no entry for key StopSignal against the same verified full Redis ID; original-repro output/exit and source snapshot are retained.
2. Once that lookup rendered safely, real native inspection exposed a missing outer JSON closing brace. The initial repaired native output was malformed JSON even for PostgreSQL. Raw stdout/stderr and intermediate source are retained; an independent deterministic JSON-framing test reproduced the delimiter failure before repair.
3. Optional-field validation cast non-string types before checking them: numeric15 and a one-element string array could become accepted strings. The repair rejects non-null, non-string values before the existing strict signal allowlist. Direct assignment preserves array types instead of allowing conditional-expression pipeline flattening. Hashtable and persisted-object representations receive equivalent strict validation.

Source changes are limited to scripts/windows/Atlas-CompleteShutdown.ps1 (null-safe index for StopSignal and closing JSON delimiter) and scripts/windows/Atlas-CompleteShutdown.psm1 (strict optional field presence/type handling). tests/test_r7e46v_inspection_compatibility.py adds deterministic adapter/policy, malformed-type and framing contracts. Shutdown ordering, signals/allowlist policy, deadlines, intent persistence, receipt/replay/recovery, PID/run ownership and startup restoration are unchanged.

## Audit of other fields

Only StopSignal is optional in the emitted production container projection. Id/Name, Config/Labels and State.Running/Status are required for safe identity/state verification; they remain mandatory and fail closed if absent/malformed. Individual required Compose labels use index but return null or fail on invalid parents; the identity verifier still rejects missing project/service/root/single configuration/non-oneoff evidence. Do not make required identity fields optional or infer ownership from names.

Health, networks, image labels and diagnostic-only fields are not emitted by this production projection and were not added as mandatory shutdown dependencies. Context endpoint is required for selecting a trusted local daemon, not an optional fallback. Unknown/unsafe signal strings still reject; missing/null/empty signals retain Docker's existing default behavior without substituting a new signal or weakening IDs.

## Regression and failure evidence

- Original synthetic candidate: 3 failed / 15 passed (numeric and array coercion plus null-safe projection contract).
- Independent framing reproducer: 1 failed as expected, demonstrating incomplete JSON; not counted as a successful acceptance.
- Intermediate broader candidate: 162 passed / 2 failed; array preservation and its dictionary fixture were corrected. Its broader run had 2,366 passed / 4 failed / 3 inherited xfailed: the two array cases plus two multiprocessing lock tests whose spawned children exited through a diagnostic runner guard installed after the parent had started. Captured stdout identifies that harness-only cause. The final unmodified-isolation runner removes that guard and reruns all tests; no lock implementation was changed. All raw logs remain preserved.
- Final focused: 164 passed in 76.43s. Final canonical full: 2,370 passed, 3 inherited E136 xfailed, 0 failed, 2 dependency warnings in 171.35s. All 759 manifested Python files compile; 18 Windows PS5.1 scripts parse with 0 errors; pip consistency/diff checks pass. Ruff 3,997, 0 new / 0 resolved since R; no waiver. Exact evidence is in result.json. Passing these checks is not production approval.

Deterministic tests invoke the actual inspection function and pure shutdown policy with synthetic replies. They cover optional missing/null/empty/valid values, malformed number/array/Boolean/object and unsafe signals, all required label omissions, full-ID mismatch, already-exited services and Engine unavailability. Existing T/S regressions cover replacements, backend session changes, partial/uncertain requests, restart gates, concurrent controllers and no-replay. The framing test replaces JSON-valued template actions with null to validate the literal envelope; it is not a substitute Go interpreter. Actual Docker rendering/native quoting is independently checked read-only below.

## Read-only Docker acceptance

Docker Engine 29.8.1 accessible at the verified local Linux named pipe. Before edits, exact name discoveries were checked against the prior U IDs/images/root/config/project/service/nononeoff evidence and both exited states. No identity change occurred. The actual production Invoke-AtlasDockerCommand/Get-CompleteContainer function declarations were extracted without executing the Complete script's top-level entry point. Only inspect was invoked, both by exact names and full IDs, under Windows PowerShell 5.1. The parsed metadata passed strict ConvertTo-AtlasShutdownIdentity verification.

- PG ID:c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1, projectatlas/postgres, StopSignal SIGINT, exited.
- Redis ID:13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193, projectatlas/redis, StopSignal null, exited.

All native inspection CLIs exited; no Complete receipt or stop request was created. Named/full-ID consistency is point-in-time evidence, not permission to operate later without revalidation. No global inventories, unrelated/Genesis resources, Docker lifecycle commands, database/secret/backup contents, exec or provider calls were involved.

## Persistence, backup and activation hold

Preserve docs/R7E46U_RETRY_BACKUP_CREATION_RESTORE_PLAN.md byte-for-byte. Actual named mounts and declared paths were verified in U; effective PG config/WAL/tablespace and Redis save/AOF behavior, persistence integrity, usable independent backup provenance and isolated restore validation remain unaccepted. V creates/restores no backup and starts no database. A read-only parsed inspect cannot establish durable data or graceful shutdown/restore.

Still required: separate approval for cold read-only-source backups under verified writer quiescence and confidential manifests; separate scratch-only restore validation with compatible pinned images/no production mounts/network and approved data/credential access; independent results and reviewed recovery contract. Only then seek explicit bounded Stage B approval. No implicit scratch cleanup/deletion, production restore, backend Gaming startup or shortcut installation is authorized.

## Gate decision and safest next milestone

Inspection optional-field/native JSON compatibility may pass only to final verified tests/read-only evidence. Production remains NO-GO. Keep cash C1-C4 scope, provider rights/HTTP budget, stuck-worker operational acceptance, Ruff policy, clean-machine/runtime/Gaming resources/cadence, real shutdown/persistence/restore, desktop migration, E136/Discord consent and PM-V2 gates unchanged. Full gate matrix: gate-matrix.json in the V evidence directory.

Next safest milestone: separately approved backup-creation preparation/execution scope from the existing U plan, followed by separately approved isolated restoration validation. If payload reading/helper creation/access is not approved or source quiescence/config coverage is unknown, remain blocked. Do not execute Stage B, start production or change shortcuts automatically.

Evidence directory: `logs/diagnostics/r7e46v-20261018-005513`. Mandatory roadmap verification and final archive hashes are recorded in result.json.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Core current obligations: close V inspection compatibility using exact final evidence, then establish effective persistence and independently restorable backup provenance before separate Stage B/shortcut approvals.
