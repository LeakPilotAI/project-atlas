# V6 active-listener and trusted-browser evidence recovery

**BLOCKED — stable active-listener observations still fail the unchanged three-reader contract, and the current environment has no registered trusted Chrome tab/navigation provider.**

Starting commit `2cc0c8086838875281274d3956d070c3ac82b6eb`, branch `chatgpt/atlas-rebuild-v1`. This is a disposable evidence investigation. No integrated two-cycle rehearsal, installed application/interpreter, operational selection, financial writer, provider, PAPER operation or consumed operational grant was executed. Historical failures remain unchanged.

## Stable socket reproduction

New source fixture `tests/v6_stable_listener_fixture.py` creates one IPv4 loopback HTTP listener and retains it continuously until an explicit Stop/EOF. It records bind, listen, READY, socket witnesses, HTTP traffic and teardown using monotonic nanoseconds plus diagnostic UTC. Native `SO_ACCEPTCONN` is read before and after each of three complete observation cuts. The PID, native creation identity, original process handle, executable/file hash, ancestry, exact command and complete Job roster are independently verified by the existing V6 owner and V5 ownership implementation.

The explicit `-StableListenerProbeOnly` wrapper mode routes exclusively into the HTTP-diagnostic branch. It cannot enter `BrowserWindow`, browser ACK, `run_cycle` or second Open. All new fixture/helper sources are included in its source-hash manifest. Bounds remain **600 seconds / 8,192 entries / 64 MiB**. No production socket observer, state decoder or three-reader policy was changed.

Genuine run: `logs/diagnostics/qd-v6-integrated-rehearsal-stable-listener-20261103`.

| Identity | Observed value |
| --- | --- |
| Listener endpoint | **IPv4 127.0.0.1:64357**, TCP |
| Controller PID / native creation | **13908 / 134382403956010782** |
| Worker / supervisor | **29592 / 21100**; exact console and full native roster retained in `job-attribution.json` |
| Retained listener socket value | **544**, unchanged across all live witnesses |
| Process image | Direct source Python, `c:\users\renal\appdata\local\programs\python\python312\python.exe` |
| Readable native socket status | `SO_ACCEPTCONN=0` after bind; **1 after listen and at every before/after witness** |

Exact monotonic event times (nanoseconds):

| Event | Timestamp |
| --- | --- |
| Bind begin / end | 9490768996200 / 9490782222700 |
| Listen begin / end | 9490782487900 / 9490782715200 |
| First before-witness / final after-witness | 9495636037000 / 9501959413500 |
| Direct HTTP request interval | 9501971296700–9501978565300 |
| Shutdown begin / socket closed | 9501980122300 / 9501990797300 |

The listener lifetime from successful listen to close was **11.2080821 seconds**. Repeated reader cuts were bracketed by continuous-listen witnesses spanning **6.3233765 seconds**. The controller source performs no close, rebind or replacement between those witnesses; socket/PID/creation/endpoint remain identical. Raw native file/process/socket values and event UTC are retained privately, not reconstructed from a later PID.

## Reader results and cause classification

| Sample | CIM | Native IP Helper | netstat | Original gate |
| --- | --- | --- | --- | --- |
| 1 | State **0**, owner 13908 | Raw state DWORD **0**, owner 13908 | No scoped row; exit **0** | REFUSED |
| 2 | State **0**, owner 13908 | Raw state DWORD **0**, owner 13908 | No scoped row; exit **0** | REFUSED |
| 3 | State **0**, owner 13908 | Raw state DWORD **0**, owner 13908 | No scoped row; exit **0** | REFUSED |

All queries completed without enumeration errors. Every original reader's start/end timestamp falls inside the corresponding before/after retained-socket witness interval. Raw CIM property types, raw IP Helper scoped row hex, API return codes, command lines, netstat stdout/stderr and exact exit status are retained in `stable-listening-{1,2,3}-*` and `action-identities.jsonl`. Empty netstat output was not promoted to affirmative listener absence.

The raw state bytes are zero before Atlas decoding. Endpoint, IPv4 family, port and native owning PID agree with the retained controller. This is not a byte-order reinterpretation of state 2, and no parser defect was demonstrated. The observed case is **stable unsupported native reporting**, not a teardown transition, an IPv4/IPv6 mismatch or an observation spanning listener replacement. These findings do not identify the exact Windows component, servicing update, socket provider or driver responsible.

