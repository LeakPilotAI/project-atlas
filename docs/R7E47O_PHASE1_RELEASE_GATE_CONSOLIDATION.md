# R7E47O — authoritative Phase 1 release gates and execution order

**Consolidation completed. Production release NO-GO.** This document and `R7E47O_PHASE1_RELEASE_GATE_MATRIX.json` supersede older Phase1 summary matrices for prioritization; original evidence/reports remain unchanged. PASS always has an explicit scope and is never activation authority.

2026-10-18 America/Chicago CDT UTC-05:00. Branch `chatgpt/atlas-rebuild-v1`; HEAD `f9df47b4cd80dd647d85043aba617cf00c4e6dc0`. Evidence: `logs/diagnostics/r7e47o-20261018-231745`. Latest master/N, release N–S, provider R/S, cash P/S, lint S, packaging/setup and lifecycle/Gaming evidence reviewed offline. No external/provider/network request. License/terms statements below are retained-source findings, not refreshed legal clearance.

## Authoritative gate matrix

Functional owners below are accountability roles, not invented assignments to named people. Machine-readable matrix supplies full dependencies, evidence references and minimum criteria for every row.

| Gate | Owner | Status / accepted scope | Dependencies and minimum remaining acceptance |
|---|---|---|---|
| Normal startup admission |Lifecycle maintainer/operator |BLOCKED, production all-entry coverage |H plan: durable parent intent, independent worker admission before side effects, exact resources/processes; manager/worker/Gaming/legacy/API/standalone coverage, no missing-state bypass. Explicit integration authorization |
| Non-clearing quarantine |Recovery maintainer |PASS, N isolated host subset only |Exact pins/separate protected output, complete bounded audit, all permission flags false. No production deployment |
| Full uncertain-state recovery |Recovery maintainer/operator |BLOCKED |Independent exact-helper quiescence, held all-resource/writer exclusion, revision-bound authority; never clear on EXITED/missing/Yes/timeout alone |
| Current backend startup/shutdown |Lifecycle maintainer/operator |BLOCKED, current whole candidate |Historical E short-run PASS does not cover later provider changes. Fresh clean ownership/resource preflight, accepted stuck-worker policy, one separately approved owned lifecycle/reconciliation/no-orphan acceptance |
| Complete Shutdown contracts |Lifecycle maintainer |PASS, isolated S/T/V |82fresh tests; backend exit before exact-ID dependencies, durable uncertain intent, no unrelated/global/deleting operations |
| Real Complete Shutdown/restore |Operator/lifecycle maintainer |NOT_TESTED |Current exact ownership, backup readiness and explicit real-container acceptance window; graceful stop and preserved dependency restoration |
| Desktop/setup workflow |Operator/Windows maintainer |BLOCKED |Historical legacy Stop concern; setup still calls legacy shortcut installer. Fresh target review and explicit truthful manager/backend-only/complete migration approval |
| PostgreSQL/Redis backup/restore |Operator/storage maintainer |BLOCKED |Effective coverage, independent quiescence/ownership, capacity/destination/encryption/key recovery, usable manifested backup and disposable restoration under separate authorization |
| Logical quote pacing |Provider maintainer |PASS, default singleton/one loop/process |Current source matches tested snapshot; bounded queues/ownership/cooldown; not provider/account-wide HTTP entitlement |
| Actual aggregate HTTP budget |Provider maintainer |BLOCKED |All consumers/processes, internal requests/redirects/cookie/crumb/fallback/retry counts, endpoint-specific allowances and transport pinning |
| Provider data rights |Operator/data-license owner |BLOCKED |Applicable current endpoint/account/use/display/storage/redistribution permission; software license or public reachability is insufficient |
| Cash C1–C4 scope |Operator/cash maintainer |BLOCKED |Explicit combined-release scope decision; retained regression evidence, no silent revert. Source behaviors are already implemented, not disabled |
| Stuck-worker handling |Provider/lifecycle maintainer/operator |BLOCKED operational policy |Choose explicit fail-closed timeout/manual-recovery limits or separately approved bounded/cancellable design; no arbitrary thread/process kill; coherent whole-lifecycle budgets |
| Ruff disposition |Quality maintainer/operator |BLOCKED |3,997unadjudicated findings; adjudicate runtime correctness/security first or exact reviewed baseline. No silent waiver |
| Source artifact integrity |Release maintainer |PASS, structural isolated source scope only |Paired deterministic archive/hash/manifest/extraction/compile evidence in final artifact-validation.json; no deployment or fresh-machine certification |
| Clean-machine installation/distribution |Windows/release maintainer/operator |NOT_TESTED |Pinned reproducible Python/runtime inputs, full dependency/notice review, approved setup/shortcut path, fresh disposable Windows acceptance |
| Gaming configuration |Lifecycle/strategy maintainer |PASS, source/fixtures and historical E brief runtime |Explicit flag, discovery>=180s or slower configured cadence, independent default8s PAPER management; not all collectors throttled |
| Sustained Gaming performance |Operator/performance maintainer |NOT_TESTED |Approved representative windows, Atlas PID-family measurements, actual cadence/drain/health and gaming contention acceptance |
| E136 recovery |Consent/security maintainer |BLOCKED |Three strict expected failures remain: independent rollback witness, coordinated dual-store revocation rollback, atomic recovery snapshot |
| Discord lifecycle delivery |Consent/notification maintainer/operator |BLOCKED |E136/recipient contracts, explicit activation and durable no-backfill watermark; both central automated senders stay denied |
| Extended-hours activation |Research/lifecycle maintainer/operator |BLOCKED |Separate activation/rollback approval after cash/provider/lint/packaging/runtime gates. Disabled by default; Gaming cannot opt in |

