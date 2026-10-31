# R7E46P - cash scope and remaining isolated release gates

**Milestone disposition: isolated source validation complete; runtime continuity BLOCKED. Release decision: NO-GO.** Production activation, backend restart and live
rollback remain prohibited. Source/test assessment is not operational acceptance.

Date:2026-10-16,America/Chicago,CDT UTC-05:00. Exact observation timestamps are
in baseline.json and api-after.json. Branch:chatgpt/atlas-rebuild-v1.
HEAD:f9df47b4cd80dd647d85043aba617cf00c4e6dc0.
Evidence:logs/diagnostics/r7e46p-20261016/.

## Cash-scanner decision

Classification: **intentional source repair, not a newly discovered unintended
regression; combined-release operator scope acceptance remains BLOCKED.**

The earlier R7E44G instruction explicitly requested freshness and market-calendar
repairs. The preserved roadmap records SOURCE AND FULL REGRESSION GREEN with
2135passed/3xfailed, including66data-reliability cases, and explicitly leaves
runtime certification pending. N and O retain the same scope restriction. Neither
that source authorization nor this P request approves a new runtime behavior or
combined production release. HEAD is a committed comparison reference, not proof
of the last accepted runtime semantics. Source history's latest scan changes include
`a2b71173` (bounded history readers), `bc018218` (cycle/journal scans),
`b4f17016` (outcome enrichment) and `3f5a53b2` (equity intelligence).
The pending calendar/wakeup repairs are uncommitted, not part of those commits.

Exact differences from committed HEAD:
- Future cached fetch times fail `_age_ok` rather than satisfying TTL.
- First regular-session price fetch is forced when last quote predates open,
  without forcing extra fundamental/valuation fetches.
- Closed-session wait wakes for the next calendar opening, retaining the60sminimum
  and configured open interval, instead of always taking the six-hour closed wait.
- Explicit2026-2028NYSE holidays/early closes and DST-aware session bounds,
  weekend/system-offline handling and fail-closed unsupported calendar horizon.

Both cash source files remain byte-identical to P preflight. Reverting the known
wakeup/freshness repairs without a verified accepted target would reintroduce
verified defects, so no restoration was performed. Existing G regression tests
exercise boundaries, weekend/holiday/DST openings, the real scanner sleep path,
first-open fetching and future timestamp safety. P reruns them in isolation rather
than adding tests that merely mirror the implementation.

[Exact proposed operator decision](R7E46P_CASH_SCOPE_DECISION.md): accept inclusion
of these four existing behaviors in a future whole-source candidate, preserving
session restrictions and configured rate limits. This would be scope acceptance
only; it would not approve restart, activation, trading/Discord changes, live
benchmarking or deployment. Alternative: supply a verified accepted baseline and
approve a separately isolated narrowed/restored artifact. No decision is inferred.

## Ruff findings and safe disposition

[Complete per-file/rule/review-category inventory](R7E46P_RUFF_INVENTORY.md)
records the entire source artifact, rather than only the previously reviewed subset.
Whole artifact:3998 findings, preserved O baseline4005, committed HEAD3982.
P resolved7 and introduced0 by per-file/code/message multiset comparison. The
previous changed/untracked76-file subset is478 ->471. This is not a clean-lint claim.

Safe changes:
- Hyperliquid adapter:datetime.UTC aliases and the newly added postponed optional
  annotation; no price, freshness, WebSocket or ownership behavior changes.
- Shared HL cache:UTC alias and modern list annotations in the new freshness helper.
- Manual service:sort the import block; its moved freshness helper has no startup
  side effects. No request or PAPER behavior changes.

All four reviewed files (including unchanged main.py) have identical executable
AST after explicitly normalizing imports, postponed annotations and the identical
UTC object. `datetime.UTC is datetime.timezone.utc` is verified. Import changes
were separately reviewed. main.py is byte-identical to preflight: its broad optional
research-startup catch remains a policy finding rather than being silently waived.

