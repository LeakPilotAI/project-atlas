# R7E46T — independent Complete Shutdown ownership/recovery review

Outcome: source review and isolated repair/acceptance preparation; **production release NO-GO**. Real Complete Shutdown, Docker restoration and desktop migration remain unaccepted/unapproved. October 17, 2026, America/Chicago (CDT UTC−05); exact UTC observation timestamps are retained in diagnostic JSON. Branch chatgpt/atlas-rebuild-v1, HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0 unchanged.

## Independent findings and scoped fixes

S passing tests were treated as historical evidence, not operational certification. New synthetic callback tests were run against unchanged S code first: 7 failed, 2 passed (repro2.log). The initial runner-path setup failure is separately retained in repro.log. No real service was involved.

| Finding | Before | T repair / evidence |
|---|---|---|
| Completed receipt identity fence | Repeat complete shutdown ignored retained IDs when prior state was COMPLETE, allowing a replacement with matching labels | Compare retained dependency IDs/root for completed as well as incomplete receipts; reject before any stop |
| Final whole-pair evidence | PG could restart, or a formerly absent PG could appear, while Redis drains; earlier observations could yield COMPLETE | Reinspect both names/IDs after all operations; reject additions/replacements and report any restarted service as incomplete |
| Accepted but unconfirmed stop | Successful CLI cleared intent before actual exit; later invocation could replay a request while the ID remained running | Keep durable intent until exact-ID inspection confirms exit; accepted-but-running requests remain pending and are never automatically replayed |
| Backend state reporting | Final backend ownership failure could leave reported backend_state=STOPPED | Capture actual final status before rejection; no false final stopped claim |
| Persisted exit flag coercion | PowerShell accepted string true / numeric 1 as confirmed exit | Require actual Boolean exit evidence; reject malformed prior and completed receipts without changing them |
| Session change during preflight | Policy bound stop to the second status rather than the initially observed session | Require initial valid run GUID and refuse a newly appeared/different session before backend stop; isolated interleavings cover running/stopping/stopped |
| Startup parser asymmetry | Restoration parser lacked full-ID/oneoff/Boolean/status coherence validation; string false could coerce to true | Tighten shared ownership parser; verify full ID, non-oneoff and exact consistent process state. Update old identity fixture with real required fields; no weaker assertions |

Changed runtime source: scripts/windows/Atlas-CompleteShutdown.psm1 and scripts/windows/Atlas-ContainerOwnership.psm1. Added tests/test_r7e46t_shutdown_review.py and updated required metadata in tests/test_e128_background_mode.py. No cash/provider/PAPER authority/config/Compose/shortcut source was changed. New test import formatting was corrected only in the new file; no broad lint cleanup or policy waiver.

## Confirmed source guarantees and limits

Exact root/config/service/project labels and full IDs fence the two permitted dependencies; pair project conflict rejects before any stop. The root mutex excludes competing supported controllers, and strict run/PID/creation/executable/command checks remain intact. Backend exit precedes dependency requests; unavailable/foreign/malformed state fails closed. Stop uses infinite grace, bounded owned-CLI observation and no kill/removal/destructive Docker command. Already-stopped/absent cases remain idempotent. Journal/database/volume deletion is absent. Durable pending intents and preserved receipt versions block uncertain replay and startup.

Real signal delivery, save/checkpoint completion, mounts/persistence, permissions, CLI/daemon interruption and clean-machine behavior are NOT certified by mocks. The mutex does not fence external Docker administrators. Docker labels are operational provenance, not cryptographic protection against a privileged daemon user. Final inspection is point-in-time evidence; receipt loss/corruption requires forensic recovery, never deletion/bypass. Image defaults and mounted volumes do not prove data durability. PG smart/fast versus immediate shutdown and Redis persistence/save failures are covered in the primary-source acceptance plan, not inferred from source tests.

Startup review: verified manager checks the completed receipt, rejects incomplete/pending receipts, requires the same retained IDs, pins the local endpoint, starts existing dependencies by immutable IDs, verifies both healthy before API. No Engine/Desktop management occurs. PG and Redis have no Compose depends_on relation. First installation when both are absent is a separate creation path; partial missing/replaced retained services fail closed. A stale owner/lock is never cured by unused port evidence or receipt deletion. Supported Status can reconcile conclusively dead metadata; do not invoke it blindly against ambiguous records. T runtime directory had no active JSON lifecycle records before supported status; before/final status observations are retained.

## Operator preparation

- docs/R7E46T_SHORTCUT_MIGRATION_PLAN.md records exact existing links, proposed manager/Gaming/backend-only/explicit Complete targets, approval choices, metadata-only candidate review, per-link backup and rollback. No shortcut changed; no legacy script executed.
- docs/R7E46T_REAL_CONTAINER_ACCEPTANCE_PLAN.md separates read-only identity/mount/image/health evidence from explicit stop/restore/backend approvals, backup and persistence gates, failure criteria and non-destructive recovery. A container-only trial cannot certify a running API/PAPER drain.

## Updated release-gate matrix

