# Three-reader cleanup acceptance feasibility — demonstrated without gate changes

Starting checkpoint **ed6ac8e5428aa10e613df40e2d9e511cdedc9f4e**, branch `chatgpt/atlas-rebuild-v1`.

**FEASIBILITY: READY for review of a fresh, separately authorized installed nonfinancial acceptance-only test. The current cleanup contract passed three genuine disposable next-cycle admissions and refused a retained-listener fault. No gate weakening or product-source correction is required. Installed acceptance was not executed or accepted; PAPER startup remains unauthorized.**

This is a bounded feasibility result, not proof of indefinite reliability or an explanation of every historical Windows observation. The underlying State-0 behavior and the historical PID-0 LISTENING event remain unresolved.

## Exact contract and experiment

The unchanged `AcceptanceController.next_cycle` requires an accepted Stop, a fresh CIM/process assessment, unanimous usable CIM/IP_HELPER/NETSTAT evidence collected after Stop, and native controller PID/creation/image verification before writing `NEXT`. Missing, stale, ambiguous or conflicting evidence refuses; a refusal latches. The CIM/process cut must be no more than two seconds old, each collection at most five seconds, and the oldest corroborating reader at most ten seconds old. Eight-second Stop and all operational authorization requirements remain unchanged.

One retained **disposable raw-socket controller**, not installed Atlas, exercised four OS-assigned IPv4 loopback listeners. Its native creation handle, PID, image and creation time were verified using the existing ownership functions. All helper/process exclusions used actual retained diagnostic identities and the original strict scalar identity checker. This is not acceptance of an operational writer roster.

The first two cycles had no client connection. The third used one owned loopback client. The fourth deliberately issued a **false close acknowledgement while retaining its real listener**, as an explicitly labelled negative fixture. This acknowledgement was test protocol data, not an operational or financial receipt. The external socket/process checks had to reject it.

Before execution, exact bytes and hashes of the observer, decoder, ownership/pipe helpers, PowerShell collectors and both fixture scripts were retained in the private source snapshot. Before/after hashes matched; **no public application, support, observer or contract source changed in this milestone**.

## Native observations and admissions

All endpoints were **TCP / IPv4 / 127.0.0.1**. Positive owner values matched the retained disposable controller; actual machine/process identifiers remain private. Native IP Helper also queried IPv6 tables; IPv6 listener operation was not exercised. Existing offline IPv6 coverage was retained and rerun.

| Cycle / port | While physically listening | Repeated post-Stop observations | Actual admission |
|---|---|---|---|
| 1 / **50861** | Native/CIM State 0; netstat omitted the listener | Two fresh cuts: all three complete enumerations had no scoped row; process assessment passed | **NEXT accepted** |
| 2 / **52204** | Same active State-0/omission behavior | Two fresh cuts: all three had no scoped row; process assessment passed | **NEXT accepted** |
| 3 / **55011** | Native/CIM listener 0 plus established 5; netstat showed established 5 | Two fresh cuts: all three agreed on terminal **TIME_WAIT/11, PID 0**; process assessment passed | **NEXT accepted** |
| 4 / **55021**, fault | Real listener retained after the deliberately false close ACK | Both cuts retained Native/CIM State 0 while netstat omitted it; cleanup refused | **NEXT refused** |

The negative admission raised **`SECOND_OPEN_SOCKET_OR_PROCESS_CLEANUP_UNRESOLVED`**. The controller's event log recorded exactly **three NEXT commands and four listener creations**. It received no fourth NEXT after the fault. EOF then closed that fixture normally. The refusal remained latched even when a later final observation was clean; it was not silently reset.

The final fresh sweep covered **all four created ports** after controller exit:

- Ports 50861, 52204 and 55021: complete scoped row disappearance through all three readers.
- Port 55011: all three still reported only the terminal TIME_WAIT/11, PID-0 row. Full disappearance of this terminal TCP row was not observed or forced.
- All four fresh CIM/process assessments passed, with no unexplained application process. No listener or active connection remained at the tested endpoints.

Empty netstat output was **never sufficient** for admission: it also occurred while the fourth listener was genuinely retained, and that case refused. Positive admissions required actual closure in the owned fixture, its bound Stop acknowledgement, successful complete fresh enumerations, strict process/identity checks and the complete three-reader conjunction. Query silence, a missing result, an exception or an unverified owner cannot substitute for that evidence.

## Demonstrated collection sequence

The fixture collected the three-reader bundle first, then refreshed the existing CIM/process-roster snapshot **last**, immediately before invoking the real admission method. It did not mock, replace or bypass the native observer.

Across the six normal post-Stop cuts:

- Strict CIM/process snapshot age: **23.5564–26.3459 ms**, below the unchanged **2,000 ms** maximum.
- Oldest corroborating reader age at assessment: **2,155.441–2,296.437 ms**, below the unchanged **10,000 ms** maximum.
- Three actual `next_cycle` invocations accepted and advanced the disposable protocol. No synthetic success callback was installed.

This sequence avoids ageing the stricter snapshot while collecting the other views and demonstrably fits the existing limits. **No alternative-order comparison was run; the evidence does not prove that every other order would fail.** A future harness should reuse the demonstrated sequence or verify equivalent freshness with measurements, rather than enlarge the freshness allowance. It must supply the complete bundle; the old review-only worker patch does not implement that assembly and must not be blindly replayed.

Normal fixture Stop observations were **12.0115, 12.3983 and 11.9699 ms**. These are disposable socket-controller measurements, **not installed Control Center or financial Stop acceptance**. The fault's fast false ACK was not treated as evidence that its socket had closed.

## Agreement analysis and remaining uncertainty

| Condition | Result / classification |
|---|---|
| Complete closure with no connection | Achievable: repeated complete three-reader agreement and native admission |
| Terminal TIME_WAIT / owner 0 | Achievable: accepted only as documented terminal socket evidence with the other Stop/process/identity checks |
| Active State 0 | Remains unexplained and unaccepted; present again in native/CIM evidence |
| Reader omission | Observed again in netstat while the real listener was active; never counted as affirmative clearance |
| Retained real listener after false ACK | Refused; subsequent cleanup did not reset the refusal |
| PID 0 with LISTENING | Not reproduced natively here; historical failure remains unexplained. Existing offline cases require refusal |
| Missing owner / conflicting ownership | Covered by offline regressions; no native conflict fabricated or passed |
| Stale/partial/error observations | Existing refusal tests passed. No native enumeration error occurred in this run |

The readers still cannot supply usable agreement that these active sockets have documented LISTEN state 2. **That does not make the post-Stop cleanup contract unachievable**: it requires valid agreement after genuine closure, not acceptance of the active State-0 observation. State 0 was never mapped to LISTEN or to a harmless terminal state. The earlier native witness failure and the historical installed PID-0 LISTENING failure are preserved exactly as failures.

## Validation, bounds and cleanup

- **156 passed / 0 failed / 0 skipped, 5.83 seconds**, relevant socket-decoder/reconciliation, controller and mocked PowerShell regressions. No product implementation changed, so the unrelated 162-case support/selector/launcher portion of the prior **318-pass** suite was not unnecessarily repeated; that evidence remains intact.
- Lint and format checks passed for all five relevant Python files. Exact observer source bytes remained unchanged throughout the native test; Python fixture parsing and source/hash preflight passed.
- Native run: **32.8978541 seconds**, under its **120-second / 512-entry / 8-MiB** bound. At result publication: **147 entries / 2,070,243 logical bytes / 2,672,355 accounted bytes**. Later regression/documentation artifacts are not represented as part of that native-session counter.
- The sole fixture controller exited **0**, with accepted EOF/drain, empty stdout/stderr residue and its original handle closed. All **44 query-helper processes/handles** closed normally. The owned client received EOF and closed. No timeout, forced termination or unrelated-process interference occurred.
- Exact raw source snapshots, endpoints, owners, monotonic timestamps, API codes, typed CIM data, scoped netstat bytes, process roster comparisons and the negative fault event are private under `D:\Work\Project Atlas\logs\diagnostics\qd-three-reader-feasibility-v1-20261102`. See `result.json`, `probe-events.jsonl`, `source-manifest.json`, `source-snapshot`, per-cut raw files and `regressions.xml`.

This sample demonstrates repeated achievability, not a statistical long-duration reliability guarantee. Future missing, stale, unsupported or conflicting observations must still block admission.

## Recommendation and authority boundary

**Recommendation: READY at the cleanup-contract feasibility level for review of a new bounded installed nonfinancial acceptance-only handoff.** No source correction or threshold change is needed. Prepare/review the exact orchestration assembly using the proven collection sequence, current source hashes and complete bundle before requesting execution. Any fresh installed test still needs explicit operator authorization, fresh qualifying clock evidence, exact application/support receipt/ACK/native identities, actual UNSELECTED revision-4 preflight and all existing checks. No installed run was automatically attempted here.

**Installed release acceptance remains unperformed/unaccepted; PAPER and production remain blocked.** No operational selector readback, selection, rollback, support reinstallation, journal reset, frozen-payload/shortcut change, provider connection, financial activation, Windows networking/time change or Genesis modification occurred. The recovered **UNSELECTED revision-4** baseline remains preserved. All B1/C1/D1/E1 requirements, 21 decisions, seven phases, protected accounts, original UI, historical failures and unrelated work remain unchanged. The canonical roadmap and recovery state archive the prior checkpoint and record this bounded result. **Stop after this validation. PAPER NO. Production NO-GO.**
