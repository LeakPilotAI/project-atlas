# Windows Time quality diagnosis — October 30, 2026

Base: 946a0de1dfb19654895c4da3ee6696c9b6cf3ba8. Branch: chatgpt/atlas-rebuild-v1. Scope: QD-W32TIME-QUALITY-DIAGNOSIS-V1, read-only.

**Clock quality recovered naturally before this observation: all nine genuine native measurements passed at 196–226 ms. No Windows setting or service action was performed. No installation copy was started.** Every temporary capability was revoked; this is not permanent clock clearance or operational/PAPER authorization.

## Actual bounded observation

The unchanged LocalWindowsClock collected actual Windows evidence with its native probe and 240-second validity model, performed the existing operational runtime-binding check, then revoked each capability. Revocation was explicitly confirmed. No synthetic observation, caller-supplied UTC declaration or threshold change was used.

Observation: **161.562 seconds**, within the 180-second limit. Entire diagnostic including before/after configuration snapshots: **164.891 seconds**. Standard Windows process, **not administrator and not AppContainer**. All queries/processes returned; no listener, financial service or long-running observer remains.

| Elapsed start, seconds | Atlas uncertainty, ms | Native source age, seconds | Root dispersion, ms | Root delay, ms | Phase offset, ms |
|---:|---:|---:|---:|---:|---:|
| 0 | 206 | 26.2226876 | 39.5763 | 32.4946 | 14.9529 |
| 20 | 216 | 45.6098120 | 39.5763 | 32.4946 | 14.9529 |
| 40 | 226 | 65.9862311 | 39.5763 | 32.4946 | 14.9529 |
| 60 | 196 | 6.1858822 | 39.7267 | 31.9063 | 15.3609 |
| 80 | 206 | 25.7887398 | 39.7267 | 31.9063 | 15.3609 |
| 100 | 216 | 46.2173980 | 39.7267 | 31.9063 | 15.3609 |
| 120 | 201 | 17.9506431 | 38.6427 | 31.9063 | 15.1616 |
| 140 | 211 | 37.5370421 | 38.6427 | 31.9063 | 15.1616 |
| 160 | 221 | 57.9497566 | 38.6427 | 31.9063 | 15.1616 |

All nine: **ACCEPTED**, Leap 0, local stratum 5, last sync error 0, NTP source time.windows.com,0x9, State Machine 2 (Sync). All ages were below 120 seconds; all bounds were below 1,000 ms. The series was recorded in full, not reduced to its minimum. It was not monotonically decreasing; expected source-age contributions grew between normal successful synchronizations.

Final observed last successful sync: 10/30/2026 9:34:00 PM, as displayed by Windows. Final uncertainty: **221 ms**, age **57.9497566 seconds**, root dispersion **38.6427 ms**, root delay **31.9063 ms**. All accepted capabilities were revoked immediately, and the diagnostic process exited. A later runtime must acquire new evidence.

## Configuration, peers and permissions

Service remained **Running / Manual**. Configured type/source remained **NTP / time.windows.com,0x9**. Selected static values and policy observations matched before/after; LastKnownGoodTime was correctly treated as advancing runtime state rather than an unauthorized configuration mutation.

| Selected value | Historical 964-ms inspection | Current readback |
|---|---:|---:|
| MinPollInterval | 6 | 6 |
| MaxPollInterval | 15 | 15 |
| SpecialPollInterval | 64 | 64 |
| UpdateInterval | 360000 | 360000 |
| PhaseCorrectRate | 1 | 1 |
| FrequencyCorrectRate | 4 | 4 |
| LocalClockDispersion | 10 | 10 |

NtpClient remained enabled/input provider 1; NtpServer remained disabled/input provider 0. The three inspected Windows Time policy override keys were absent. No new account, registry ACL, source, peer, poll interval, time provider, firewall or startup change occurred.

One Active peer: client mode 3, peer stratum 4, Reachability 255, ValidDataCounter 8, Resolve Attempts 0, LastSyncError 0, NoAuth. The configured source and reference ID matched the historical evidence. Remote cryptographic NTP authentication or independent physical UTC certification is not claimed under the personal local clock model.

Status and peer reports displayed poll exponent **8 (256 seconds)**. Actual successful-sync timestamps advanced from 21:31:52 to 21:33:12 to 21:34:00. These are separately retained facts; the displayed exponent is not asserted to prove an exact packet schedule or override the configured SpecialPollInterval.

Direct normal-permission w32tm configuration and source queries returned **Access denied, 0x80070005**, both before and after. They were not silently elevated or called successful. Native status acquisition, registry reads and peer queries succeeded. Current registry values plus recent Windows Operational event 263 corroborate the relevant effective values and their Local origin; this is not a claim that the live configuration RPC succeeded. No administrator inspection is needed to demonstrate the current normal-user clock acceptance.

## Historical comparison

| Evidence | Context | Uncertainty, ms | Root dispersion, ms | Root delay, ms | Source age, seconds |
|---|---|---:|---:|---:|---:|
| Historical 196-ms acquisition | Genuine installed candidate, standard user | 196 | 29.0048 | 31.8600 | 53.9569218 |
| Historical 964-ms acquisition | D Python within authorized elevated read-only inspection | 964 | 794.1868 | 32.4357 | 25.0689543 |
| Prior 7,933-ms refusal | Standard-user source binding after service start | 7933 | 7771.7519* | 32.5604* | 41.6574332* |
| Current nine measurements | Standard-user D Python, native source binding | 196–226 | 38.6427–39.7267 | 31.9063–32.4946 | 6.1858822–65.9862311 |