The remaining7working-tree-only code/message findings versus HEAD are six
UP017/UP045 style findings in the untouched cash-calendar file and one BLE001
optional-startup exception-policy finding. Multiset attribution can assign a repeated
message to a later unchanged line; diff review locates the added optional-startup
catch. The original N list's main.py:508 location should not be read as proof that
the unchanged health fallback introduced the finding.

The subset also retains446HEAD-inherited and18untracked/pre-P findings. Whole
review-category totals:432correctness_review,399policy_review and3167style/
maintainability. These are audit triage labels, NOT official Ruff severities or
confirmed bugs/vulnerabilities. No existing finding is waived as harmless solely
because it is inherited. New capacity tests pass Ruff. Baseline debt and exception
policy require an explicit release-quality disposition; P avoids broad formatting
or unrelated refactoring and preserves the cash files exactly.

## Provider capacity and failure evidence

Active configured investment universe:37symbols, read directly without provider
calls or importing storage loaders. Tests use37synthetic symbols and fake transport.
No live traffic is generated. Results are mock structural evidence, not measured
provider latency, entitlement limits, HTTP quotas or gaming performance.

| Isolated scenario | Observed result |
|---|---|
| One cold consumer | Peak6quote fetches;37RH operations. |
| Two simultaneous consumers, same service/symbols | Peak12;74RH operations. No in-flight symbol coalescing. |
| Three simultaneous consumers | Peak18;111RH operations. |
| Immediate warm cache read | Zero additional provider operations. |
| Expired cache, repeated symbols | One cold37-symbol sweep again; duplicate names within a call are removed. |
| All RH endpoints empty, Yahoo empty |74RH endpoint calls +37history +37info =148logical operations;37MISSING/nonactionable quotes. |
| RH timestamp older than900s | Remains REFERENCE/nonactionable and skips independent Yahoo fallback, even if another source might be fresher. This is the current preference policy, not a newly approved change. |
| Await timeout or cancellation | Coroutine completes/raises but blocked provider worker continues until fixture release; every mock worker is explicitly drained. |

The semaphore is allocated per `get_many`, so6 is not a shared-process limit. Cache
lookup precedes fetch and there is no in-flight singleflight map. The nominal cache
TTL is15s. Service loop completes a sweep then sleeps180s; start-to-start period is
sweep latency +180s, not a guaranteed180s. Constructor minimum30s remains unchanged.

Default RH urllib timeout5s is wrapped in6sasync deadlines for each of two endpoints;
shared Yahoo wrapper deadlines are8s each for history/info. A nominal all-deadline
path is28s per symbol, seven waves for37symbols at6slots, about196s of sweep time
plus180s sleep. This is an illustrative timeout model, not a hard wall-clock bound:
executor queueing, event-loop scheduling and blocking-library work can persist.

A primary-only37operation sweep /180s gives a nominal0.206logical operations/s
ignoring sweep duration.148/180 gives0.822logical operations/s for a theoretical
fallback sweep, NOT an actual HTTP rate guarantee. Requests burst, shared consumers
multiply work, and yfinance can make internal requests/fallbacks. Its0.05s throttle
uses shared mutable state without a cross-thread lock, so it is not a proven global
20HTTP/s limiter. No provider quota or allowed traffic level was verified here.
There is no explicit whole-quote immediate retry loop; endpoint/source fallbacks
are not equivalent to retrying one request, and library-internal retries are not
bounded by this source-level logical-operation count.

## Proposed measurable acceptance thresholds

These are internal release-test criteria, not claims about provider entitlements,
operator approval, existing live performance or a new runtime configuration.

