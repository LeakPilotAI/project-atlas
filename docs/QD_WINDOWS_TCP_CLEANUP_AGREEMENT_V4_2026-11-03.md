# QD Windows TCP cleanup agreement V4

Starting checkpoint: `574f1a4c3804c493b44d4334edba110d31f2ef6c`, branch `chatgpt/atlas-rebuild-v1`. Executed November 3, 2026, America/Chicago.

**READY FOR FRESH INSTALLED ACCEPTANCE AUTHORIZATION**, based on the final offline suite and a genuine passing disposable two-cycle TCP test. This is technical readiness, not installed acceptance or permission to launch. No installed application, operational selection/rollback, support installation, journal reset, clock change, provider or financial operation occurred. No installed authorization was requested or consumed.

## Root-cause evidence

The original V3 native failure remains unchanged. Its IP Helper query sampled a particular `127.0.0.1:58766` connection to remote port `60489` at relative 0–1.1361 ms and reported FIN_WAIT1 (6)/PID 0. CIM queried at 261.7589–962.5656 ms and reported CLOSED (1)/PID 0 for the same address family and local/remote endpoint. Netstat queried at 1010.9589–1052.3495 ms and omitted that connection. A common TIME_WAIT connection was present in all readers. These were complete, fresh, distinct sequential observations, not an endpoint substitution or an evidence-age refusal. They were not an atomic snapshot. Disagreement correctly failed closed.

Source inspection identified a teardown sequencing gap: the previous HTTP diagnostics read the declared response body and closed the HTTP wrapper; they did not independently observe TCP peer EOF before proceeding to Stop and socket enumeration. HTTP body completion and local wrapper closure do not prove peer TCP teardown. A new offline test distinguishes those events explicitly.

Putting the slower CIM query first did **not** solve the problem by itself. In the first identity-corrected V4 run, CIM reported FIN_WAIT1 on the last HTTP connection while netstat and IP Helper later reported TIME_WAIT. The final strict CIM cut reported PID-0 LISTENING for that same connection. The gate refused the first cycle and never admitted the second. No state was normalized and no failed cut was recollected into a pass.

The final native run added verified peer EOF and owned client-handle closure before Stop, while retaining the revised reader order. Both cycles then passed on their first acceptance cut. This supports a client-teardown/serial-observation race as an actionable cause. It does not uniquely explain the Windows provider's earlier CLOSED, State 0 or PID-0 LISTENING representations, or guarantee every future teardown will agree. Those historical observations remain unresolved and remain refusals.

## Minimal implementation

1. `scripts/observation_runtime/acceptance_http_probe.py` retains its owned original loopback socket while parsing a bounded HTTP response, verifies actual peer EOF, sends its FIN and closes the owned socket before returning success. Missing EOF, incomplete/oversized responses, a peer that does not agree to close, invalid endpoints and exceptions refuse. Existing per-socket timeout remains at most three seconds. No fixed settling delay or repeated acceptance polling is added.
2. `scripts/observation_runtime/installed_acceptance_capture.py` supports two exact three-reader orders. The legacy default remains for existing callers; the V4 adapter uses **CIM → netstat → IP Helper → strict CIM/process roster last**. Every source is still collected once. Freshness, completeness, endpoint, state and owner requirements are unchanged.
3. `scripts/observation_runtime/installed_acceptance_capture_v4.py` provides the explicit V4 order. The reviewed worker's capture adapter uses it, and the worker's eight post-browser HTTP checks use the EOF-verifying probe. The original HTML/CSP, financial UNAVAILABLE, startup-denied and POST-403 assertions remain.
4. The V3 browser handoff, actual receipt/deadline checks, pre-selection one-use cut, original Stop, next-cycle admission, drain and rollback contracts are retained. The unchanged validators still reject any reader disagreement, active state, stale/missing source, unexpected process or ambiguous owner. No reader is removed. Forty-five-second browser and eight-second complete Stop limits are unchanged.

The previous V3 review scope/source manifest remains historical and blocked. Changed source bytes mean it must not be reused as a current execution package. The V4 increment source manifest accompanies this report and confers no operational authority. The old V3 raw evidence and earlier approval consumption are preserved.

## Native runs — failures preserved

Each native experiment used a new create-only child under `D:\Work\Project Atlas\logs\diagnostics\qd-windows-tcp-cleanup-agreement-v4-20261103`. Each had a 180-second, 1,024-entry, 16-MiB accounted-storage limit, with reserve enforced before work. Only ephemeral loopback sockets, synthetic HTTP pages and exact retained test children were used. No browser signoff was synthesized; these were TCP lifecycle tests, not genuine installed dashboard tests.

| Run | Result | Duration | Retained entries / logical / accounted bytes, including result |
| --- | --- | --- | --- |
| `native-run` | FAILED fixture identity assertion before two-cycle validation | 16.5690753 s | 66 / 121,209 / 391,545 |
| `native-run-image-corrected` | FAILED first-cycle disagreement and PID-0 LISTENING; no second Open | 16.1529821 s | 79 / 143,845 / 467,429 |
| `native-run-eof-drained` | **PASSED both cycles and final readback** | 23.7259984 s | 114 / 287,556 / 754,500 |

The first run uncovered an additional fixture-only defect: comparing the READY executable path case-sensitively against the native observer's already canonical, case-folded path. The corrected check uses the existing native observer's canonical Windows-path contract, retains exact PID/creation/image verification, rejects foreign paths and captures the compared values. Its new tests reject missing flags, integer-zero substitutes, foreign images/PIDs/releases. The first run did not retain per-assert identity values; no exact observed pair from that failed run is invented. The corrected run independently captured the genuine same-image pair.

