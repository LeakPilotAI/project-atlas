# R7E46R - provider pacing, worker ownership and shutdown-drain contracts

Date: 2026-10-17, America/Chicago (CDT UTC-05:00). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e46r-20261017/. Exact final results, archive hashes and runtime observations are in result.json and associated logs. This document describes source contracts; it is not production activation approval.

## Disposition

Isolated source remediation and validation; RELEASE NO-GO. Atlas remains STOPPED. No production provider requests, journal migration, lifecycle actions, live-capital/Discord activation, Genesis access or Git staging/commit/push/reset. The operator-authorized shutdown disposition is unchanged; no further provenance investigation or timestamp-correlation claim.

## Provider pacing and admission

New provider_dispatch.py supplies FIFO admission and owned blocking workers for the Quality Dips quote singleton's default Robinhood and Yahoo clients. Per provider: maximum3workers, minimum0.2seconds between logical starts (internal5/s ceiling), maximum64queued operations. Combined default provider-worker ceiling6; quote admission maximum64registered symbols and6quote coroutines. Each whole quote has a30second deadline including waiting for a quote slot. The existing37-symbol universe fits. Coalesced waiters share a symbol task; last-waiter cancellation cancels unused work. Oversized/full/closed/quarantined admissions are rejected observably rather than building an unbounded backlog. Existing cache and authoritative quote-quality/timestamp policies are preserved; deadline results are MISSING/nonactionable, never invented prices.

FIFO means admitted operations are scheduled in arrival order, without overtaking. Admission at capacity is an explicit rejection; this is not a weighted reservation or guarantee that every new batch will be admitted. Distinct provider services/processes and cash-scanner clients are not claimed to share this budget. Custom injected clients must supply their own transport contract; tests use explicit fake dispatchers.

There are zero automatic retries. Existing bounded RH endpoint and Yahoo source fallbacks remain; they do not bypass the provider dispatcher.429/503/RATE_LIMIT outcomes impose shared cooldown: at least5seconds, numeric Retry-After when greater, plus0-0.25seconds jitter. Unsupported, negative, nonfinite or >86400second Retry-After closes that dispatcher for operator review rather than shortening the instruction. A request already started before the response remains owned. No retry or queued replay is created. Auth/error outcomes remain failures.

These are conservative INTERNAL ceilings, NOT verified vendor quotas, permissions or actual HTTP-rate guarantees. Each RH logical call is one fixed-endpoint request; yfinance may make internal HTTP calls, caching and retries within a single logical operation. Vendor terms, real request counts, coverage, latency,401/429 rates and session/game resource effects remain unverified release gates. No live provider traffic was used to validate them.

## Lifetime, cancellation and late results

Each accepted blocking operation has an explicitly named, non-daemon owned thread and completion future. No default executor backlog is used by these quote-provider operations. Async caller timeout/cancellation removes unstarted work immediately. A started worker remains tracked and retains capacity until the thread really exits; late outcomes are discarded rather than returned to the abandoned caller. Its provider is quarantined until exit: queued operations are rejected and new work is refused. No automatic replay follows recovery. One canceled coalesced waiter cannot cancel another caller's shared quote; the last waiter can cancel unused work.

Python cannot safely kill an arbitrary blocking thread. This milestone does NOT promise hard termination of a stuck third-party call. Instead, maximum worker population remains bounded and owned; a nonterminating worker causes explicit failed drain and prevents a truthful successful process exit. No force-kill/recovery bypass is introduced. A blocked provider may still finish read/health-telemetry work after a FAILED drain, but successful drain requires real thread exit. Caller deadlines are not misrepresented as thread termination. Abnormal worker termination is marshaled as failure, not a SystemExit of the API.

## Shutdown, journal safety and restart

ExtendedHoursCollector tracks active collections, rejects work once closing, cancels pre-commit collections and prevents entry into a commit after closing. An existing shielded/fsync commit is allowed to finish. shutdown(timeout) waits only its explicit budget and raises if ownership remains. It never deletes or rolls back committed evidence. A new collector replays the existing independent commitment and identities, preventing duplicate observations after restart. Reopening an existing collector requires no pending collection.

ExtendedHoursResearchService stop uses a shared deadline, retains unfinished task references and reports SHUTDOWN_DRAIN_TIMEOUT / DRAIN_FAILED on failure; stopping requests cannot initiate later collections. Main lifespan drains quote providers AFTER existing service stops and BEFORE PAPER shutdown reconciliation. Provider drain failure sets the existing fail-closed reconciliation guard false. Final shutdown-complete logging requires both confirmed provider drain and stopped services; otherwise it explicitly reports incomplete shutdown and operator recovery required. Provider close does not stop the cash scanner prematurely.

