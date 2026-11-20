# Windows Time start and clock refusal — October 30, 2026

Base: 51888e1e91ef6b45738596cd5f276bbb97257526. Milestone: P-QD-W32TIME-SERVICE-START-V1.

**W32Time started and reports synchronization, but Atlas refused the clock at 7,933 ms uncertainty. The 1,000 ms threshold is unchanged. STOP before code copy.** The authorized V2 one-copy grant remains unused. No operational release, intent journal, installation receipt/ACK, financial service, account, provider or PAPER session was created/activated. No selection/promotion or Genesis action occurred.

## Service action and permissions

Read-only preflight verified W32Time Stopped, Manual startup, configured NTP type and source time.windows.com,0x9. A normal-permission Start-Service attempt was refused by Windows without changing the service/configuration.

Under the operator's explicit instruction to use the normal Windows elevation prompt if required, exactly one elevated service command was requested through Start-Process -Verb RunAs: **Microsoft-signed system-directory sc.exe start W32Time**, hidden, no extra arguments. No credential was supplied or prompt automatically clicked. The owned tool exited with code 0 and its process object was disposed.

The immediate post-command query saw **StartPending**. The original private record classified this as W32TIME_START_NOT_CONFIRMED/REFUSED_STOP; it is preserved verbatim as an early observation, not silently edited into success. StartPending was not treated as a reason to start again. A follow-up read confirmed **Running**; the final read confirmed Running/Manual/NTP/time.windows.com,0x9. There was only one service-start command after the normal-permission refusal, not a retry loop.

No startup type, registry configuration, NTP peer/source, firewall, time provider or system-wide setting changed. No explicit resync, service restart/reload or manual clock adjustment occurred. Normal synchronization by the approved running service was observed. The service was left Running with Manual startup; no unapproved stop action was performed.

## Clock evidence and mandatory refusal

The existing LocalWindowsClock and validators were used unchanged. The first acquisition correctly refused CLOCK_UNSYNCHRONIZED. Its accompanying diagnostic showed Leap 3, Stratum 0 and Last Sync Error 1; no capability was issued. A further short normal-observation script had a 50-second ceiling within the approved observation allowance; it made no synchronization/configuration request and stopped after 3.296 seconds on the first numerical uncertainty refusal.

| Final synchronization diagnostic | Observation |
|---|---|
| Service | Running |
| Configured type/source | NTP / time.windows.com,0x9 |
| Leap / stratum / last sync error | 0 / 5 / 0 |
| Reported last successful sync | 10/30/2026 9:16:56 PM, as displayed by Windows |
| Preceding diagnostic age | 41.6574332 seconds |
| Preceding diagnostic root dispersion | 7.7717519 seconds |
| Preceding diagnostic root delay | 0.0325604 seconds |
| Preceding diagnostic phase offset | 0.0013256 seconds |
| Atlas fresh acquisition | **CLOCK_UNCERTAINTY_EXCEEDED:7933ms** |
| Maximum uncertainty / age | **1,000 ms / 120 seconds**, unchanged |
| Accepted clock capability | None |

The 41.6574332-second age belongs to the immediately preceding diagnostic, not the validator's separate acquisition. The validator progressed through its freshness checks and then refused the numerical uncertainty bound; no stale observation or historical accepted anchor was substituted. The exact separate validator age was not retained, so it is not invented here.

Windows reports successful synchronization; that status alone does not establish Atlas acceptance or independent UTC accuracy. The small phase offset is not the uncertainty bound. Atlas includes root dispersion, half root delay, absolute offset, measured local wall/QPC skew, a margin and its conservative aging model. The observed 7.7717519-second root dispersion alone exceeds one second. The genuine validator returned 7,933 ms, so no threshold was relaxed and no offset-only substitute was used.

There was no further acceptance retry after the numerical refusal. The observation scripts took 3.578 and 3.296 seconds respectively; the normal-observation script ended early and did not exhaust its ceiling. No long-running monitor remains.

Private evidence, retained outside Git:

- logs/diagnostics/qd-w32time-service-start-v1-20261030.json — normal refusal/elevated command result and initial StartPending check.
- logs/diagnostics/qd-w32time-clock-observation-v1-20261030.json — original unsynchronized acquisition/diagnostic.
- logs/diagnostics/qd-w32time-bounded-normal-observation-v1-20261030.json — synchronized diagnostic and genuine 7,933-ms refusal.

## V2 copy status and preservation

The operator-confirmed V2 canonical pin remains **09e899b09916300aec70b69d743d4c7e2383f43ecb58cea4a032f4070988917e**. All three current adapter source pins remain unchanged/matching. The intended destination remains:

D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118

The destination and matching .pending.jsonl/final receipt remain absent. **Installed files: 0; created installation directories: 0; copied bytes: 0. Native installed readback, installation receipt/ACK validation and complete V2 installation preflight: NOT EXECUTED/NOT PASSED.** No existing selected release, selector, shortcut or financial directory was written. The complete selected-release integrity audit remains pending; untouched-by-this-action is not a substitute for that audit.

No implementation changed, so the historical 223-pass regression selection was not repeated or relabelled as current installed acceptance. Only service and genuine clock observations were executed. Original native failures, cache variance, unattributed metadata-digest finding, all private evidence and unrelated changes remain preserved. B1/C1/D1/E1, all 21 decisions, seven phases and PERSONAL_PAPER_ONLY_V1 remain unchanged.

## Remaining blocker and next boundary

The service-start action is complete; a second start, another elevation attempt, resync or configuration experiment is not authorized by this consumed service-start scope. **The immediate blocker is clock quality, not service startup: 7,933 ms exceeds 1,000 ms.** Further read-only clock-quality diagnosis or a later fresh recheck should be separately scoped; any suggested system correction requires explicit authorization before application. No peer/polling/dispersion change is proposed as already approved.

If genuinely qualifying clock evidence becomes available through authorized actions, the existing unused V2 one-copy grant can resume the remaining source/resource/selected-release/native preflight and exact unselected-copy adapter. Every original condition still applies, and any failed check stops the operation. Promotion, providers, financial custody/inception and PAPER startup remain outside that grant.

**W32Time: Running / Manual. V2 operational copy: authorized but NOT STARTED. PAPER startup: NO. Production: NO-GO.**