No failed run was resumed. Each fresh experiment had separate evidence and children. Within each run, a failed acceptance cut latched refusal; it was not resampled into acceptance. Separate diagnostic observations of a released held-FIN socket did not grant admission to its failed held-FIN attempt.

### Passing two-cycle evidence

| Cycle | Port | Stop ACK component | Complete Stop + socket/process readback, including final drain where applicable |
| --- | --- | --- | --- |
| 1 | 49872 | 0.0206046 s | **2.3749056 s** |
| 2 | 65092 | 0.0153382 s | **2.3473608 s** |

For each cycle, all three readers independently returned the same four TIME_WAIT (11)/PID-0 connections, matching both endpoints. The final strict CIM/process snapshot passed afterward with zero unexpected processes. The original `AcceptanceController.next_cycle` admitted the second cycle only after first-cycle Stop and both socket/process checks. Final EOF/drain exited normally; independent final readback for both HTTP ports passed. TIME_WAIT is an existing allowed terminal state, not evidence that all rows disappeared. No FIN_WAIT1, FIN_WAIT2, CLOSED-vs-other-state disagreement or PID-0 LISTENING was accepted.

### Coverage and limits of the native evidence

| Condition | Evidence and result |
| --- | --- |
| First and second clean cycle | Genuine final native run: unanimous fresh TIME_WAIT and strict process clearance; both passed |
| Rapid teardown, FIN_WAIT1, CLOSED and absent row | Original V3 raw evidence retained; new identity-corrected run independently reproduced FIN_WAIT1 → TIME_WAIT disagreement; both failed |
| FIN_WAIT2 | Genuine held peer: native states included 7; active connection refused; peer EOF and owned closure performed afterward |
| TIME_WAIT / absent endpoint | Genuine three-reader terminal agreement and separate never-connected closed endpoint passed |
| Retained listener / State 0 | Genuine held-listener observations refused; raw State 0 remained unnormalized |
| PID-0 LISTENING | Genuine strict CIM observation in the failed V4 run refused; underlying Windows representation remains unexplained |
| Unexpected process ownership | A deliberately unclaimed, exactly owned fixture child caused `APP_PROCESS_NOT_RELEASED`; its normal EOF exit was verified |
| Missing/stale reader, conflicting owner/endpoint | Offline adversarial tests refused; no claim these were genuine fresh OS observations |
| Cleanup/rollback | Genuine owned socket/child/helper cleanup; actual worker failure-finally/UNKNOWN/no-retry rollback coverage offline with mocked effect ports. No operational or native selector rollback performed |

The final native run closed 30 query handles and two child handles; the earlier runs closed 18 and 21 query handles and two child handles each. Children exited 0, without forced termination. The first failure's unrecorded HTTP port was not reconstructed. The later strict process checks establish no surviving unclaimed Atlas/test Python processes; final known-port readback is separately retained. Do not promote a later clear readback into a pass for either failed run.

Final read-only verification covered **15 known disposable ports** across all three runs. Every fresh three-reader cut and subsequent strict process snapshot passed; all **45 additional query handles** closed. It created no listener, took **32.6255353 seconds**, and stayed within its 90-second/512-entry/8-MiB limits (166 entries, 206,162 logical and 886,098 accounted bytes including result serialization). The unrecorded first-failure HTTP port remains explicitly outside exact endpoint readback rather than being invented. Both original failures remain failures.

## Regression and preservation

**421 passed, 0 failed, 0 skipped, 22.90 seconds**, comprising the unchanged 382-case V3 selection plus 39 new cases. New coverage includes ordered single-cut capture, active/terminal states, missing/stale/conflicting source evidence, refusal latching, worker integration, fixture identity and HTTP response-versus-EOF/handle sequencing. Earlier 35-, 28- and 38-case focused selections overlap and are not additional distinct cases. Final lint and formatting checks passed for six changed/new core and fixture files; Python/PowerShell parsing and the static PAPER policy audit passed (652 sources, zero issues). No financial-accounting or risk validator was weakened.

Evidence root also retains raw observations, process ownership comparisons, fixture ACKs, native results, offline output and final known-port readback. The default managed process's ordinary CIM inventory query was denied; no permissions/configuration changes followed. Authorized native tests used a normal nonadministrator Windows process with the existing supported native query interfaces, not elevated Atlas or changed ACLs.

The canonical roadmap uses its archival updater. Recovery state retains the complete previous result/blockers; queue and continuation history are preserved. Unrelated research-test changes and untracked evidence remain excluded from the commit. Original UI, protected financial stores, installation receipt/ACK/journal, B1/C1/D1/E1, all 21 decisions and seven phases remain unchanged.

## Readiness and exact next action

**READY FOR FRESH INSTALLED ACCEPTANCE AUTHORIZATION** is limited to the demonstrated source/disposable TCP prerequisites. A passing two-cycle TCP test is not a completed Control Center/browser/financial acceptance run. Original browser acknowledgement and pre-selection safeguards are preserved, but the EOF probe and revised sampling order have not been exercised against the genuine installed application.

Next: prepare and review a fresh exact V4 installed acceptance package binding the current source, fresh diagnostic root and independently reread selector baseline. Do not reuse the old V3 source pins, root or grant. No authorization is requested here. Any later installed run needs separate explicit approval, fresh clock acceptance, complete release/support/receipt/ACK/journal/native-identity/ACL verification and rollback readiness.

Last independently verified selector baseline remains **UNSELECTED revision 6**, head `c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc`; no operational readback or mutation was performed in this task. Financial enrollment, custody/current research, executable IEX, fresh clock and financial commissioning gates remain unaccepted by this evidence. No PAPER account or pilot result is claimed.

**STOP after validation, checkpoint, commit, push and remote verification. PAPER: NO. Production: NO-GO.**