No clean-machine or operational gate was upgraded merely because source tests passed. Backend/DB status is not freshly audited O; operator-reported Atlas STOPPED remains inherited. Historical S's unavailable Docker pipe and K's later readable retained-helper observation describe different dates/scopes, not conflicting current-state claims. M/N have not solved Linux writer exclusion.

## Provider scheduling and rights — offline findings

Current provider/runtime and all selected test files match31files in the guarded isolated source. Tests run with production data/credential/network access denied. `provider_dispatch.py` and `quality_dip_quotes.py` verify:

- Three owned workers per default provider, six combined; at least0.2s between logical starts per provider, internal ceiling5/s;64queued/provider;64registered symbols and6quote coroutine slots;30s whole-quote acceptance window;15s default quote cache.
- FIFO for admitted work, not weighted reservations/fairness across independent consumers. Capacity/closed/quarantine rejects are observable; no unbounded admitted backlog. Separate processes, custom clients and standalone cash YFinanceClient calls are not collectively budgeted.
- Dispatcher automatic retries0; existing bounded RH endpoint/Yahoo-source fallbacks remain.429/503/RATE_LIMIT gives >=5s or larger valid numeric Retry-After plus0–0.25s jitter; unsupported values close admission. This is not proof that underlying libraries/redirects make only one HTTP request.
- Caller cancellation removes unstarted work. Started non-daemon blocking workers remain owned/capacity-held; provider quarantines, late outcomes discarded. Python cannot safely kill an arbitrary blocked thread. A nonterminating call may retain the API process and cause manager timeout.
- Quote and research drain domains are20s each; manager stop wait30s is **not a demonstrated end-to-end deadline**. Shielded commits may finish after failed drain; no-write-after-success applies only after confirmed complete drain. Failed drain must preserve evidence/ownership and refuse successful-stop/automatic-restart claims.

Installed yfinance1.7.0 was inspected as files/metadata, never imported for requests. Cookie/crumb acquisition, strategy fallback and internal retries mean one Atlas logical call can amplify into multiple wire requests. Broad `>=` requirements do not freeze these behaviors. `yfinance-transport-review.json` records installed source hash and marker line references. No external host request was sent.

