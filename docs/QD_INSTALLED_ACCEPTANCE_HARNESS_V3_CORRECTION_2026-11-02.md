# QD installed acceptance harness V3 correction

Executed November 3, 2026 (America/Chicago), from `395ca25b8cff1c7bcf489a7fc2c1bc11bb46174b`. The filename retains the date explicitly requested by the operator.

**Result: BLOCKED — required disposable native second-cycle cleanup validation failed.** Source corrections and offline regression coverage are complete. Installed acceptance has not passed. No installed Atlas launch, operational selection/rollback, support installation, journal reset, provider connection, financial operation or new operational authorization consumption occurred.

## Browser acknowledgement findings and correction

The original V2 record remains a failure. Its ACK wait began only 14.3128 ms after the recorded READY observation; navigation was requested 23.3697119 seconds after that wait began. The genuine render/ACK attempt occurred at 45.7370666 seconds, 0.7370666 seconds beyond the unchanged 45-second deadline. No earlier ACK file was awaiting receipt. First paint was not independently measured. The evidence establishes late browser coordination, not slow page rendering or a proven clock/receipt race.

V2 ran serial HTTP diagnostics before requesting the browser and its supervisor performed accounting/status work before relaying the request. The old ACK helper also wrote diagnostic events before publishing ACK. That last ordering could delay a future ACK, but cannot explain away this already-late attempt.

The corrected shared sequence now verifies the existing READY/image contract, immediately publishes a nonce-bound browser ticket and notifies the supervisor, waits for genuine browser acknowledgement, and only then runs unrelated HTTP diagnostics. The supervisor relays the request before accounting/report work. The helper publishes ACK before optional output. Explicit signoffs still require actual READY/image verification, dashboard rendering, financial-unavailable state and closure of the test tab. A ticket is never browser success.

The deadline starts at verified READY, before diagnostics or navigation, an earlier/conservative origin compared with V2. It remains 45 seconds. Both generation and actual consumer receipt must be timely; a timely-generated ACK received late refuses. Missing, malformed, contradictory or late evidence latches refusal. Tickets bind exact release/image, host, selection head, loopback origin, cycle, nonce and monotonic timestamps. Operational and disposable domains remain distinct. The window and pre-selection capability are bound to their creating process/thread. Timely browser receipts and Stop ACK observer receipts persist before unrelated work can obscure later failures.

An initial offline run found that unnecessary hardlink publication of this nonfinancial coordination file was denied in the managed process context. Windows ACK publication now uses atomic, no-replace rename; POSIX retains no-replace hardlink behavior. This changes no native financial codec, custody rule, ACL or financial acknowledgement.

## Pre-selection evidence correction

V2 had source/ownership checks before selection but omitted its separate fresh three-reader socket cut. Its later clear final sweep cannot retroactively satisfy that requirement.

The V3 worker collects fresh IP Helper, raw CIM and netstat evidence for the retained exact endpoint, then refreshes the stricter CIM/process snapshot last. The retained V2 READY record identifies `127.0.0.1:52159` only; it is not current socket evidence. Immediately before the selection callback, the one-use capability independently revalidates raw observations, endpoint identity, timestamps, process ownership and ordering. Missing evidence, stale observations, listener ambiguity, State 0, PID-0 LISTENING and disagreement all refuse. Cached `accepted: true` is not authority. No unrelated diagnostics run between validation and dispatch.

The original 2-second process snapshot, 10-second reader age, 5-second collection and eight-second complete Stop requirements are unchanged. Cycle cleanup must match that cycle's READY endpoint. A cleanup or timing refusal latches; a later clear sample does not revive the cycle.

## Source implementation

- `scripts/observation_runtime/installed_acceptance_handoff.py`: bounded, exact, deadline-aware genuine browser ticket/receipt protocol.
- `scripts/observation_runtime/installed_acceptance_sequence.py`: immediate browser handoff; raw pre-selection revalidation; existing Stop/cleanup/drain gates; durable observer receipts.
- `scripts/acceptance_browser_ack.py`: explicit genuine-browser signoff command, default refusing and confined to diagnostics.
- `scripts/acceptance_harness_v3/`: source-controlled review templates for gate, supervisor, worker, capture, preflights, PowerShell controller and known-head rollback. Original V2 scripts/pins are preserved.
- Five test/fixture files cover the protocol, real worker failure-cleanup block with mocked effect ports, and disposable native orchestration.

The new 113-file source manifest and blocked review scope are in `docs/QD_INSTALLED_ACCEPTANCE_HARNESS_V3_SOURCES_2026-11-03.json` and `docs/QD_INSTALLED_ACCEPTANCE_HARNESS_V3_SCOPE_2026-11-03.json`. These are review artifacts, not an execution approval. Operational entry explicitly refuses the blocked status before creating a claim or native Job. No future run may reuse an old grant/root or alter this status without fresh verified evidence and review.

The last genuinely verified operational baseline remains UNSELECTED revision 6, head `c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc`. It was not reread operationally in this task. A future reviewed run would need current baseline verification, fresh clock acceptance, exact application `2c039af29dfefd1df77e0caa3db3fdf5ed188118`, support/receipt/ACK/journal verification, temporary revision 7 and known-head rollback revision 8 restoring revision 6. No such mutations occurred here.