| Criterion for future acceptance | Current disposition |
|---|---|
| One shared maximum6active quote fetches across all consumers; one in-flight fetch per symbol;37cold same-symbol requests coalesced across consumers | BLOCKED:mock peaks12/18 and74/111operations. |
| Proposed internal pacing <=5logical starts/s/provider, subject to stricter documented provider terms; zero unexpected401/429 in bounded healthy window | NOT TESTED/NOT IMPLEMENTED globally; provider allowance itself unverified. |
| Cold healthy37-symbol sweep p95<=60s,p99<=120s; degraded full sweep<=180s; no unbounded work queue growth over3cycles | NOT TESTED live; nominal196stimeout model does not satisfy degraded target. |
| >=34/37usable LIVE/FRESH quotes in each of3consecutive eligible extended-session cycles; every accepted timestamp nonfuture and <=900s; LIVE<=120s | Timestamp semantics PASS in fake tests; actual coverage/latency NOT TESTED. |
| Warm cache causes zero extra operations; expiry respects shared budget; stale/reference data never becomes actionable | Warm cache/staleness PASS isolated; shared budget BLOCKED; stale RH fallback preference requires explicit policy disposition. |
| Canceled/timed-out work remains counted until its blocking worker actually exits; no residual owned provider work after approved20sgraceful budget | BLOCKED/NOT TESTED:mock proves coroutine timeout is not worker termination; no production shutdown attempted. |
| During approved observation, API health p95<=1s, PAPER8smanagement p95interval<=10s/max<=16s; no new research execution/Discord side effect | NOT TESTED as a live feature workload. Gaming/resource benchmarking remains separate approval. |
| New paired journal commits match witness; zero duplicate/conflicting identities silently accepted; faults quarantine; disabled rollback preserves evidence and prevents new research writes | PASS isolated source; production activation/rollback NOT TESTED and prohibited. |

No capacity behavior was changed in P. These results justify isolated global budget,
coalescing and worker-lifetime work before requesting production activation.

## Artifact verification and assumptions

O's preserved C/D archives still have SHA256
`db389b3c57b18b8cd9d32b5ab3b2467a35b3bdca2d8d6af6a475b4cd079461b1`.
They are identical. A separate reserialized ZIP is byte-identical too; clean
extraction verifies all884manifest inputs. Required collector, integrity module,
service, provider timing, Windows launchers, migration document and inert recovery
test fixture are present. No original artifact was overwritten.

P's final E/F archives are also byte-identical, clean-extracted and hash-verified:
SHA256 `2b9798b3ad7af560c71e4e6770819a55ce5fada1dcf15d3ec9200d19a46777a8`.
887source/support inputs,72explicit untracked inputs. The full/focused suite imports
only the extracted app, with production data/credential and network guards. No
staging, commit, deployment, environment mutation or production data is packaged.

Additional packaging finding: untracked
`backend/app/static/vendor/lightweight-charts.LICENSE`(11347bytes) exists in source
but is omitted by the builder extension whitelist. No additional untracked binary
runtime asset was found in the scoped inventory. Required runtime code is present;
companion distribution metadata is incomplete. Record this as a separate BLOCKED
gate, not a missing-code test failure. No licensing conclusion is inferred here.

Environment assumptions remain Windows locking, Python>=3.12, installed dependencies
and zoneinfo data. Installed versions are recorded, not bundled wheels or a tested
clean-machine installer. Commitment path binding and reviewed legacy migration
are required when moving existing state; source archives must not carry that state.
Provider entitlements/network connectivity are not supplied by a source archive.
Archives freeze source/context before final P report/roadmap attestation. Later
attestation documentation is not silently inserted into already tested archives.

## Activation gate matrix

| Gate | Status | Evidence / unresolved requirement |
|---|---|---|
| Cash implementation intent and source regressions | PASS | R7E44G history; isolated calendar/freshness/opening tests. |
| Cash combined-release operator scope acceptance | BLOCKED | Explicit proposed statement awaits acceptance. |
| Journal independent integrity/legacy migration contract | PASS | Oadversarial cases rerun; witness/migration source and contract packaged. |
| Actual production migration/recovery | NOT TESTED | No production journal/witness created or migrated. |
| Provider timing and age semantics | PASS | Deterministic RH/history/info boundary regressions. |
| Shared provider capacity/pacing/coalescing/worker lifetime | BLOCKED | Mock peaks12/18;196stimeout model; residual worker evidence. |
| Feature-flag isolation | PASS | Fake launcher/environment tests; ordinary/Gaming launch does not opt in. |
| Gaming discovery vs PAPER management contract | PASS | Isolated>=180sdiscovery / independent management behavior. |
| Live feature game-impact performance | NOT TESTED | Current runtime normal; no benchmark or activation. |
| No new P Ruff findings | PASS | Whole O4005 ->P3998; introduced0/resolved7. |
| Existing Ruff debt and exception policy disposition | BLOCKED | Complete inventory retained; no blanket waiver. |
| Canonical regressions | PASS |2253passed/3known xfailed/0unexpected failures,240.17s. |
| Required runtime source and reproducibility | PASS | OandParchive hash/extraction checks. |
| Distribution companion completeness | BLOCKED | Untracked lightweight-charts.LICENSE is absent from both manifests; builder whitelist excludes it. |
| Preserve running backend through validation | BLOCKED | Preflight RUNNING; final STOPPED, graceful shutdown14:18:30UTC; initiator unproven. |
| Clean-machine dependency portability/provider access | NOT TESTED | Versions/pip consistency checked locally only. |
| Production activation authorization | BLOCKED | Explicitly prohibited by current request. |
| Actual loaded feature acceptance/graceful rollback | NOT TESTED | Requires future approved owned-session window after source/scope gates. |