| Provider/source family | Offline budget/rights finding | Remaining gate |
|---|---|---|
| RHJ underlying-equity and classic Robinhood quotes |Cached S primary-document review records RHJ60requests/s and15s price caching; applicability to every account/classic fallback is not proven. Default dispatcher5logical/s is internal only |Current applicable endpoint/aggregate allowance and use/redistribution rights. Cached text is not a new entitlement verification |
| Yahoo/yfinance |Installed library declares Apache-2.0 and license file exists; cached S terms/maintainer review identifies automated-use/personal-use restrictions. No permission record or numeric HTTP entitlement established |Automated-access/data-use rights and actual internal HTTP accounting or licensed alternative. Library license does not license Yahoo data |
| Hyperliquid REST/WS/backfills |Separate adapter/cache paths,30s HTTP timeout and reconnect/backoff mechanisms; not covered by quote singleton dispatcher |Per-endpoint weighted/account budget, all consumers and applicable data/storage/redistribution terms |
| Binance public historical archives |Separate download path has20s timeout and up to3attempts/backoff; historical acquisition is distinct from live quote pacing |Archive-use/redistribution rights and request budget; public URL is not blanket data permission |
| Kalshi public research |Separate read-only client8s timeout/connect4s, bounded pagination/candles; no coverage by the equity limiter |Endpoint rules, eligibility/rights and all-request budget; no live-capital authority inferred |
| SEC/Federal Reserve/context sources |Literal source endpoints found; no new request or current rights review |Source-specific identity/access/caching/redistribution conditions. Document links/context are not all active market feeds |

Literal-host inventory found9hosts including two localhost entries and a documentation host. It misses dynamically composed URLs, RHJ/Yahoo library internals and environment-selected paths; it is explicitly not an exhaustive live provider list. The cached S source URLs are retained references only: no browsing or current legal interpretation was performed O. Applicable vendor permission cannot be created by an operator code-scope approval.

Missing acceptance: wire-level multi-consumer budgets including fallbacks/auth/redirects; dependency-version transport pinning; authoritative classic endpoint entitlement; actual licensed coverage/latency/429/401 under Gaming; nonterminating-worker lifecycle policy. Mocked timing/ownership tests PASS does not waive these gaps. No live-load test recommended before rights and scope approval.

## Cash-scanner reconciliation — existing repairs, no new approval

The four source repairs were requested in R7E44G; **acceptance in the combined release remains missing**. Neither this audit nor source-test PASS is that decision. They execute as part of the cash scanner when it runs: **not behind the disabled extended-hours opt-in**. Source `investment_scan_enabled` defaults true; actual protected environment/runtime settings were not read. Atlas is operator-reported stopped, not a running demonstration.

| Decision | Existing behavior enabled by repair | Evidence / remaining acceptance |
|---|---|---|
| C1 |Reject negative age/future cached timestamps instead of treating them fresh |Freshness/PAPER boundary tests; account for safe refetch/rejection under skew |
| C2 |Force first regular-session price refresh when stored price predates that open; no forced fundamentals/valuation refresh |Opening-plan tests; budget one extra price fetch per affected symbol; future live opening latency/coverage |
| C3 |Calendar-aware next-open wake rather than six-hour oversleep, retaining60s minimum and configured open cadence |Weekend/holiday/DST/wake-loop tests; not a tick-level opening SLA |
| C4 |Bounded2026–2028 NYSE holiday/early-close/DST calendar; unsupported horizon SYSTEM_OFFLINE |Calendar/horizon tests; maintained source and future exchange/unscheduled-closure review |

Precise approval wording remains ready in `R7E46S_CASH_SCOPE_DECISION.md`: accept C1–C4 as source scope only, preserving restrictions/rate limits; no startup, feature activation, live provider request, trading/Discord, migration or benchmarking authority. Rejection requires a specified accepted target and separately scoped remediation; do not silently restore a known readiness defect.

No repair introduces a brokerage execution path or overrides PAPER_ONLY/MANUAL_ONLY. Potential extra fetches and calendar maintenance are provider/operational risks, not trading-authority permission. The separate extended-hours flag remains disabled by default and Gaming alone cannot enable it; no flags were changed/read from protected production configuration.