The journal no-write guarantee applies after successful collector AND provider/service shutdown confirmation. A failed commit drain is not such a confirmation: an already-owned commit may still finish and must be preserved. No destructive rollback is attempted. Budgets are20seconds per drain domain (research service and quote service), not an asserted20second bound for the entire Atlas lifecycle and all unrelated services. Nonterminating library/OS I/O may keep the process in a manager timeout state; runtime acceptance/operational policy remains separately approved work. No production shutdown was run.

## Observability and scope preservation

New GET /diagnostics/quote-dispatch reads counters and limits without fetching or creating work: queued/owned/active work, accepted/started/completed, paced waits, deadline/cancellation, queue/closed/quarantine/shutdown rejections, throttles, late discards and drain failures. Existing /diagnostics/extended-hours response contract remains intact; service status also reports stopping/pending collections and DRAIN_FAILED where applicable. No credentials, request headers or quote payloads are exposed by new metrics.

The optional dispatcher parameter defaults to None on standalone RH/YFinance clients. Only the quote singleton constructs the new paced default clients. Cash scan.py and market_hours.py remain byte-identical; session/rate/risk authority is unchanged. Cash combined-release scope acceptance remains required. Research stays disabled by default, Gaming Mode alone cannot opt in, and normal PAPER management cadence is unchanged in source. Actual runtime cadence is not claimed while stopped.

## Validation and failure disposition

Initial focused run:102passed/1failed because an existing diagnostic endpoint exact-response contract changed. Repaired by adding a separate endpoint, preserving the original; no test was weakened. Next focused run125passed. Subsequent focused run194passed/1failed in a new real-time/thread-entry ordering fixture; isolated rerun passed. The test was corrected to use the controlled pacing clock and to assert scheduling/worker capacity without assuming OS thread entry order. All original failure logs and archives are preserved.

First broad candidate D:2280passed/3known xfailed/2warnings in121.29seconds, no unexpected failures. Final focused/full results, exact counts, Ruff comparisons, compilation, dependency/PowerShell checks and immutable candidate hashes are recorded in result.json; only those results determine final milestone status. No pre-execution success is inferred here.

Clock defect: preserved Q artifact reproduces the old comparison failure at a controlled rounding boundary. tests/test_evidence_checkpoint_history.py now freezes ONLY that module's scorecard clock for consistent before/after report comparisons. Production freshness code is unchanged. Existing three E136expected failures (independent rollback witness, dual-database rollback consent resurrection, atomic recovery snapshot) remain unwaived.

New provider exception-boundary catches are explicitly justified: marshal worker termination to an owned future and expose provider errors while retaining ownership. No unrelated lint cleanup or inherited policy waiver. Known Ruff debt remains a release-quality decision; new-code and whole-artifact comparisons are retained.

## Release gate matrix

| Gate | Disposition |
|---|---|
| FIFO pacing, bounded admission and coalescing | PASS only to isolated evidence in final results; internal ceilings, not vendor certification |
| Owned worker timeout/cancellation/quarantine/late discard | PASS isolated; hard thread termination intentionally not claimed |
| Bounded drain / refusal of new work / explicit failed confirmation | PASS isolated; production shutdown NOT TESTED |
| Journal commit preservation / no post-success write / restart deduplication | PASS isolated; production migration/rollback NOT TESTED |
| Clock-sensitive regression | Test-only deterministic clock; final suite evidence required |
| Vendor license companion and reproducible source artifact | Q packaging repair retained; final artifact verification recorded separately |
| Cash combined-release scope | BLOCKED explicit operator acceptance; no behavior change authorized |
| Vendor entitlements, internal Yahoo HTTP behavior, live latency/coverage/resource thresholds | BLOCKED / NOT TESTED; no live traffic generated |
| Ruff debt / exception policy / three E136expected failures / clean-machine portability | BLOCKED release-quality/recovery disposition |
| Production activation and controlled rollback | NO-GO, no approval and no runtime acceptance |

## Remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

## Single safest next execution

R7E46S: isolated release-candidate consolidation and explicit gate-decision preparation. Review provider-term/transport assumptions, stuck-worker operational recovery limits, cash-scope acceptance and lint/recovery policy; verify final artifact portability and prepare a narrowly bounded separately approvable runtime acceptance plan. Keep Atlas stopped. No activation or benchmark is authorized by this recommendation.
