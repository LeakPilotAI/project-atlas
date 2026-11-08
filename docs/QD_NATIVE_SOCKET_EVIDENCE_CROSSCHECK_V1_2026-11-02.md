# Native socket evidence cross-check — State 0 localized; installed acceptance BLOCKED

Starting checkpoint **69f48737fa6bdf81bbd1c4bc41a6ee40027ad879**, branch `chatgpt/atlas-rebuild-v1`. This report uses the operator's November 2 Chicago date; captured UTC timestamps fall on November 3. No installed Atlas application was launched.

**One bounded disposable investigation completed. State 0 is present in the native IP Helper return bytes and CIM's raw property; it is not an Atlas decoder default or a CIM-only representation. The deeper reason Windows returned that value remains unresolved. The historical PID-0 LISTENING discrepancy also remains unresolved. Installed acceptance: BLOCKED.**

## Scope, ownership and containment

Exactly one standalone child created one IPv4 TCP listener at **127.0.0.1:61432**, using an OS-assigned ephemeral port. A single owned loopback client at **127.0.0.1:60507** connected to demonstrate a real accepted connection and observe graceful terminal state. No Atlas application/former diagnostic port was bound, and no external destination was contacted.

The retained child creation handle was checked against native PID, creation FILETIME and executable image before observations and shutdown. Repeated native image/creation observations matched the original claim throughout the active cuts. Executable SHA-256 and native stat identity were recorded privately. In the tables below, **A denotes that exact verified positive child PID**, not an invented account/process authority; its actual value, creation time and image identity are in private `owner.json`.

The investigation enforced a **90-second / 512-entry / 8-MiB** diagnostic ceiling with cleanup reserves; the child also had a 60-second natural lifetime. It used ordinary Windows-user permissions, no administrator token, no force-kill path and no Windows configuration action. Raw captures were confined to `D:\Work\Project Atlas\logs\diagnostics\qd-native-socket-crosscheck-v1-20261102`. Later source tests/documentation are separate from the native-session counter.

## Raw evidence before normalization

| Stable cut | Native IP Helper | CIM direct / explicit property | Raw scoped netstat output |
|---|---|---|---|
| Listening 1 | State DWORD **0**, owner A | **0 / 0**, `UInt8` / `System.Byte`, owner A | No row for this listener |
| Listening 2 | State DWORD **0**, owner A | **0 / 0**, same positive owner | No row for this listener |
| Connected | Listener **0 / A** plus established **5 / A** | Listener **0 / A** plus established **5 / A** | Established **5 / A** only |
| After exit 1 | TIME_WAIT **11 / 0** | TIME_WAIT **11 / 0** | TIME_WAIT **11 / 0** |
| After exit 2 | TIME_WAIT **11 / 0** | TIME_WAIT **11 / 0** | TIME_WAIT **11 / 0** |

All captured local endpoints matched **TCP / IPv4 / 127.0.0.1:61432**. Established/terminal remote endpoints matched the owned client. Both IP Helper address-family tables were queried; no IPv6 row shared the test port. Actual IPv6 listener behavior was not exercised; IPv6 decoding/matching was tested offline.

The scoped native IPv4 row's first four bytes were literally **`00 00 00 00`** while the listener was held open. The decoder did not produce zero by truncating or replacing a field. CIM exposed both `$row.State` and `CimInstanceProperties['State'].Value` as numeric zero, with the same correct owner and local endpoint. Netstat produced no scoped listener line before parsing; its established line for that exact local endpoint appeared once the owned connection existed. Its omission cannot prove the listener was closed.

IP Helper returned **122** for all ten expected buffer-size probes and **0** for all ten data fetches. CIM/netstat query processes exited zero with empty stderr. No enumeration exception or conversion failure occurred during the native run. Unsupported state validation is a separate failure from API-call success.

Unmodified complete scoped evidence is retained privately:

- `listening-1`, `listening-2`, `connected`, `after-exit-1`, `after-exit-2` files with `-ip-helper-raw.json`, `-cim-raw.json`, `-netstat-raw.bin` and `-crosscheck.json` suffixes.
- IP Helper records API codes/sizes, 24-/56-byte row layouts and scoped row hex. CIM records direct values, explicit property values, CIM/CLR types and collection timestamps. Netstat captures exact scoped bytes before its parser.
- `owner.json`, `owned-client.json`, `child-final-stdout.bin`, `child-final-stderr.bin`, `result.json` and `capture-source-hashes.json` contain private identity, ownership and cleanup details. Machine-specific owner/image identities are not committed to Git.

The first CIM sample's UTC timestamp is **2026-11-03T02:43:09.8454739Z** (November 2 in Chicago). UTC is recorded context, not financial clock-acceptance evidence. Ordering uses monotonic timestamps throughout:

| Cut | Start / finish milliseconds from first observation boundary | Reconciliation |
|---|---:|---|
| Listening 1 | 0.000 / 1,852.446 | Refused: native/CIM State 0; netstat absent |
| Listening 2 | 2,058.031 / 3,096.218 | Refused for the same reason |
| Connected | 3,123.016 / 4,133.145 | Refused: state-0 listener still present |
| Child exit observed | **4,147.608** | Normal exit, close acknowledgement |
| After exit 1 | 4,147.786 / 5,163.480 | Three usable views agree on terminal row only |
| After exit 2 | 5,423.433 / 6,464.252 | Same terminal-only agreement |

## Root-cause assessment

**State 0 origin established:** it is a genuine value in the native Windows API response, also exposed by CIM. It is not explained by Atlas's JSON parser, scalar conversion, or PowerShell's direct-property adapter: direct and explicit CIM values agree, and the native DWORD independently contains zero. Two held-listener cuts and a real accepted connection preceded shutdown; a shutdown transition does not explain those stable-cut observations. Why the Windows stack exposed zero is **not established**. No unsupported meaning, blanket mapping to LISTEN, or system-setting correction is inferred.

Microsoft's documented [IPv4 TCP-row contract](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcprow_owner_pid) defines LISTEN as 2 and TIME_WAIT as 11. The [CIM TCP class](https://learn.microsoft.com/en-us/windows/win32/fwp/wmi/nettcpipprov/msft-nettcpconnection) uses the same documented state range. The implementation follows the [GetExtendedTcpTable](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable) API and [OWNER_PID table layouts](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcp6row_owner_pid). State 0 remains unaccepted.

**PID 0 considered separately:** this disposable run demonstrated an exact owned connection becoming TIME_WAIT/owner 0 after acknowledged child exit. That is the observed terminal condition of this test; it does **not** explain the earlier installed endpoint **127.0.0.1:60840** reported as **LISTENING/owner 0**. That historical event lacks simultaneous IP Helper bytes and sufficient timing/endpoint detail in its first audit. The prior finding remains unresolved and unaccepted. PID 0 never becomes automatically harmless.

The two post-exit observations prove disappearance of this test's listener/active connection and agreement on terminal state, **not disappearance of every TCP row**: TIME_WAIT remained during the bounded window. No attempt was made to purge it, change Windows networking or kill another process.

## Source correction and explicit reconciliation policy

New `scripts/observation_runtime/socket_evidence.py` provides scoped SDK decoding, typed CIM-property comparison, strict netstat parsing and conservative three-view reconciliation. New `scripts/windows/Atlas-Socket-Raw-Crosscheck.ps1` captures raw, typed, port-confined CIM evidence without process/application/service mutation.

The test-harness `AcceptanceController.next_cycle` now requires this cross-check **in addition to** the existing accepted Stop, fresh CIM/process-roster assessment and retained native controller identity. Missing corroboration refuses by default. It grants no startup or financial authority and changes no installed support file.

Policy:

1. Require exactly CIM, IP_HELPER and NETSTAT; all complete, error-free, endpoint-bound and collected after the relevant monotonic boundary. Missing/stale/partial evidence refuses.
2. Compare canonical address family, local endpoint, state and owner. Non-listener rows also compare remote endpoint. Listener remote fields are preserved raw but have no TCP identity meaning under the documented API contract.
3. Refuse unknown states, owner absence, duplicate rows, API/parser errors and cross-source disagreement. Do not choose whichever reader passes. A consistent LISTEN row still refuses cleanup, including PID 0 or an unrelated owner.
4. Only unanimous usable absence or terminal CLOSED/TIME_WAIT evidence can clear the **socket portion**. Exact process/creation identity, accepted Stop, writer/process cleanup and all other gates remain separately required. A later observation cannot retroactively accept a prior failure.

The original eight-second Stop, 45-second browser deadline, current financial gates, risk rules and runtime authority are unchanged. The earlier review-only worker patch remains historical and does not supply the newly required bundle; it cannot be reused as an installed-launch authorization. Final source contains additional invalid-input/type checks and formatting applied after the native capture. All retained native cuts replay identically under that source; **no second native run or final-source installed acceptance is claimed**. A byte-exact pre-edit decoder snapshot was not retained, so final-source hashes must not be represented as native deployment acceptance pins.

## Tests and cleanup

- **318 passed / 0 failed / 0 skipped, 16.18 seconds**, relevant offline/disposable suite. This adds **70 cases** to the preceding 248-case evidence. Coverage includes raw IPv4/IPv6 decoding, zero states from either API, PID 0 versus missing owner, transitions/disappearance, process-exit-with-residual-socket cases, stale/error/conflicting observations, source substitution, unrelated listeners and second-Open refusal.
- Native API error/buffer-growth mocks retain error codes and fail closed. Actual PowerShell typed capture and native IPv4 ownership were exercised only by the single diagnostic above. Prior mocked PowerShell/Stop/handle tests and support/selector/launcher regressions remain passing.
- Ruff lint/format checks and Python/PowerShell parsing passed; no lint cache was enabled.
- Five retained native cuts replay exactly at their original observation boundaries: three active refusals and two terminal-only agreements. An initial direct Python-versus-JSON equality check differed only because tuples deserialize as lists; exact canonical JSON comparison verified every persisted value. This is offline replay, not current clock/startup evidence.
- The previous **one failed native State-0 witness** and all historical browser/cleanup failures remain unchanged. This diagnostic's successful collection is not a passing expected-LISTEN witness or installed acceptance.

The bounded native run completed in **6.574553 seconds**. At result publication: **45 entries / 1,809,931 logical bytes / 1,994,251 accounted bytes**, below its declared limits. The child acknowledged close and exited **0** with empty stderr; the owned client received EOF and closed. The child creation handle and all **ten query-helper handles** closed after exit collection. No timeout, forced termination, remaining owned listener or unrelated-process action occurred.

## Final state and next boundary

**Installed acceptance remains BLOCKED.** The unsupported native state and historical PID-0 LISTENING event must not be normalized, hidden or treated as resolved. A further narrowly reviewed read-only Windows TCP-state/provider investigation may identify the system-level explanation; current evidence justifies no networking or clock configuration change. Any installed acceptance still requires a fresh explicit grant and every original preflight.

No installed Atlas launch, release selection, rollback, support reinstallation, journal reset, financial/provider/PAPER/live activation, automatic startup, Windows setting change or Genesis modification occurred. The recovered **UNSELECTED revision-4** baseline remains preserved; no operational selector readback or publication was performed here. All B1/C1/D1/E1 requirements, 21 decisions, seven phases, protected accounts, frozen payload, original UI and unrelated work remain unchanged. Canonical roadmap/recovery evidence is archived and updated. **Stop after this investigation. PAPER NO. Production NO-GO.**