## Fresh Ruff disposition and packaging review

`scripts/audit_release_lint.py` produced fresh raw JSON, enriched findings, file/rule CSV, settings and command/version in `lint-current/`. Count **3,997**:3,972HEAD-inherited +25later inherited; **0new/0resolved versus S** by file/rule/message multiset. This matching is not individual-line ancestry or a waiver. The utility's legacy `new_since_R`/`pre_S_inherited` labels are retained; O explicitly used S final raw diagnostics as its previous baseline. No source/runtime change was introduced O.

| Triage category | Count | Proposed order — not approved severity/baseline |
|---|---:|---|
| Correctness review |489 |First runtime redefinitions/capture/default/unused-result cases, with call-site tests; distinguish tests from runtime |
| Security/exception-policy review |480 |Review silent/broad exception boundaries, failure propagation and logging;399BLE001 occurrences included. Never blanket-disable safety fallbacks |
| Style/baseline candidates |3028 |Only after correctness review, separately approve exact hash/file/rule baseline or small behavior-preserving batches; no mass import/type rewrite |

Representative inherited rules remain F81155, B0233, B0082, F6011(test duplicate), PLR01248(intentional NaN checks require preservation), ASYNC2511(intentional watchdog fixture). These are review leads, not confirmed bugs or automatic safe fixes. No Ruff finding is adjudicated or waived O. Recommended first code-quality milestone is a bounded runtime correctness/security batch, not thousands of cosmetic edits.

Packaging source review: builder explicitly includes required untracked source/scripts/tests/docs and the vendored `lightweight-charts.LICENSE`; rejects live data/credential/venv/backup inputs and creates deterministic source ZIP/manifest/observed dependency list. Final fresh paired artifact, extraction/hash/compile counts live in `artifact-validation.json`. This is a source-candidate test, **not a database backup, clean Windows install or deployment**. Protected environment values and live evidence are not packaged.

Twenty direct Python dependencies are installed and declared-license metadata/file hashes recorded. This is not a complete transitive distribution clearance. yfinance software licensing is distinct from data rights. Vendored chart Apache2license companion exists; retain headers/attribution and review applicable notices before distribution. No full application-license/SBOM/notice clearance is inferred. Frontend lock exists, exact Next/React requirements are recorded, while Python dependencies use broad lower bounds; observed environment list is not a hash-locked installer or proof of fresh resolvability. No dependency install/update occurred.

Windows PowerShell **5.1.26100.9711** parsed18scripts with0errors. This proves syntax, not clean-machine runtime compatibility. Setup expects Python>=3.12, pip/build dependencies, local NTFS/native APIs, Windows timezone support, operator-owned configuration and Docker Linux endpoint identity. Node is optional for the API-served dashboard; standalone frontend install uses npm ci. `Fresh-Setup.ps1` installs floating Python constraints, may create/copy `.env` examples, and invokes the legacy desktop shortcut installer. It was **not run**; approved configuration/shortcut migration and fresh-machine acceptance remain open. Linux helper image/provenance dependencies are a separate unaccepted production-helper path, not silently supplied by a normal source ZIP.

Rollback remains evidence-preserving: disabled-by-default feature state, retained journals/independent commitments and migration instructions; no source reset/one-component restore/fence deletion. Source archive reproducibility does not validate database restore or cross-version state migration.

## Gaming acceptance plan — proposed, not executed/approved

Source opt-in changes only Perp discovery: normal60s, Gaming>=180s or configured slower; PAPER management stays independently configured8s by default. Other collectors are not throttled. Historical E runtime verified actual API Gaming settings, ownership, dashboard and graceful stop, but preceded later provider/drain changes.

Historical resource evidence is only2.046730s: API working set675.12MiB, private996.77MiB,29–30threads;1.500CPU-seconds equals73.3% of one logical core or6.1% normalized over12logical cores. This is not whole-system CPU, an idle baseline, memory-leak evidence, sustained game contention or savings versus normal.

After separate lifecycle/benchmark authorization and approved rights/budgets:

1. Fresh exact owner/run/resource preflight; refuse ambiguous or applicable UNCERTAIN state. Use supported explicit Gaming launcher, verify actual API flag/effective discovery and normal PAPER cadence. No extended-hours activation.
2. Warm5minutes, observe idle15minutes and representative active research15minutes at modest5s sampling; at least five effective discovery cycles. Sample verified Atlas-owned PID family only. Record per-core and host-normalized own CPU-time deltas, working/private bytes separately, threads, active/queued workers, rejects/late results/drain metrics. Use ordinary already-approved workload, not provider load amplification.
3. Agree thresholds **before** execution. Proposed provisional targets, not measured results or release approvals: own-family host-normalized CPU p95<=3% idle/<=10% active; working set<=1.5GiB and no unexplained sustained post-warm growth; health p95<=1s; normal8s PAPER interval p95<=10s/max<=16s. Revise explicitly based on representative baseline, not after failure to manufacture PASS.
4. Confirm actual discovery intervals against effective configured cadence and schedule tolerance, with no missed position-management cycles. Observe licensed provider coverage/401/429/queues. Compare normal/Gaming only in separately approved matched workload/session windows; no resource-saving claim from interval configuration alone.
5. Operator reports game hitches/contention; do not inspect unrelated game/Genesis processes. Gracefully stop only the owned run, verify reconciliation, worker exit and retained evidence; follow the separately approved backend-only versus complete-dependency plan. Stop timeout/drain failure remains BLOCKED, no kill/restart or evidence deletion. Deliberately stuck-call injection remains isolated, not production.

This milestone did not activate Gaming or sample runtime resources. Extended benchmarking/optimization remain separately authorized. The proposed thresholds require operator agreement and are not a replacement for actual measurements.

## Prioritized execution sequence

| Rank | Short milestone / expected closure | Access and dependencies |
|---|---|---|
|1 |Record operator C1–C4 scope decision and quality-disposition direction; perform first bounded runtime correctness/security lint adjudication with focused tests |Offline source/fixtures; C1–C4 wording already reviewable. No acceptance inferred O. No broad baseline waiver |
|2 |Resolve stuck-worker operational policy and a coherent stop-budget contract |Offline deterministic failure tests first. Explicit acceptance of fail-closed/manual limits or separately scoped transport/process design; no force-kill workaround |
|3 |Provider entitlement/redistribution dossier and complete logical-to-HTTP consumer budget map |Offline records/account-owner evidence; permission/licensed alternative needed. No live traffic before rights/budget gates |
|4 |Reproducible install/notice/setup path and clean-machine acceptance package |Offline pin/manifest/license/shortcut plan; fresh install and shortcut changes require separate authorization; no setup execution now |
|5 |Finish coverage/quiescence/capacity/key recovery and approve cold backup plus disposable restore |Read-only preflight first under separate scope; real volumes, copying and scratch restore each need explicit approval. No production restore |
|6 |Bounded current-candidate normal startup/shutdown, then exact Atlas-only Complete Shutdown/restore acceptance |Explicit owned lifecycle approval and fresh preflight; required backup/storage readiness; no Engine/Desktop/unrelated resource action |
|7 |Sustained Gaming resource/cadence acceptance against approved baseline |Separate benchmark window after lifecycle/provider gates; preserve PAPER management and resource objectives |

The full uncertain-helper recovery framework may remain unavailable while source-only release work, isolated testing and a separately authorized **verified-clean normal-operation scope** progress. That limitation is acceptable only if recovery remains refused and there is no requirement to clear affected uncertainty. It is not acceptable to call an uncertain production scope clean, disable admission, initialize missing protected state automatically, or infer authority from quarantine. E136 can likewise remain blocked with both central senders denied for separately approved PAPER/manual runtime acceptance; no notification readiness is claimed.

Recommend **R7E47P — Bounded Runtime Lint Correctness/Security Adjudication**: select the first small runtime batch from current CSV/findings, produce tested concrete dispositions/remediations, retain exact no-new-findings evidence and leave broad baseline approval separate. Cash C1–C4 operator scope decision can be recorded independently; current wording needs no new framework. Stop at O's consolidated decision gate.