| Gate | Status | Evidence / next requirement | Approval |
|---|---|---|---|
| Cash C1-C4 scope | BLOCKED | R7E46S_CASH_SCOPE_DECISION.md; existing reliability tests; Explicit operator acceptance or separately scoped remediation | Required |
| Provider logical pacing/cancellation/drain | PASS | R7E46R reports and isolated provider suites; Retain bounded queues, deadlines and uncertain-worker safeguards | No source approval; production remains gated |
| Provider rights and actual HTTP capacity | BLOCKED | R7E46S_PROVIDER_ACCEPTANCE.md; official RHJ/Yahoo documents; Verify entitlement, classic quote limits and Yahoo internal HTTP budget | Required |
| Journal integrity and migration design | PASS | R7E46O_JOURNAL_MIGRATION_RECOVERY.md; adversarial regressions; Production migration remains separately gated | Required |
| Feature flag/Gaming isolation | PASS | R7E46M contracts and Gaming inheritance regressions; Actual environment requires separately authorized runtime acceptance | No source approval; production remains gated |
| Ruff policy | BLOCKED | R7E46S_RUFF_DISPOSITION.md; lint-final inventory; 3997 findings require remediation or explicit reviewed baseline | Required |
| Reproducible complete artifact | PASS | T extracted source hashes and final reproducible artifact evidence in result.json; Keep historical S artifacts; T repair supersedes their lifecycle source, not their historical results | No source approval; production remains gated |
| Complete shutdown isolated contracts | PASS | R7E46T seven failing adversarial reproductions retained; repaired tests and final isolated lifecycle suite; Keep opt-in; require real engine/IDs/mount/persistence/runtime acceptance before installation | No source approval; production remains gated |
| Complete shutdown real Docker acceptance | NOT TESTED | T exact-name read-only inspection: local dockerDesktopLinuxEngine pipe unavailable; Explicit approval and all steps in R7E46T_REAL_CONTAINER_ACCEPTANCE_PLAN.md | Required |
| Desktop Stop workflow | BLOCKED | T read-only shortcut metadata unchanged; legacy blocked stopper and misleading batch; Explicit names/targets/workflow approval per R7E46T_SHORTCUT_MIGRATION_PLAN.md | Required |
| Windows clean-machine portability | NOT TESTED | Observed requirements/dependencies; Windows PS5.1 parser; Clean Windows dependency/install and Docker identity acceptance | Required |
| Production activation/rollback | BLOCKED | No activation approval; cash/provider/lint/runtime gates unresolved; Approved bounded Gaming/live-data/disabled rollback plan only after gates | Required |
| E136 independent recovery witnesses | BLOCKED | Three inherited xfails retained; Independent witness, dual rollback and atomic recovery acceptance | No source approval; production remains gated |
| Stuck-worker operational acceptance | BLOCKED | R worker ownership/drain design; no hard deadline for permanently blocked thread; Explicit operational decision or separately scoped cancellable transport | Required |
| Gaming resource and actual cadence | NOT TESTED | Isolated Gaming inheritance; no T runtime startup; Separate bounded resource/cadence and PAPER management acceptance; extended benchmarking not implicitly approved | Required |
| Prediction Market Intelligence V2 safeguards | BLOCKED | Permanent roadmap PM-V2.1–PM-V2.6, exactly-once/pre-deadline/auto-flat and no opposing positions gates remain; Separate phase evidence and acceptance; no live-capital authority | Required |
| Redis/PG persistence and graceful real exit | NOT TESTED | Source Compose named mounts and safe-signal allowance; engine unavailable; official DB documentation; Verify actual image/PID1/signals, persistence config, backups and before/after data markers during separately approved acceptance | Required |

## Validation and runtime evidence

Final extracted candidate: **142 focused passed; 2,348 full passed, 3 inherited xfailed, 0 unexpected failures, 2 dependency deprecation warnings**. Manifested Python compilation: 758 files passed; Windows PS5.1 parsing: 18 scripts, zero errors; dependency consistency and Git diff checks passed. Ruff remains 3,997, zero new since R.

Exact final counts and checks are authoritative in logs/diagnostics/r7e46t-20261017/result.json. Raw failing reproductions, repaired runs, focused/full regression logs, parser/compile/lint/dependency and preservation evidence are retained. The preliminary repaired run passed 50 tests; the broader focused lifecycle run passed 142. Three inherited E136 expected failures remain unresolved; never count them as completed release gates.

Fresh supported status confirms STOPPED. Selected local endpoint is the Docker Desktop Linux named pipe; exact Atlas-name inspection failed because that pipe is unavailable. Current containers/health/ownership are UNKNOWN, not absent or stopped. No global Docker inventory or Genesis resource inspection occurred. No lifecycle action, production journal mutation, credentials exposure, shortcut replacement, trading/Discord activation, Git staging/commit/push/reset or VPS work occurred.

## Single safest next milestone

R7E46U — separately approved bounded real-container acceptance using the prepared plan, only after read-only ownership, persistence and backup prerequisites pass. If the Engine or evidence is unavailable, remain blocked without starting it. Keep runtime actions prohibited until local Engine availability and ownership/persistence prerequisites can be independently established. Do not silently turn U into a startup or shortcut installation. Cash/provider/lint/E136/Gaming/PM-V2 gates remain unchanged.

## Full remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Core additions: T shutdown race/coercion/identity repairs need independent real lifecycle/persistence/restore acceptance; obtain explicit shortcut migration approval and preserve all uncertain-operation evidence.
