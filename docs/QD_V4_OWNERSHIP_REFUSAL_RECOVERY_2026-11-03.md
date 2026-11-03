# V4 ownership-refusal recovery — historical identity unresolved

**BLOCKED: PID 19940's historical ancestry and retained-launch identity are unproven. The original installed acceptance remains FAIL; its single-use grant is consumed.** Recovery began at `f9bc9692a77224ba27dbae0a963c08995e6685f4` on `chatgpt/atlas-rebuild-v1`. No installed Atlas launch, selector publication, provider access, financial action or Windows configuration change occurred during recovery.

## Interrupted work recovered

The previous execution completed the failure-report draft, derived evidence summary, canonical roadmap archival update, recovery JSON update, execution-queue prefix and commissioning-continuation prefix. It stopped before final preservation review, staging, commit, push and remote verification. These changes were recovered rather than regenerated. The unrelated pre-existing modification to `tests/test_free_research_pipeline.py` was preserved and excluded from this increment.

The original result is documented in `QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_RESULT_V4_2026-11-03.md`. Retained evidence is under `logs/diagnostics/qd-final-installed-nonfinancial-acceptance-v4-20261103`; it was not reset, overwritten or re-executed.

| Original V4 result | Preserved finding |
| --- | --- |
| Clock | Accepted 704 ms; synchronization age 8.5643160 s; temporary capability revoked |
| Native integrity | Eight groups passed, 20.8151692 s |
| Ownership | Refused unclaimed PID 19940; all three declared native scalar comparisons passed |
| Installed Open / browser / Stop cycles | Zero; both cycle timings unavailable |
| Selection / rollback | Neither attempted; no rollback required |
| Preservation | 17 original files unchanged; selector contained only revisions 1–6 |
| Final recorded selector | UNSELECTED revision 6; no revision 7 or 8 |
| Authorization | Consumed by the single failed attempt; no retry |

## Exact process evidence

The metadata capture observed PID **19940** with executable:

`D:\Work\Project Atlas\backend\.venv\Scripts\python.exe`

Its complete recorded command line was:

```text
"D:\Work\Project Atlas\backend\.venv\Scripts\python.exe" -I -B "D:\Work\Project Atlas\logs\diagnostics\qd-final-installed-nonfinancial-acceptance-v4-20261103\supervise.py" --execute-one-approved-installed-acceptance 737d3f6fea4cda5d60194ea03f619d5d778acd0b6fcf60ebfde78cb815b8dd84 f9bc9692a77224ba27dbae0a963c08995e6685f4
```

The CIM JSON creation value was `/Date(1793701401874)/`, or **2026-11-03T10:23:21.874Z**, at millisecond serialization resolution. It is not an exact native FILETIME observation and cannot substitute for the missing original process handle.

| Required investigation | Evidence and limit |
| --- | --- |
| Parent process identity | **Not captured.** The metadata projection omitted `ParentProcessId`; no retained parent creation/image/handle record was found. Do not query a reused PID now to reconstruct history. |
| Relationship to supervisor | The command names the exact approved supervisor, scope hash and checkpoint. The separately declared running supervisor was PID 24704, base Python, exact native creation `134381750018854599`. A wrapper relationship is plausible, not independently proved. |
| Authorized helper role | Supervisor orchestration was an approved role, but PID 19940 was not bound to it by the approved retained-identity claims. A matching command alone does not establish ownership. |
| Three declared identities | Supervisor self PID 24704; retained worker launch PID 28996; running worker PID 21700. Each PID/creation/image comparison passed. |
| Why excluded | `supervise.py` passes only `observe_pid(os.getpid())`; the worker appends its retained primary launch claim and its own running identity. No outer supervisor-launch identity is included. |
| Was the roster incomplete? | The roster did not cover this observed process. Whether it was a legitimate omitted wrapper, rather than an unauthorized process with a matching command, remains unresolved. |
| Did the harness launch it? | The recorded launch command and Windows venv/base-image pattern support that hypothesis; original parent/launch-handle proof is missing. It cannot be asserted as established historical fact. |
| Was refusal correct? | **Yes.** An in-scope observed process had no verified claim. The guard correctly refused instead of adopting it. |