## Validation, failures and preservation

Final canonical suite from final E/F extraction: **2253passed,3known xfailed,
0unexpected failures,2dependency warnings,240.17s**, exit0. The three xfails remain
E136independent rollback witness/dual-database rollback/atomic-recovery snapshot
gaps, not passing tests or permission to enable Discord.

Initial focused candidate:148passed/0failed15.99s. Final encoding-verified candidate:
148passed/0failed17.22s. Eight new mock capacity/failure/cache/cancellation cases;
full and focused counts overlap. All original N/O failures and archives remain.

Before final acceptance, additional AST review caught incidental Windowscp1252
mis-decoding during the initial lint edit. Only the owned isolated full-test run
was interrupted, original preflight UTF8bytes were verified against Oarchive hashes,
and intended safe edits reapplied explicitly asUTF8. Superseded A-D archives and
interrupted test output are preserved; they are not final acceptance evidence.
The final canonical AST comparisons pass, including original text/constants. Two
initial inventory/proof harness attempts also needed explicitUTF8; no such failure
is concealed as a passing test. No live backend process was signaled.

751Python artifact files compile.16Windows scripts plus1inert test fixture parse.
Dependency consistency and Git diff integrity pass. No dependencies were installed.
Ruff is deliberately reported as unresolved debt, not a passing clean check.

## Runtime safety

Preflight supported Status verified RUNNING API24804,launcher4836,run
`f670a59a-e41b-450f-9371-38208c0fc88d`. Final Status unexpectedly reports STOPPED.
At2026-10-16T14:19:27.4241463Z(09:19:27CDT),all four read-only API probes refused
connections on127.0.0.1:8000. Current Gaming configuration,PAPER reconciliation
and risk status therefore cannot be reverified. Historical O readings are not
substituted for missing current telemetry.

Atlas api.out/api.err record graceful shutdown14:18:30.653-.772UTC,including
PAPER shutdown reconciliation interrupted=3,persisted_marks=3. Stop-worker stdout/
stderr files were created14:18:27.102UTC and remain empty. This is consistent with
a controlled shutdown but does not identify its initiator. The owner/runtime records
are no longer present and supported Status says no background run is recorded.
No audit test processes remain. No restart,recovery,record reconstruction,or forced
process action was attempted. The source tests passing cannot close this runtime
continuity failure. A separate Atlas-only read-only provenance audit is required.

No explicit Atlas Start/Stop/restart or Docker command was issued by the audit.
An unattributed graceful backend shutdown nevertheless occurred during final
validation; preserve that uncertainty rather than claiming runtime untouched.
No process kill/recovery, live provider probe,
production extended-hours activation, live trading, automatic Discord, subscription/
outbox mutation, production PAPER mutation, Genesis access, shortcut edit,
protected config change, Git stage/commit/push/reset, cleanup or VPS work occurred.
Existing live services may naturally evolve PAPER evidence; no byte-freeze claim.
The permanent gaming objective and Atlas/Genesis separation remain binding.

## Complete remaining roadmap