Microsoft's documented owner-PID row contract identifies LISTENING as **2**; zero is outside its documented state table. [Microsoft TCP row contract](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcprow_owner_pid). Native `SO_ACCEPTCONN` is a separate supported query of a socket's listening mode; its result does not rewrite a TCP-table row or replace a reader. [Microsoft socket option reference](https://learn.microsoft.com/en-us/windows/win32/api/winsock/nf-winsock-getsockopt).

Read-only local version evidence: **Windows 11 Pro 26H2, 10.0.26300.9818**, x64. Networking file versions were saved in `windows-version.json`. A community report on Microsoft Q&A describes the same State-0/netstat symptom on that build. This is corroboration of a reported platform problem, **not Microsoft confirmation of our root cause or a validated fix**. [Matching report](https://learn.microsoft.com/en-us/answers/questions/6057787/getextendedtcptable-returns-dwstate-0-for-listenin).

Different networking-file version numbers alone do not prove corruption. No Windows patch was installed/removed, driver disabled, network/security setting changed, service restarted, firewall modified or system repair executed. The community thread's proposed repairs were not treated as instructions or authorization. A supported Windows-side correction must be separately reviewed/authorized and must restore genuine valid state evidence; no exact corrective update has been verified here.

The independent direct HTTP request returned **200**, **113 bytes**, in **7.2686 ms**; actual TCP peer EOF and client-handle closure passed. This proves HTTP service during that interval, not accepted table-state evidence, browser navigation or financial authority. All three active cuts remain refused; no deadline extension, reader removal, State-0 conversion or failed-cut resampling into success occurred.

## Trusted browser capability findings

Read-only capability discovery was performed before any new navigation or policy refusal. It used the documented Computer Use inventory, not another interface to complete a previously denied action. **No browser input, navigation, acknowledgement or safety retry occurred.** The current registered browser providers are:

| Provider | Type | Required Windows Chrome evidence |
| --- | --- | --- |
| ChatGPT in-app browser, ID 2 | `iab` | Separate target; not substituted for required Windows Chrome |
| Codex MCP Apps, ID 1 | `mcpapps` | App surface; not a Chrome tab/navigation bridge |

There is **no registered Chrome extension/CDP browser provider** in the returned inventory. Chrome's native application window exists, but native-window presence is distinct from a trusted browser-tab/navigation channel. The native skill exposes window identity, accessibility and screenshots, while the previously observed URL policy refusal is internal to that tool. It exposes no documented override or independent trusted URL attestation that Atlas can fabricate. Visible/typed address-bar content and screenshots were not substituted for the required verification.

The supported inventory methods are `cua.getState` and `cua.listBrowsers`; returned browser-provider documentation must be obtained before using any provider's navigation methods. No unlisted Chrome provider ID, debug port, extension, security setting or hidden browser interface was guessed or created. Browser discovery is not acknowledgement evidence.

**Exact environment prerequisite:** provide an approved Windows Chrome browser connection exposing policy-checked tab URL/navigation observations, or restore the native Computer Use tool's supported policy-compliant navigation verification. A stable ordinary window alone does not establish that capability. An in-app browser cannot silently replace the pinned Windows Chrome acceptance target. Any connection/install/access change is outside this diagnostic execution; no security-sensitive browser permissions were broadened. Once the capability exists, a separately directed browser-only prerequisite must establish real window/tab identity, localhost navigation, trusted post-navigation URL, rendered fixture, genuine ACK within 45 seconds and test-tab closure. Do not repeatedly retry a policy refusal or automatically run the integrated rehearsal.

## Strict cleanup, tests and preservation

After normal controller Stop/EOF, controller/console native exit verification and retirement of owned query handles, fresh **CIM → netstat → IP Helper** cuts followed by strict rich process verification last passed on **64357, 60103, 60105 and 62833**. The original unanimous validator accepted only valid terminal/absent states; no active State 0 was allowed into cleanup. Original helper claims came from verified retained identities. The worker independently verified its worker-only Job, then the outer owner verified **zero Job members**, worker exit **0**, native log drain and closed process/thread/Job/image/log handles. No forced termination occurred.

Native query-only checks subsequently found no owned survivors among **13 recorded old/new process identities**. No unrelated browser/process was terminated, adopted or reparented. All query handles closed. **Fresh strict cleanup: PASS. Active-listener agreement: FAIL.** The new cleanup does not retroactively pass historical failed observations or the consumed V5 acceptance.

Actual native diagnostic completed in **43.4618215 seconds**. Final root accounting including result: **249 entries / 288,003 logical bytes / 1,307,907 accounted bytes**. Source/event/raw hashes are retained in `logs/diagnostics/qd-v6-evidence-gate-recovery-20261103/native-proof.json`. Failure evidence and required diagnostic artifacts remain; no files were deleted and zero disk space was reclaimed.

Source additions: `tests/v6_stable_listener_fixture.py`, `tests/v6_stable_listener_evidence.py`, `tests/test_v6_stable_listener_evidence.py`; explicit fixture-mode/source-manifest changes in `tests/run_v6_integrated_rehearsal.ps1` and `tests/v6_integrated_rehearsal_worker.py`. No operational ownership, TCP state mapping or acceptance policy source changed.

- Final full relevant suite: **590 passed, 0 failed, 0 skipped in 37.98 seconds**, including all previous **575** cases and **15 new** stable-lifetime/refusal cases.
- Final focused selection: **24 passed, 0 failed, 0 skipped in 3.04 seconds**. Earlier focused 21/2.50 s and broader 587/39.09 s results are preserved, superseded by the final selections. Counts overlap.
- Added cases cover unchanged socket/native identity, PID reuse, handle/port/family/address replacement, non-listening/bool status, early/late or missing readers, and actual original `reconcile` refusing State 0/reader omission despite separate socket-level listen evidence.
- No-cache lint/format and PowerShell parsing passed. All **155 V5 source pins**, original V5 FAIL/consumed raw hashes and the previous native diagnostic raw hashes were rechecked unchanged. The unrelated research-test SHA-256 remains `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb`.

## Decision and exact next prerequisite

**BLOCKED — valid active three-reader LISTENING evidence and a supported trusted Windows Chrome localhost-navigation channel are both missing.**

These are environment/evidence requirements, not new accounting features or administrative reviewer assignments. Current authorized source engineering and diagnostic validation are complete. Do not reinterpret the confirmed socket's State-0 rows, substitute another browser target, manufacture an ACK or relax a gate. Provide a supported Windows TCP reporting correction and the approved browser capability, then validate them with bounded prerequisite tests before requesting any integrated rehearsal. Any actual system repair/update or browser-access enrollment needs its own explicit scope; none was performed here.

Canonical roadmap and recovery state are archived/updated. Validated diagnostic source/tests/documentation may be committed and non-force pushed independently of the blocked operational result; final SHA is reported after remote verification. Historical **UNSELECTED revision 6** is retained as last independently verified selector evidence, not newly read or changed here. No fresh financial clock capability was collected. B1/C1/D1/E1, all 21 decisions, seven phases, USD/USDC separation, protected financial records and Genesis isolation remain unchanged. **No integrated rehearsal or installed Atlas launch. PAPER: NO. Production: NO-GO. STOP after this evidence-gate checkpoint.**

## Interrupted-checkpoint recovery and evidence provenance

Milestone **QD-V6-EVIDENCE-GATE-CHECKPOINT-RECOVERY** resumed from the actual working tree. Before checkpointing, both local HEAD and a fresh remote branch query returned **`2cc0c8086838875281274d3956d070c3ac82b6eb`**; the preceding evidence-gate increment had **not** been committed or pushed. Its five source files, report, archived roadmap and recovery edits were preserved. No new native listener, process-ownership experiment, installed application or browser navigation was run during recovery.

| Evidence | What was independently checked during recovery | What was not repeated |
| --- | --- | --- |
| Source and artifacts | All five pending source-file hashes match the retained tested manifest; **247** raw diagnostic-file hashes match the retained proof | Native execution of those files |
| Previous full regression | JUnit contains **590 unique tests**, zero failures/errors/skips; all previous **575 test identities** are included | The 590-test suite was not rerun; its original console duration was 37.98 s, JUnit suite duration 37.681 s |
| Current focused validation | **24 passed, 0 failed, 0 skipped in 2.27 s**; current no-cache lint/format and PowerShell parsing pass | These 24 overlap the 590; totals must not be added |
| Three live observations | Raw files and event journal agree on the unchanged socket/PID/endpoint and `SO_ACCEPTCONN=1`; fresh offline evaluation of the original validator refuses **3/3** | No fresh kernel/socket measurement |
| Previous strict cleanup | Hash-verified logs record passed three-reader/process cuts, Job zero, handle closure and 13 no-survivor queries | No new cleanup or survivor query; this is a **recovered PASS**, not a new current-machine clearance |
| Browser providers | A new read-only `cua.listBrowsers` call again returned only in-app browser ID 2 and MCP Apps ID 1 | No Chrome tab claim, URL navigation, ACK or policy retry |
| Historical protection | All **155 V5 source pins**, V5 FAIL/consumed raw hashes and unrelated research-test hash were checked unchanged | No protected account, financial journal, installation selector or Genesis inspection |

Private audit: `logs/diagnostics/qd-v6-checkpoint-recovery-20261103/offline-artifact-audit.json`. This distinguishes current artifact verification from recovered process/socket observations. A retained manifest provides integrity comparison, not a new independent runtime witness or release acceptance. No confirmed Windows operating-system defect is claimed. The observed unsupported reporting is established in the saved run; its underlying OS/component/provider cause remains unproven.

## Supported observation candidates and unapproved alternatives

There are documented Windows APIs worth separately scoped evaluation, but **none has been demonstrated to satisfy the unchanged complete three-reader contract on this computer**:

- `GetExtendedTcpTable` supports a listener-specific `TCP_TABLE_OWNER_PID_LISTENER` table for IPv4/IPv6. This is a documented additional observation candidate, not evidence that it produces valid rows here. The existing run used the all-endpoints owner-PID table. [Microsoft table classes](https://learn.microsoft.com/en-us/windows/win32/api/iprtrmib/ne-iprtrmib-tcp_table_class), [API contract](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable).
- `GetTcpTable2` is another documented IPv4 TCP table API. Its existence does not establish implementation independence, valid results on this host, or agreement with CIM and netstat. No call was executed in this recovery. [Microsoft GetTcpTable2](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-gettcptable2).
- `SO_ACCEPTCONN` already provides useful socket-level evidence, but it does not independently enumerate competing endpoint owners or supply missing results from the other readers. HTTP response success likewise cannot replace native listener-ownership agreement.

A positive result from a supplementary API would **not** automatically clear CIM State 0 or netstat omission. Under the current contract, all three required readers must still provide usable, fresh, consistent endpoint/state/owner evidence. No state conversion, reader replacement or policy change has been applied.

**Proposed change only — NOT APPROVED:** if the original observers cannot provide qualifying evidence, an alternative active-listener admission contract could be designed for the sole operator's separate review. It would need independently verifiable retained socket/process provenance, exact endpoint and competing-binding coverage, PID-reuse protection, freshness, failure/refusal rules and equivalent adversarial disposable tests. Keep the existing three-reader cleanup contract, process/Job/handle checks and deadlines. `SO_ACCEPTCONN=1` plus HTTP 200 alone is insufficient. No equivalent alternative design has been established, implemented or authorized here; changing active-admission requirements cannot be presented as a routine observer repair.

A Windows repair/update is therefore **not asserted to be the only path** or a verified correction. The next choice is separately scoped evidence gathering with documented supplementary APIs, or separately reviewed design of an equivalent evidence contract—not an assumed OS defect, patch rollback or automatic safety relaxation.

The trusted-browser prerequisite remains exact: an approved Windows Chrome connection with policy-checked current-tab URL and navigation observations, or a repaired supported native Computer Use verification path, followed by a genuine browser-only acceptance test. Provider inventory is not navigation proof, and no different browser target or typed/screenshot URL may silently substitute. Any access enrollment or contract change requires its own explicit authorization; this recovery grants none.

**Final recovery status: BLOCKED — V6 integrated rehearsal.** The validated source-only increment and truthful evidence checkpoint may now be committed/pushed. The resulting local and remote SHA must be explicitly compared; the final response records the verified SHA. PAPER: NO. Production: NO-GO.