The existing `disposable_host_owner.py` explicitly documents Windows virtual-environment redirectors spawning a second PID and uses a directly retained interpreter for its separate disposable host. That supports a possible mechanism, not retrospective proof for PID 19940. The original metadata guard verifies PID, native creation time and image for claimed candidates; it does not independently bind command, parent or every declared claim's presence. The separate fixture command observer can verify retained process continuity, command, parent and account but deliberately grants no startup, shutdown or independent ownership authority.

**No production roster or allowlist was changed.** The evidence does not meet the condition for certifying PID 19940 as an omitted legitimate helper. In particular, no PID exclusion, command substring exemption, broad parent exception or post-failure identity adoption was introduced.

## Offline validation

Added `tests/test_v4_ownership_refusal_recovery.py`, **24 new passing cases**:

- Actual metadata ownership block, with CIM and process observations replaced by fixtures: supervisor/helper matches; undeclared wrapper and child refusal; missing helper claim; executable mismatch; stale creation/PID reuse; wrong or malformed PID; missing image; empty claims; enumeration failure. Identity mismatch paths dispose the mocked process observation.
- Existing retained fixture command observer: exact context passes observation only; command, parent, executable, creation/PID reuse, missing context, account, missing row and duplicate row refuse. All CIM/account queries are mocked. The only retained live Process is the disposable PowerShell test process itself. Even a matching observation explicitly returns ownership/startup/shutdown/production authority false.

Adjacent existing suites passed **126 cases**: resource-audit parser, owned handle cleanup, installed-acceptance cleanup and sequencing. Combined distinct final coverage: **150 passed, 0 failed, 0 skipped**. The final 24-case run took 11.31 s; adjacent 126-case run took 5.58 s. No installed application, operational store or provider was used by these tests. Tests are evidence of existing refusal behavior and fixture context checks, not a corrected installed ownership contract or passing installed acceptance.

The first test invocation had **24 setup errors** because its new reporting parent directory did not yet exist; no test body ran. After creating that workspace-only directory, all cases passed. An import-order lint finding was corrected in the new test file; final no-cache lint passed. Logs/XML remain in `logs/diagnostics/qd-v4-ownership-refusal-recovery-20261103`. The original 303/421 passing evidence and all historical failures remain preserved, not relabeled as new results.

## Next prerequisite and boundaries

Before another installed attempt, review a launch boundary that retains and verifies every supervisor/redirector/worker role from creation: exact executable and command, parent **identity** (PID plus creation/image, not PID alone), process creation time, native launch handle and lifecycle/Job relationship. Missing, stale, reused, unexpected or unverifiable processes must refuse. Alternatively review an exact wrapper-free launch that preserves runtime dependencies and native ownership. Neither proposal is implemented or certified by this recovery because the historical prerequisite is unresolved.

A **new approval package is required** after any verified correction: new source/scope pins and unused evidence root, actual selector-baseline reread, full installation/receipt/ACL/clock/socket/process preflight, and a fresh explicit single-use operator grant. Never reuse the V4 claim or historical 704-ms clock evidence. No additional approval chain or external reviewer is introduced.

The last independently verified operational selector remains **UNSELECTED revision 6**, head `c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc`; original post-abort byte/namespace preservation supports that result. This recovery used retained evidence and source only, not a fresh operational native selector read. All B1/C1/D1/E1 gates, 21 decisions, seven phases, protected accounts, original UI and Genesis isolation remain unchanged. Financial commissioning still requires accepted current research/executable IEX, financial custody/authority and separately authorized inception/PAPER execution. **PAPER: NO. Production: NO-GO.**

Stop after recovery, validation, documentation and verified Git synchronization. No installed acceptance retry is authorized by this milestone.