Completed historical milestones: E131-E135isolated Discord contracts; R7E44ownership/
Gaming audit-repair-acceptance/source reliability history; R7E46Fcollector,Glocking,
Hlifespan,Ihistorical isolated soak,Krecovery contract,Lcheckpoint updater,Misolated
activation readiness,Nrelease audit,Ojournal/provider/artifact remediation.
P completes cash decision analysis, safe lint cleanup, capacity evidence and archive
verification. Cash acceptance, capacity implementation and production gates stay open.

1. **Core reliability/operations:** explicit cash scope decision; lint debt/policy
   triage; global provider budget, pacing/coalescing and bounded worker lifecycle;
   clean-artifact regressions; dependency portability if required; separately
   approved live-data/witness activation and disabled rollback; sustained recovery;
   gaming CPU/RAM/API/PAPER continuity benchmarking; safe Windows launcher,
   diagnostics and immutable backup work. R7E46Jproduction follow-up remains open;
   no R7E45benchmark or runtime optimization approval follows from P.
2. **Research Evidence Engine:** immutable hypotheses/outcomes, replay,
   precision/recall/calibration/false positives, realistic PAPER fees/slippage/funding,
   anti-lookahead/leakage, reproducible reports, Research Memory/analogues.
   E29baseline/challenger NOT_READY and context-only Alpha/cadence/corroboration gates.
3. **15-minute crypto PAPER research:** eligibility/rules/jurisdiction/fees/settlement,
   timestamped contract price/depth, spot/perp volatility/funding/liquidity joins,
   independent probabilities/calibration, executable edge, realistic fills/costs,
   actual settlement and out-of-sample regimes before any separate live proposal.
4. **Cross-Market Intelligence:** unified evidence, liquidity/positioning/anomalies,
   explainable scores, cautious suspicious-activity hypotheses, uncertainty,
   invalidation and reproducibility.
5. **Professional SaaS:** demand/pilots/tiers, auth/tenant isolation, billing/
   entitlements, versioned APIs, dashboards/exports/alerts, onboarding/support/
   analytics, data licensing and unit economics. Pricing remains unvalidated.
6. **Institutional platform:** RBAC/audit/security/incidents, reproducible workspaces/
   governance, stable APIs/metrics, licensing/compliance/requirements/enterprise pilots.
   No hosted/VPS work authorized.
7. **Commercial expansion:** fit/retention, partnerships/integrations, white-label/
   API licensing, evidence-led markets, revenue/margin/cost/churn and reinvestment.

Legacy unfinished gates: E136 independent/dual consent rollback and atomic recovery,
recipient transport/render/storage/fencing/uncertainty/deadletters, explicit Discord
approval/durable no-backfill watermark, no uncertain-send auto-retry, exactly-once
prediction PAPER predeadline auto-flat, portfolio-versus-strategy risk policy.
Historical Prediction Market Intelligence V2 PM-V2.1-PM-V2.6(discovery, probability/
calibration, executable edge, pre-event PAPER strategy, evidence/backtests, dashboard)
is preserved with one position/market, no combos/stacking/averaging/opposing YES+NO
and pre-event execution gates. New settlement research cannot silently override them.

**Single safest next execution: R7E46Q - read-only unexpected Atlas shutdown
provenance audit.** Identify the request/actor path using Atlas-only evidence and
review test/lifecycle isolation before any further runtime action. Do not start,
stop,recover or restart anything. Provider budget/coalescing/worker lifetime, vendor
license packaging,cash scope and lint policy remain subsequent unresolved gates.
No activation recommendation follows from this execution.

## Mandatory roadmap checkpoint

Supported updater completed. Backup:`PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261016-092511-e6613167.bak`.
Read-back PASS;historical bytes outside the managed block identical;permanent
strategy,recovery contract,seven phases and Prediction Market Intelligence V2 retained.
Before SHA256`6db2c467859ac87ae17998ea2614467f8fef4a722ced5dc1b7304c561d181f12`;
after SHA256`82023f940006b037e302a2c46b0a65548b1001441cbf2271ba5599354161fe87`.
See roadmap-verification.json for the machine-readable proof.
