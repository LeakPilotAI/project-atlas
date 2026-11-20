# Installed-runtime clock validation — October 30, 2026

Base: `5687ce6893ca6e33dde1af68c712f8dc4e60a3da`. Scope: **QD-INSTALLED-RUNTIME-CLOCK-VALIDATION-V1**, bounded read-only candidate verification and normal-permission clock acquisition. **The genuine isolated installed clock path passed without Windows administrator privileges.** No Windows configuration change, UAC elevation, service action, resync, provider, financial writer, account activation, installation promotion or Genesis action occurred.

## Verified candidate and execution path

Candidate: `D:\Work\Project Atlas\logs\diagnostics\qd-native-install-2e13e1d5b0f44498\candidate`, the retained disposable installation from source `2b9ba32a683b62933f29d3b52777a21753e50631`. It is **not** a new operational release or the current promotion candidate.

The retained source selection and archive were checked against their published pins:

- 637-source inventory: `4ed3ac5fc286e560e8208ce812ed44d73d23da853fdfc88e34356d579f3e3dfd`.
- Source archive: `684e295e6004ef8c401b2b701977b8aad058e235176149b0ade518e176280dae`.
- Original dependency inventory: `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`, matching all 9,566 installed dependency rows.

Native read-only audits verified **10,203 files / 903 directories**, exact original volume/file identities, protected owner/SYSTEM ACLs, link counts, hashes, sizes and complete namespace. The AppContainer comparison including audit took **10.237 seconds**; the standard-user comparison took **6.510 seconds**. A separate post-execution full audit took **8.106 seconds** and again matched the original receipt. Each audit had a 180-second bound; each clock child had a 30-second bound. No candidate bytes, namespace, permissions or receipt were repaired, adopted or changed. Handles closed after verification.

The child used **candidate\python\python.exe**, `-I -B`, a candidate working directory, no inherited PYTHONPATH/PYTHONHOME and explicit candidate/backend module roots. Its executable, base prefix, actual process creation identity and retained process handle were checked. Clock, replay and personal clock-dependency module origins all resolved inside the verified candidate. It did not import workspace clock code or fixture authorities. The clock module's file SHA-256 is `a1d21ca5f55579ebbc690347fee3b902c26ea4c5d7e1f6ae292945a4f174571e`, identical to the current workspace version; no clock source or validator change was needed.

## Permission finding

| Actual execution context | Administrator token | AppContainer token | KEY_READ | KEY_QUERY_VALUE | Installed native probe |
|---|---|---|---|---|---|
| Tool's confined process | No | Yes | Error 5 | Error 5 | Registry refusal |
| Standard Windows user process | No | No | Success | Success | Genuine clock evidence acquired |

Both comparisons used the same candidate and installed clock module. No `RunAs`, UAC or administrator token was used. The second execution required tool permission to run outside the tool's AppContainer; **that permission is not Windows administrator elevation**. The script explicitly refused administrator tokens. Both owned candidate children exited with code 0; no unrelated process was terminated.

Exact registry requirement: read `NtpServer` and `Type` from `HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters` before and after the status query. The direct least-privilege probe demonstrated that **KEY_QUERY_VALUE (0x1)** suffices in the standard process; the existing PowerShell registry read also succeeds there. **KEY_READ (0x20019)** is read-only and also succeeded. Neither grants setting, subkey-creation, ACL-changing or ownership rights. AppContainer denied even the narrower request, so changing the reader to ask for fewer rights would not have resolved that confined-context failure.

This is an execution-context restriction, not evidence that the ordinary desktop user needs an administrator runtime or a registry ACL repair. No registry ACL was changed or broad permission granted. The correct validated path is the intended standard Windows desktop process. There is no automatic privilege escalation or attempt to change AppContainer policy. A native read refusal remains fail-closed when Atlas actually runs in a context lacking access.

## Genuine clock result

The installed `_WindowsProbe` read actual OS status, and the **unchanged** `uncertainty_ms` validator accepted **196 ms**. A separate real installed `LocalWindowsClock` construction, explicit runtime binding and live continuity sample also accepted **196 ms**. The capability was revoked in a `finally` block, then its owned child exited. No synthetic sample, caller-supplied accuracy declaration or offset-only replacement was used.