*The refusal row's dispersion/delay/age belong to its preceding diagnostic, not the separate validator acquisition. Its exact validation age was not retained; the validator had passed freshness checks before refusing uncertainty. Historical records are not rewritten.*

All use time.windows.com,0x9 and the same uncertainty envelope: root dispersion + half root delay + absolute phase offset + measured wall/QPC skew + fixed margin + 500-ppm aging over source age, collection and 240-second validity. Current clock source SHA-256 remains **a1d21ca5f55579ebbc690347fee3b902c26ea4c5d7e1f6ae292945a4f174571e**, matching the verified installed clock version. Read-only Git comparison also confirmed canonical source equality with the 964-ms preflight's base commit 13cc83a2c9f9f674a5fab97fa7b362060a0fc9d6, including unchanged parser, uncertainty function, native probe and binding class. No unit, duplication or validator defect was demonstrated.

The dominant change is dispersion: about **7,772 ms then versus 39 ms now**. Delay stayed near 32 ms; current phase offset is about 15 ms, larger than the preceding refusal diagnostic's 1.3 ms. Source age remained comfortably within its limit. Therefore a large offset, collection timing or network round-trip delay does not explain the earlier multi-second bound. The historical 964-ms and current configuration values above match exactly; access context affected query permission, not a relaxation of the quality formula. The 196-ms clock capture did not include a complete configuration export, so equality of every setting at that earlier instant is not claimed.

## Cause: confirmed factor and bounded inference

**Confirmed immediate factor:** Windows' reported root dispersion dominated the 7,933-ms refusal. A roughly 7.77-second dispersion already exceeds Atlas's entire one-second allowance. It had recovered before the first current measurement, without a correction in this diagnostic. This is natural recovery relative to the prior checkpoint, not a claim that the drop occurred inside this 161.562-second series.

Bounded recent logs were read without enabling logging: **13 System Time-Service records** and **30 Operational records**. Relevant evidence:

- Events 37 and 35 recorded valid NtpClient data and synchronization during the previous service-start period.
- Operational event 261 recorded Windows' own roughly 1.024-second adjustment during initial reacquisition, not a manual change by Atlas.
- Event 266 recorded reason 3, internal W32Time state change; it is not the reason-0 explicit administrator resync category.
- At **21:25:28 America/Chicago on October 30**, Windows' own periodic event 260 already reported dispersion **0.0327889 seconds**, offset 0.0083207 seconds, fresh successful synchronization and the same source/configuration. That event predates the current diagnostic.
- Recent configuration events 263 report the same relevant Local values. Their update wording is not proof the values changed. Current before/after values remained identical.
- Event 158 says VMICTimeProvider stopped because the environment is unsupported, explicitly describing this as expected outside Hyper-V guests. Selected-source evidence remains NTP; there is no demonstrated reason to disable that provider.

**Most likely mechanism: transient post-start synchronization/clock-filter settling while Windows accumulated and selected usable samples.** This is an inference from the restart/reacquisition sequence, subsequent normal successful samples and recovery with the same settings. Microsoft describes sample filtering/selection and clock-rate convergence, but Windows is not an exact NTP reference implementation. The available observations do **not** separate the original upstream packet's dispersion from Windows' internal filtering/uncertainty. Exact attribution of that split, a specific filter-slot formula or permanent accuracy is not established. [Microsoft: Windows Time service operation](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/how-the-windows-time-service-works)

No current evidence supports a required peer/firewall change, persistent network failure, incorrect Atlas arithmetic or permission escalation. LocalClockDispersion 10 was present during passing and failing evidence and is not the measured root-dispersion floor for this selected NTP source. Reducing it merely to force a smaller declaration is unjustified; Microsoft describes its fallback role when configured sources cannot supply time. [Microsoft: tools and settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)

## Decision and next action

**No Windows configuration correction is justified now.** The restored/current configuration has produced nine genuine qualifying observations. Leave source, startup, poll/correction settings and providers unchanged. No restart, stop, forced synchronization, manual time adjustment, administrator elevation or system change occurred in this execution.

This short window does not prove long-term behavior across sleep, network loss or later service restarts. Keep fresh acquisition, continuity, age and uncertainty refusal active; never reuse these revoked measurements as runtime authority.

The next useful action is to **resume the previously authorized, unused V2 unselected code-copy task in a separate execution**, obtaining a new runtime-bound clock and revalidating all original source/resource/selected-release/native conditions. This diagnostic explicitly did not permit automatic copy, so no installation was attempted despite passing samples. No new V2 approval, paid time source, reviewer chain or tuning experiment is required by these observations. Selection/promotion, financial custody/inception, current research/executable IEX, actual financial Stop/dashboard/restart acceptance and PAPER remain gated.

No runtime code changed; completed broad regression suites were not repeated. These are **nine actual native clock acceptances**, not nine synthetic unit tests or a new financial acceptance. Private evidence is under logs/diagnostics/qd-w32time-quality-diagnosis-v1-20261030: before/after snapshots, exact sample records, execution context and result. Historical 196/964/7933 evidence, original experiment/native failures, cache variance, metadata anomaly and unrelated work remain preserved.

**Read-only diagnosis: COMPLETE. Current observed clock acquisition: PASSED, capabilities REVOKED. Installation copy: NO. PAPER startup: NO. Production: NO-GO.**