## Validation and restrictions

Fresh guarded offline provider/cash/activation/Gaming suites: **136passed,0failed,0skipped;15.76s**. Lifecycle S/T/V: **82passed,0failed,0skipped;47.52s**. Selected E136contracts: **1passed,3strict expected failures;1.15s**. Non-overlapping total **219passed,3expected failures,0unexpected failures,0skips**. Expected failures remain release blockers, not passes. N's636/4skip result is retained historical evidence and not added to O's total.

Pip check: no broken requirements. PS5.1 parsing18/0errors. Current tested runtime/test31file hashes match guarded isolated source. Fresh Ruff inventory intentionally exits its inner lint check with findings; audit utility succeeds in recording them, not in making the quality gate PASS. Final source artifact hash/extraction/compilation and preservation details are in result.json. Initial file-discovery regex had a reversed range; corrected read-only tooling query, not a product/test failure. Original test/failure artifacts from earlier milestones untouched. No broad lint rewrite, new runtime source or production behavior change.

No Atlas/Docker lifecycle, provider/network request, real-volume inspection/backup/restoration, Genesis, production registry/startup/ACL/configuration/shortcut change, live trading/Discord, Git staging/commit/push/reset/deletion or VPS. Source archives/temporary fixture rollback tests are not production data backups. Atlas STOPPED is operator-reported, not a fresh runtime audit. Source/configuration review did not read protected `.env` values.

Master updated only by `scripts/windows/Atlas-Roadmap-Checkpoint.ps1`. Final result verifies raw backup equality, exact read-back, byte-identical outside-managed history and permanent strategy/recovery/PM-V2 anchors. Current gate JSON is required in the final source artifact; artifact validation must pass before O is reported complete.

## Complete remaining seven-phase roadmap

1. **Core reliability/operations:** matrix gates above; normal all-entry admission/owned lifecycle, stuck-worker budget, provider rights/wire budgets, cash scope, Ruff/artifact/license/clean-machine acceptance, real data/runtime/rollback/Gaming; separate storage coverage/capacity/key recovery/backup/disposable restoration/Complete Shutdown/shortcut approvals. Full recovery remains independently blocked; non-clearing quarantine limited. No extended benchmarks/optimization without approval.
2. **Evidence Engine:** immutable hypotheses/outcomes, replay, precision/recall/calibration/false positives, realistic PAPER fees/slippage/funding, bias controls and Research Memory. E29 NOT_READY; corroboration context-only.
3. **Fifteen-minute crypto PAPER:** eligibility/jurisdiction/rules/fees/settlement, timestamped spot/perp/depth/volatility/funding/liquidity, calibrated probability/executable edge, realistic fills/out-of-sample evidence before live proposal.
4. **Cross-market intelligence:** equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable uncertainty/invalidation/reproducibility; cautious hypotheses.
5. **SaaS:** demand/pilots, tenancy/auth/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics/licensing/unit economics; pricing unvalidated.
6. **Institutional readiness:** RBAC/audit/security/incidents, governed research/workspaces/API/compliance/pilots; stronger principal/TPM/off-machine authority separately scoped; no VPS dependency.
7. **Commercial scale:** product-market fit/retention, partnerships/integrations/white-label/API licensing, evidence-led expansion and measured economics/reinvestment.

Cross-phase: E136 independent witness/dual rollback/atomic recovery, recipient transport/render/storage and uncertainty/dead letters. Discord explicit approval/durable no-backfill/no automatic uncertain retry. Prediction exactly-once/pre-deadline/auto-flat; portfolio-versus-strategy risk undecided. PM-V2.1–PM-V2.6 discovery/calibration/edge/pre-event PAPER/evidence/dashboard; one position per market, no combos/stacking/averaging/opposing YES+NO; settlement research never overrides pre-event safeguards. PAPER_ONLY/MANUAL_ONLY, permanent Gaming efficiency/normal PAPER cadence and Atlas/Genesis separation preserved.
