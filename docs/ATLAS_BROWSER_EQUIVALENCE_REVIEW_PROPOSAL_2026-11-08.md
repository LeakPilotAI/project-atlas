# Atlas browser acceptance: proposed equivalent-contract review (2026-11-08)

Status: PROPOSAL ONLY. NOT APPROVED. NO GATE CHANGE. PAPER PRODUCTION NO-GO.

## Existing constraint
The November 7 commissioning report requires a trusted Windows Chrome tab provider, verified tab identity/current URL/post-navigation origin, and independent active-listener agreement. A terminal-driven Chrome run, HTTP 200, DOM dump, screenshot, or generic browser tool is not automatically equivalent. The October 26 headless Chrome acceptance was synthetic and cannot be promoted to operational acceptance.

## Proposed review path
1. Identify the original signed/approved browser witness contract and the exact origin/identity evidence it requires. Retain it unchanged as the baseline.
2. Evaluate whether an operator-owned local Chrome DevTools Protocol session, launched with an isolated temporary profile and explicit loopback endpoint, can provide independent tab identity, navigation, current origin and final rendered dashboard state. Treat CDP as an untrusted candidate until independently reviewed. Do not attach to an existing personal Chrome profile or enable remote debugging on the normal profile.
3. Collect browser witness, native listener, CIM/IP Helper and netstat observations independently, preserving their raw disagreements. Do not infer listener agreement from HTTP success or SO_ACCEPTCONN alone.
4. Confirm browser witness binds to the exact installed application, release, owned child PID, loopback origin, and bounded session, and that graceful Stop releases owned resources with no unrelated process termination.
5. Require explicit review and acceptance of any equivalent contract before using it for an operational gate. Until then, run only isolated disposable diagnostics and label them NONFINANCIAL / NOT ACCEPTED.

## Fail-closed criteria
Missing provider identity, missing independent listener evidence, disagreement between readers, stale browser origin, unexpected profile, missing owned-child binding, or incomplete Stop witness => REJECT. No relaxation of existing acceptance predicates. No financial enrollment, startup, source publication or account inception is authorized by this proposal.

## Other independent blockers
Native Quality Dips and Hyperliquid enrollment, accepted provider rights and current market evidence, source publication, financial Start/Stop flatten/reconciliation and multi-day supervised PAPER soak remain separate gates. Browser acceptance alone cannot authorize full PAPER production.

## Operator burden
No additional Chrome installation or user setup should be requested before this candidate is reviewed against the original contract. The existing VS Code Desktop Commander terminal connection is not a trusted Chrome tab provider.

## 2026-11-08 native disposable listener recheck (not accepted)
Executed opt-in `tests/test_acceptance_socket_native_disposable.py` on Windows using an ephemeral owned loopback child (no installed Atlas host and no financial operations). The test FAILED at the `listening` collection: the resource audit exited 2 with `APP_PROCESS_NOT_RELEASED`; CIM returned a scoped TCP row for the disposable port with `state: 0` rather than an independently accepted LISTENING observation. This does not establish three-reader agreement. Do not promote browser CDP preview success into Gate 1 acceptance. The current native resource audit/reader disagreement requires diagnosis under unchanged validators before retrying genuine installed-host browser commissioning.

## 2026-11-08 audit failure investigation
Read-only inspection of `scripts/windows/Atlas-Acceptance-Resource-Audit.ps1` established that `APP_PROCESS_NOT_RELEASED` is raised when its global Atlas-path Win32_Process query returns any process outside the `ATLAS_AUTH_HELPER_CLAIMS` roster, even when the queried ephemeral listener is healthy. A separate read-only CIM process inventory observed pre-existing Atlas-venv `python.exe` and `ruff.exe` processes (PIDs 28536 and 27788 at observation time), both parented by PID 26332; neither was started or terminated by this investigation. The disposable test only claims its pytest process and parent, so a global process-absence requirement cannot be satisfied while these unrelated development processes remain. This explains the audit error but does NOT resolve the separately observed TCP `state: 0`, nor establish three independent LISTENING readers. Do not loosen the audit, kill unrelated processes, or promote Gate 1. A bounded owned-process test environment or explicitly authorized process-lifecycle isolation is needed before the next acceptance attempt.

## 2026-11-08 direct three-reader ephemeral comparison
Added `scripts/observation_runtime/disposable_listener_reader_diagnostic.py` to compare CIM, native IP Helper, and netstat on the same temporary Python-owned loopback listener without calling the global process-cleanup audit or starting the installed host. First actual run: scoped port 55324, owner PID 30040; CIM state=0 and owner=30040, IP Helper state=0 and owner=30040, netstat returned no scoped rows. The listener was closed on exit. These results reproduce the listener discrepancy independently of the `APP_PROCESS_NOT_RELEASED` audit refusal. No acceptance, financial authority, or operational startup follows. Next diagnose Windows TCP state reporting and netstat enumeration, retaining the unchanged three-reader unanimity requirement.

## 2026-11-08 Windows TCP state follow-up
Extended the disposable reader comparison with direct `SO_ACCEPTCONN`, raw port-scoped netstat lines/exit status, and `Get-NetTCPConnection` state. Actual ephemeral listener on port 59896, PID 29252: `SO_ACCEPTCONN=1`; CIM State is System.Byte 0 with matching owner; native IP Helper State 0 with matching owner; `Get-NetTCPConnection` returned matching address/port/owner but null State; `netstat -ano -p tcp` exited 0 yet had zero port-scoped lines. This is independent of the global process-cleanup audit. Socket readiness alone cannot replace three independent LISTENING observations. The Windows TCP enumeration discrepancy remains a genuine Gate 1 blocker; no listener validator or authorization was relaxed.

## 2026-11-08 connected disposable listener comparison
Added an optional connected-loopback lifecycle to the three-reader diagnostic. With a Python-owned listener on port 54426 (PID 31520), all three readers exposed the accepted ESTABLISHED connection with TCP state 5 and matching owner. At the same time CIM and native IP Helper continued to expose the listening endpoint as state 0, Get-NetTCPConnection represented that listener with null State, and netstat did not emit a LISTENING row. The distinct connected-row observation confirms the readers can enumerate established traffic but cannot supply the contract-required LISTENING state on this machine. No change to the original acceptance predicates, operational authority, or financial dispatch. The diagnostic closes both connection ends and listener on exit.

## 2026-11-08 netstat filter-control comparison
The disposable reader probe now collects both unfiltered `netstat -ano` and protocol-scoped `netstat -ano -p tcp` while the same socket remains open. On observed port 49553, both commands exited 0 and both omitted the listener, while CIM and IP Helper returned a matching endpoint with state 0, `Get-NetTCPConnection` returned null state, and `SO_ACCEPTCONN=1`. Therefore the missing netstat LISTENING row is not explained by the `-p tcp` filter. This is a negative diagnostic, not acceptance evidence; the original three-reader listener requirement remains unchanged.

## 2026-11-08 independent .NET listener control
Added `scripts/observation_runtime/disposable_dotnet_listener_probe.ps1` using a separate Windows .NET TcpListener implementation with a `finally` Stop and no Atlas host startup. Actual ephemeral port 51767, owner PID 28348: CIM returned matching owner and state 0, Get-NetTCPConnection matching owner and null state, netstat -ano omitted the listening endpoint. The same discrepancy occurs independently of Python's socket implementation, narrowing the issue to Windows TCP enumeration/state exposure on this machine. This is diagnostic only, not operational listener acceptance; the native IP Helper three-reader requirement is not waived.
