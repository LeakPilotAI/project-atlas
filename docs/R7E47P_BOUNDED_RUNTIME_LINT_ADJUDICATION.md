# R7E47P — bounded runtime lint correctness/security adjudication

Completed offline bounded batch; **production NO-GO**. 2026-10-18 America/Chicago CDT UTC-05:00. Branch chatgpt/atlas-rebuild-v1, HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e47p-20261018. STOPPED is inherited operator-reported status, not a fresh runtime audit.

## Exact selected findings and pre-change classification

12 original findings: cache3B023+5BLE001, Redis3BLE001+1S110. Chosen for market provenance and resource cleanup risk, not ease. S110 overlaps the already-selected Redis handler and was included when final inventory identified the second resolved diagnostic. Original source copies, selections, baseline and reproducer failures retained. Four diagnostics refer to two defects, not four independent bugs. No automatic Ruff fixes, suppressions or blanket baseline approval.

| Original location | Rule | Classification | Rationale and action |
|---|---|---|---|
| backend/app/adapters/hyperliquid_cache.py:150:29 | B023 | FALSE_POSITIVE | Synchronous local parser never escapes/awaits before loop advances; distinct two-symbol test. Retain without suppression. |
| backend/app/adapters/hyperliquid_cache.py:150:37 | B023 | FALSE_POSITIVE | Synchronous local parser never escapes/awaits before loop advances; distinct two-symbol test. Retain without suppression. |
| backend/app/adapters/hyperliquid_cache.py:152:42 | B023 | FALSE_POSITIVE | Synchronous local parser never escapes/awaits before loop advances; distinct two-symbol test. Retain without suppression. |
| backend/app/adapters/hyperliquid_cache.py:68:12 | BLE001 | MAINTAINABILITY | Silent optional registry-import failure; independent REST/freshness fallback remains valid. Defer diagnostics improvement; no availability policy change or waiver. |
| backend/app/adapters/hyperliquid_cache.py:79:20 | BLE001 | CORRECTNESS_DEFECT | Lookup could select unrelated first exchange dictionary value. Exact hyperliquid dictionary key only; compatibility BLE001 retained. |
| backend/app/adapters/hyperliquid_cache.py:96:16 | BLE001 | INTENTIONAL_PATTERN | Plugin failure logged; fallback boundary preserves cancellation. Retain without suppression or baseline waiver. |
| backend/app/adapters/hyperliquid_cache.py:120:12 | BLE001 | INTENTIONAL_PATTERN | REST failure logged and no rows returned; cancellation propagates. Retain without suppression or baseline waiver. |
| backend/app/adapters/hyperliquid_cache.py:179:12 | BLE001 | INTENTIONAL_PATTERN | Malformed parsing logged and returns no rows, tested. Retain without suppression or baseline waiver. |
| backend/app/core/redis.py:41:16 | BLE001 | CORRECTNESS_DEFECT | Both close methods failing discarded ownership and falsely logged success. Retain reference, log only exception type names, raise chained error; inner BLE001 and S110 resolved, outer compatibility BLE001 retained. |
| backend/app/core/redis.py:44:20 | BLE001 | CORRECTNESS_DEFECT | Both close methods failing discarded ownership and falsely logged success. Retain reference, log only exception type names, raise chained error; inner BLE001 and S110 resolved, outer compatibility BLE001 retained. |
| backend/app/core/redis.py:61:12 | BLE001 | INTENTIONAL_PATTERN | Optional lazy Redis contract returns None; callers need separate review. Retain without suppression or baseline waiver. |
| backend/app/core/redis.py:44:13 | S110 | CORRECTNESS_DEFECT | Both close methods failing discarded ownership and falsely logged success. Retain reference, log only exception type names, raise chained error; inner BLE001 and S110 resolved, outer compatibility BLE001 retained. |

## Minimal corrections

backend/app/core/redis.py: both-close failure retains the owned client, logs exception types only, and raises fallback error chained from primary error. No false client-closed log. Primary success and successful legacy fallback still clear ownership; repeated successful close is idempotent. Cancellation propagates and ownership is retained; failed cleanup can be retried.

