# R7E46Q — isolated release-blocker remediation

Date: 2026-10-17; America/Chicago (CDT UTC-05:00). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e46q-20261017/.

## Shutdown disposition and safety

The operator canceled further shutdown-provenance investigation and confirms an intentional, operator-authorized overnight shutdown using the verified background manager. Record the shutdown as operator-authorized. Independent timestamp correlation to October 16 09:18:30 CDT is NOT claimed. No further provenance investigation is required absent new contradictory evidence. This supersedes the draft correlation gate in preserved correlation.json; that file records the earlier investigation, not the current release decision. The original R7E46P report remains unchanged. Its unexpected-to-auditor shutdown description is not a current unexplained-termination blocker.

Supported read-only Status verified STOPPED. No startup, shutdown, restart, production migration, provider requests, trading/Discord activation, protected configuration change, Genesis access or Git staging/commit/push occurred. One unprivileged Status query could not access Windows CIM; the supported read-only query with process-query access succeeded. Historical runtime/PAPER observations are not presented as current live measurements.

## BEFORE / AFTER and release gates

| Gate | Before | Current disposition |
|---|---|---|
| Cash-scanner combined-release scope | Explicit acceptance missing | BLOCKED; decision prepared in docs/R7E46P_CASH_SCOPE_DECISION.md. No cash source changes or inferred approval. |
| Concurrent quote consumers | Per-call six slots; 2/3 consumers peaked 12/18 with 74/111 quote operations | PASS isolated for shared singleton callers: one service-wide six-slot semaphore and per-symbol in-flight task; 1/2/3 consumers each peak six and perform 37 quote operations. |
| Request coalescing | No in-flight deduplication | PASS isolated: shared task, independent result copies, cache update once, failed-task cleanup and retry. One canceled waiter cannot cancel another caller's work. |
| Provider total capacity | Pacing, blocking-thread deadlines, degraded sweep/queue bounds unresolved | BLOCKED. This change bounds quote coroutines, NOT all underlying HTTP/thread lifetimes, separate service instances, processes or providers. No global HTTP quota claim. |
| Vendor license companion | Existing untracked lightweight-charts.LICENSE omitted | Explicit required companion included; missing file now fails artifact build. Final artifact verification recorded separately. |
| Journal integrity/migration | O independent commitment passes isolated adversarial tests | Retained isolated PASS; production migration/rollback NOT TESTED and prohibited. No journal modifications. |
| Feature flags / Gaming | Isolated safeguards pass | Retained isolated PASS; actual activated feature workload NOT TESTED. Gaming alone cannot opt in; PAPER cadence unchanged. |
| Ruff / quality | P full artifact 3998 findings; no waiver | BLOCKED quality disposition. Safe Iterable import modernized; no broad formatting or exception-policy changes. Current counts/comparison in evidence; historical counts not rerun claims. |
| Production activation / rollback | NO-GO | NO-GO. Explicit approval and separately bounded runtime acceptance remain required. |

## Implementation contracts and limitations

backend/app/investment/quality_dip_quotes.py: move concurrency slots from each get_many call to the existing shared service; register one asyncio task per normalized symbol with no await between lookup/registration. Shield shared tasks from individual waiter cancellation. Always clear in-flight state on completion/failure and consume otherwise-unobserved exceptions. Return separate shallow result dictionaries, preserving existing quote/timestamp/source-preference/cache semantics. All production quote consumers inspected import the singleton. Separate constructed services do not share the semaphore. This is an event-loop-local service contract, not cross-thread safety.

Cancellation deliberately permits already registered shared quote tasks to finish and populate the cache. A canceled large request can still leave queued work, and provider wrappers can time out while blocking threads continue. These are explicitly retained release blockers; this milestone does not implement shutdown draining, a global provider request budget, pacing, singleflight across processes or kill threads. No silent quote-quality promotion or new Yahoo fallback policy is introduced.

scripts/build_release_candidate.py: explicit required companion allowlist adds backend/app/static/vendor/lightweight-charts.LICENSE without broadening packaging to arbitrary untracked files. Existing missing-input and protected-input rejection remain. No legal sufficiency or clean-machine deployment claim.

Tests: update the prior P capacity reproduction to assert the repaired behavior; add independent waiter-cancellation, result-isolation and failed-fetch cleanup tests. Earlier evidence/archives are preserved. Cash scope proposal remains the four R7E44G behaviors: future timestamp rejection, first regular-session price refresh, calendar-aware wake-up retaining minimum/rate limits, and 2026–2028 holidays/early-close/DST/horizon handling. Scope acceptance would not itself authorize runtime activation.

## Validation

145 focused tests passed (10.04s): provider concurrency/coalescing, quote receipt-time boundaries, journal adversarial integrity, activation isolation and cash reliability. Earlier read-only ownership audit: 32 passed (14.18s), two PowerShell files parsed without errors. Four changed Python files compiled and pip check reported no broken requirements. Full release results and final artifact hashes are recorded in acceptance-results.json. No inferred full-suite success.

Initial sandbox runs stalled during Windows proactor event-loop socket-pair initialization before test-body execution and were interrupted; diagnostic stack and sandbox-test-interruption.txt explain this. Retried tests retain a harness guard against external connections and production data/credential access. No service was interrupted. Final lint, artifact and roadmap results are separate evidence files.

Completed background: E131–E135 isolated Discord foundations; R7E44 ownership/Gaming/source reliability; R7E46F–I collector/locking/lifespan/isolated soak, K recovery, L updater, M activation readiness, N review, O journal/timing remediation, P scope/capacity audit. Production J follow-up and all unresolved gates remain open. Q implements partial isolated release remediation, not production acceptance.

## Remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; finish provider pacing, bounded blocking-worker lifetime and queue/backpressure contracts; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

## Safest next execution

R7E46R: isolated provider pacing, bounded worker-lifetime/backpressure and shutdown-drain contracts, with fake blocked providers and no runtime activation. Seek a concrete cash-scope and release-quality policy decision independently; do not change cash behavior or infer approval. Atlas remains stopped.