## Validation and preserved failures

| Validation | Result |
| --- | --- |
| Initial ACK coordination tests | 48 passed, 18 failed, 2.74 s; hardlink permission refusal preserved and corrected as described above |
| Final relevant offline selection | **382 passed, 0 failed, 0 skipped; 18.88 s** |
| Final changed-source selection | **88 passed, 0 failed, 0 skipped; 3.62 s**, overlapping the 382 cases, not additional distinct cases |
| Required disposable native run | **1 failed, 0 passed; 56.3377623 s** |
| Static PAPER policy audit | 650 source files, 0 issues; no operational acceptance/startup authority |

The offline selection covers browser in-time/late/missing/late-receipt behavior, timing origin, malformed signoffs, identity/endpoint substitution, missing/ambiguous/disagreeing/valid pre-selection cuts, one-use refusal, sequencing, actual worker finally-block behavior under disposable mocked ports, rollback UNKNOWN/no retry, cleanup/drain errors, existing socket/ownership safeguards, roadmap archival and release policy. Syntax parsing and no-cache lint/format checks passed for the new core helpers and tests; PowerShell review templates were parsed without execution.

The native test used an explicit synthetic HTTP child and ephemeral ports, not Atlas or an operational account. Its held-listener negative pre-selection test correctly refused without dispatch. After closure, genuine fresh three-reader evidence admitted the fixture BEGIN callback once. This was an in-memory fixture action, never release selection.

Two genuine in-app browser observations confirmed clearly labelled synthetic pages with financial values UNAVAILABLE. Cycle 1's consumer received ACK at 25.2533001 seconds; its complete Stop/readback took 2.0998932 seconds (child Stop component 0.0135209 seconds), and the unchanged next-cycle gate admitted cycle 2. Cycle 2's witness generated ACK at 22.002712 seconds; the receipt gate completed before Stop, but its exact receipt timestamp was not retained after the failed cycle result. The later source refinement persists receipts before subsequent failures. No exact cycle-2 receipt time or successful complete second Stop is claimed.

After cycle 2 Stop, the same transient connection appeared as IP Helper `FIN_WAIT1` (6)/PID 0, CIM `CLOSED` (1)/PID 0, and absent from netstat; a common TIME_WAIT row was also retained. The existing reconciliation refused `CROSS_SOURCE_DISAGREEMENT`. A passing single CIM/process snapshot did not override this failure. No normalization, retry into a pass, deadline extension or operational retry followed. The native test therefore **failed** even though the child exited normally.

Later independent read-only cleanup found both created HTTP ports (`65105`, `58766`) empty in all three complete fresh readers and accepted strict process snapshots. That establishes final resource cleanup, not a successful second-cycle acceptance. Literal State 0 observed in the held-listener test remains unnormalized; the older unexplained installed PID-0 LISTENING finding is not resolved by these terminal states.

The final endpoint, refusal-latch, thread-ownership and receipt-preservation refinements were verified offline after this native run. They have not received a new successful native lifecycle run. Genuine installed dashboard, READY/origins and installed rollback were not exercised. Rollback/failure-finally behavior was tested offline against the actual worker AST with mocked effect ports. Browser screenshot capture returned an error; accessibility evidence and that error are retained, with no claimed standalone visual image or installed dashboard acceptance.

## Resource containment and cleanup

Evidence root: `D:\Work\Project Atlas\logs\diagnostics\qd-installed-acceptance-harness-v3-correction-20261103`.

Native child scope: `native-run`, 180 seconds, 1,024 entries, 16 MiB accounted storage, with cleanup reserve. At result: 51 entries, 83,545 logical bytes, 292,441 accounted bytes. After final read-only cleanup evidence: 75 entries, 125,407 logical bytes, 432,607 accounted bytes. Duration 56.3377623 seconds; all bounds respected. Evidence is retained rather than deleted.

The test child drained on EOF and exited 0; its retained handle closed. Twelve diagnostic helper handles and six additional final-readback handles closed. No forced termination or unrelated process termination occurred. Both browser test tabs closed. No installed application ports were bound. No operational rollback, release selector, provider, financial writer, Windows Time/network setting or Genesis resource was used or changed. Ordinary existing Python test tooling was used; no software or runtime deployment was installed elsewhere.

Private raw evidence includes `native-run/result.json`, `native-run/after-refusal-final-cleanup.json`, `validation-summary.json` and static audit output. Existing V2 evidence, its consumed authorization, original 45.7370666-second failure, protected installation history and unrelated work remain preserved.

## Readiness and next boundary

**V3 remains BLOCKED**, as required when a mandatory native test fails. The smallest next engineering task is disposable TCP teardown/observation feasibility under the unchanged strict three-reader and eight-second gates, with retained transient-state evidence. The underlying Windows cross-reader timing disagreement remains unresolved; no system configuration correction is justified by this run alone.

Do not request or perform another installed acceptance until required disposable validation succeeds and an exact updated scope/source manifest/current baseline is reviewed. Any installed run still requires a new explicit single-use authorization and all fresh preflight checks. This task stops after offline correction, evidence preservation, checkpoint, commit and push. The original alien-themed frontend, B1/C1/D1/E1, all 21 decisions and seven phases remain unchanged. **PAPER: NO. Production: NO-GO.**