backend/app/adapters/hyperliquid_cache.py: legacy dictionary lookup accepts only hyperliquid, not the first unrelated adapter. Missing adapter returns no rows for unchanged independent REST/freshness fallback. Existing get/get_adapter/require compatibility unchanged. No certification of arbitrary malicious plugin implementations.

Added tests/test_r7e47p_redis_cleanup.py(6 cases) and tests/test_r7e47p_cache_adjudication.py(5 cases). All HTTP,Redis and adapter fixtures fake. Cache two-symbol test demonstrates synchronous loop closure safety; malformed universe refuses rows; cancellation propagates; foreign dictionary adapter never queried; exact legacy adapter remains supported.

## Validation

Original Redis reproducer2failed4passed0.44s; cache1failed4passed0.54s, retained in original-confirmed.txt/original-cache-confirmed.txt. Final focused provider/cash/activation/Gaming/repair suite147passed0failed0skips15.34s. Isolated S/T/V lifecycle82passed0failed0skips37.58s. **Final non-overlapping229passed,0failed,0skips,0xfail**. Intermediate145pass not added. E136 expected-failure suite not rerun; historical blockers unchanged. No full-canonical-suite claim.

Sandboxed pytest attempts produced no output and were canceled through their exact tool sessions. Final authorized tests ran outside sandbox in source-only isolated extraction with production data/.env and outbound socket guards. No service process signaled. A read-only own-test CIM diagnostic was denied; no runtime inference or further process audit. Failures/empty stalled logs preserved. Four changed/new files hash-match isolated tested copies.

Ruff O baseline3997 ->3995, resolved2 (inner RedisBLE001,S110), new0 by file/rule/message multiset, not exact-line ancestry. Remaining3970HEAD-inherited+25later-inherited;489correctness,478security-policy,3028style. Whole-tree Ruff still fails. New-test targeted Ruff passes. Redis targetedBLE001 retains2 documented warnings; cache retains5BLE001+3B023. Initial inventory detected2I001 imports in new tests; corrected those imports only, intermediate raw evidence retained. No waiver for retained warnings.

Four changed/new Python files compiled without product pyc. Windows PowerShell5.1 parsed18scripts0errors. Git diff integrity passes with pre-existing newline warnings. O987manifest files checked before matrix/checkpoint update: only the2intended runtime modules differed. No dependencies/config/PAPER/Discord/provider pacing/cashC1-C4/startup/recovery/Windows behavior edits.

## Limits and release-gate disposition

main.py still ignores close_redis errors at the broader lifespan boundary. This batch establishes client-local truthful failure/ownership, not whole-lifecycle success. Higher-level shutdown truthfulness and coherent20s+20sdrains versus30smanager wait need separate bounded adjudication. No new lifecycle or production integration approved.

Existing authoritative R7E47O_PHASE1_RELEASE_GATE_MATRIX.json updated only for lint evidence/criteria plus latest-review metadata. All21identities/statuses/prior evidence and20unrelated gate objects preserved. **5scopedPASS,13BLOCKED,3NOT_TESTED**. Source-artifactPASS refers to O historical artifact only; it does not package P changes. Refresh required before a future release artifact gate.

| Gate | Status |
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

## Next execution and permanent boundaries

Recommend separately authorized R7E47Q: bounded shutdown error propagation and whole-lifecycle drain-budget adjudication, limited main/Redis/dispose handlers and existing stop-budget contracts, isolated failing reproducers before correction. No real lifecycle. CashC1-C4 decision remains independent. Stop after P.

Required checkpoint updater only; final result.json verifies original backup equality, exact read-back and byte-identical outside-managed history plus permanent strategy/recovery/PM-V2 anchors. No Atlas/Docker lifecycle, provider requests, real-volume/helper/DB/backup/restoration, Genesis, protected config/registry/ACL/shortcut, trading/Discord, Git staging/commit/push/reset/delete or VPS. PAPER_ONLY/MANUAL_ONLY, Gaming efficiency and normal PAPER cadence unchanged.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