| Measurement | Actual value |
|---|---:|
| Source | `time.windows.com,0x9` |
| Service / configured type | Running / NTP |
| Leap / stratum / last sync error | 0 / 5 / 0 |
| Last successful sync, Central | 07:24:27 |
| First native measurement age | **53.9569218 seconds** |
| Live binding collection, Central | **07:25:21.7872031** |
| Live binding source age | **54.4241500 seconds** |
| Root dispersion | 29.0048 ms |
| Absolute phase offset | 2.5674 ms |
| Half root delay | 15.93 ms |
| Wall/QPC skew | 0.0012 ms |
| Drift over first source age | 26.9784609 ms |
| Drift over 240-second validity | 120 ms |
| Collection drift / fixed margin | 0.3647083 / 1 ms |
| First conservative sum / rounded bound | **195.8465692 / 196 ms** |

Atlas retained its **1,000-ms uncertainty limit, 120-second source-age limit, native provenance and continuity checks**. Its local-process capability authenticates local acquisition under the existing personal Windows/NTP model; it does not certify remote NTP cryptographically or eliminate same-user and oscillator-model assumptions. Windows Time was allowed to synchronize normally; this task did not start, reload, restart, reconfigure or force it.

The accepted capability is revoked, its process is gone, and its snapshot is historical evidence. It cannot be reused for a later session. The previous 964-ms acceptance and original aborted experiment's 1662/1656-ms refusals remain separate historical evidence, not rewritten results.

## Regression and preservation evidence

**102 distinct pytest cases passed, 0 failed, 0 skipped, 5.99 seconds.** Selection: Windows native-probe boundary, existing Windows clock validation, IEX clock admission, installed module identity and disposable installer refusal/namespace tests. **Nine new offline cases** cover exact bounded read-only command launch, signed-tool and before/after-source checks, module environment isolation, registry/status/change refusals, excessive output, timeout, process access denial and malformed output. They prove refusal does not retry, elevate, repair permissions or return invented evidence. All Windows interfaces are mocked in those nine tests; they are distinct from the two genuine installed comparisons above.

Ruff passed. Static PAPER policy audit: **642 runtime sources, zero issues, no startup authorization**. The previous 295-case V2 guard evidence is preserved and was not needlessly repeated; its guard code is unchanged. Accounting, shutdown, risk policy and all financial records are unchanged, so no new accounting engine test or financial publication was introduced for this clock-only milestone.

Private evidence remains under `logs/diagnostics`: `qd-installed-clock-normal-v1.json`, `qd-installed-clock-standard-user-v1.json`, `qd-installed-clock-postinventory-v1.json`, `qd-installed-clock-pins-v1.json` and `qd-installed-clock-regressions-v1.txt`. The exact executed diagnostic scripts remain retained. No native/process identity, SID, credential or financial payload is committed. Both clock children exited, post-audit handles closed, no listener opened and no cleanup of unrelated evidence or files occurred.

The canonical roadmap is updated through its archival updater, preserving the previous managed body verbatim, seven phases and 21 historical decisions. The recovery state retains both the previous V2 preflight and original unresolved experiment record. The unrelated modified research test and all untracked evidence are preserved. The active installation, selectors, protected financial accounts and journals were not changed.

## Remaining commissioning boundary

**This normal-process clock-access blocker is resolved for the verified candidate path. No Windows configuration or permission change is recommended.** No current clock capability persists after the test.

The next useful milestone is the reviewed **current operational release/resource acceptance**, subject to its explicit authorization: the existing isolated candidate is a disposable receipt and cannot be promoted as financial authority. Actual current research publication/provenance/native custody, entitled current instrument/calendar/halts and executable IEX evidence remain unaccepted. Real personal authority/session/writer/current-custody/resource bindings and the actual Control Center Stop/dashboard/restart acceptance remain necessary. Prior isolated Stop timings do not substitute for the operational composition.

This read-only directive authorizes none of promotion, provider activation, financial enrollment/inception or PAPER startup. Those actions still require their separately reviewed exact scope and all mandatory technical checks. At that point Atlas must obtain its **own fresh native clock capability in its verified standard-user installed process**; this report is not a reusable clock grant. The sole operator remains release authority under the personal PAPER policy; no external committee requirement is introduced.

**Installed normal-permission clock path: VERIFIED at the recorded cut. Candidate: UNCHANGED / NOT PROMOTED. Financial activation: NO. PAPER startup: NO. Production: NO-GO.**
