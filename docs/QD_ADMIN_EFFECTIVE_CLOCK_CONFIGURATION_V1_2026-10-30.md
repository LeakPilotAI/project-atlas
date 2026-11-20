# Administrator effective Windows Time inspection — October 30, 2026

Base `d1c27ce90a7e0adee71e07615c4078d9afa13c3a`. The operator authorized **exactly one administrator-elevated read-only inspection**, not the correction proposal. That one permission is now **consumed successfully**. No retry or second elevated inspection occurred.

## Actual execution and preservation

At **06:00:12–06:00:13 Central**, one hidden Windows PowerShell child ran with administrator membership under the **same existing Windows operator SID**. It verified the Microsoft-signed system `w32tm.exe`, read configuration/service snapshots, and executed only:

1. `w32tm.exe /query /configuration /verbose`
2. `w32tm.exe /query /source /verbose`
3. `w32tm.exe /query /peers /verbose`
4. `w32tm.exe /query /status /verbose`

All four returned exit code **0**. Elevated inspection duration **0.273 seconds**; complete parent/elevation/read/exit receipt duration **3.394 seconds**. Exact owned elevated child exited with code 0; process handles were disposed. Standard output/error were drained asynchronously to prevent pipe-buffer deadlock. Each exact owned query was bounded to four seconds; the parent allowed 30 seconds for the inspection child. No timeout, cancellation or refusal occurred.

Before/after settings and service snapshots matched exactly. **No registry/configuration write, reload, resync, service start/stop/restart, source change, clock setting or firewall action occurred.** No market provider/network probe, installation, financial resource, account, PAPER session or Genesis access. Only private diagnostic receipts were written in the existing Atlas diagnostics directory.

Private receipts: `logs/diagnostics/qd-w32time-admin-effective-read-once-v1.json` (single-attempt reservation), `qd-w32time-admin-effective-child-v1.json` (actual elevated output), `qd-w32time-admin-effective-final-v1.json` (owned exit and outcome). Machine/process identities stay outside Git. The diagnostic runner is retained locally as `qd-w32time-admin-effective-read-once-v1.ps1`; it refuses reuse if the reservation or child receipt exists. Elevated code was supplied as a fixed encoded read-only payload, not imported from the workspace.

## Effective configuration, not merely registry expectations

The privileged query reports the following values with **(Local)** origin. None of these listed fields is reported as a Group Policy override.

| Effective setting | Observed | Existing proposal | Assessment |
|---|---:|---:|---|
| MinPollInterval |6|unchanged|Already matches the proposed lower polling bound. |
| MaxPollInterval |15|6|Proposal's original-value assumption confirmed. |
| SpecialPollInterval |64|unchanged|Existing special polling value confirmed. |
| PhaseCorrectRate |1|unchanged|No adjustment requested. |
| UpdateInterval |360000|100|Proposal's original-value assumption confirmed. |
| FrequencyCorrectRate |4|unchanged|No adjustment requested. |
| LocalClockDispersion |10|unchanged|Do not lower this declaration to manufacture evidence. |
| MaxAllowedPhaseOffset |1|unchanged|Windows' gradual-versus-step threshold; distinct from Atlas's uncertainty budget. |
| MaxPosPhaseCorrection / MaxNegPhaseCorrection |54000 / 54000|unchanged|No expansion or contraction requested. |
| ResolvePeerBackoffMinutes / MaxTimes |15 / 7|unchanged|Recovery settings are observed, not diagnosed as faulty. |
| NtpClient Enabled / InputProvider |1 / 1|unchanged|Client active. |
| NtpServer provider Enabled / InputProvider |0 / 0|unchanged|No time-server activation. |
| Type / NtpServer |NTP / `time.windows.com,0x9`|unchanged|Same configured and effective source. |
| Service state / startup |Running / Manual|unchanged|No service intervention required for this inspection. |

The peer is **Active**, mode 3/client, Stratum 4, Reachability 255, ValidDataCounter 8, with about 57.48 seconds until its next scheduled action. Peer last-success is **06:00:07 Central**; the separate status field reports **06:00:06**. Preserve those as distinct reported fields. Host/Peer poll still displays 13 (8192 seconds); this does not erase the prior observed roughly 64-second special synchronization cadence.

## Clock state and root-cause assessment

Current inspected status: Leap 0, local Stratum 5, State Machine Sync, Last Sync Error 0, synchronization age **6.4957833 seconds**, root delay **0.0318393 seconds**, dispersion **0.7947354 seconds**, phase offset **+0.7350043 seconds**. The age meets Atlas's unchanged 120-second requirement.

Dispersion **794.7354 ms** plus absolute phase offset **735.0043 ms** already totals **1,529.7397 ms**, before half-delay, validity drift, acquisition skew or any margin. Therefore **this status cannot meet the unchanged 1,000 ms model**. This is a necessary lower-bound refusal analysis, not a fabricated exact operational bound. No new operational clock anchor or runtime acceptance was issued from the receipt. The prior genuine 1,803/1,736 ms acquisition refusals remain historical; they are not relabelled as this sample's exact result.

**Confirmed:** effective local settings match the original proposal, peer contact is healthy, and residual local clock quality remains inadequate. The earlier eight unanswered attempts were followed by recorded recovery; the current configuration does not prove where those earlier packets were lost. No new evidence supports a DNS, peer or firewall change. No Atlas clock-calculation defect has been demonstrated.

**Supported interpretation:** Windows retains an approximately 0.735-second residual phase error and permits a large adaptive polling range while using a relatively large correction update interval. Windows' phase-correction algorithm depends on these parameters. Its current one-second `MaxAllowedPhaseOffset` means a sub-second residual is eligible for gradual correction rather than an immediate clock step. This explains why a successful synchronization is not itself proof that the residual disappeared; it does not certify a complete causal decomposition or a correction completion time. [Windows Time tools and correction behavior](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)

## Technical disposition of the proposed changes

**Technically justified as a bounded experiment; not proven necessary or guaranteed sufficient.** Microsoft documents MaxPollInterval 6 and UpdateInterval 100 for its high-accuracy configuration. Pairing those values with the already effective MinPollInterval 6 and SpecialPollInterval 64 is a coherent targeted discipline experiment. It does not establish the earlier loss cause or authorize adoption of Microsoft's entire profile. No Manual-to-Automatic change, Secure Time Seeding change, frequency setting change, provider change or time-source replacement is requested. [Microsoft high-accuracy settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/configuring-systems-for-high-accuracy)

The missing applicability/effective-origin evidence is now supplied. The remaining boundary is **explicit operator authorization for actual Windows writes**, not another administrator read-only diagnostic or an external reviewer.

Exact next decision: approve or reject the existing [bounded correction proposal](QD_WINDOWS_TIME_CORRECTION_PROPOSAL_V1_2026-10-30.json):

- Save and freshly verify the original typed values and unchanged effective/source/service scope.
- Change only `W32Time\Config\MaxPollInterval` **15 → 6** and `UpdateInterval` **360000 → 100**.
- One configuration reload, **no forced synchronization, service restart or manual clock adjustment**.
- Observe normal synchronization for at most **180 seconds**, and validate genuine evidence against unchanged **1,000 ms / 120 seconds** and continuity/authentication rules.
- At most **300 seconds total**, including verification and conditional rollback. On error or no qualifying clock, restore only the two recorded original values if they still belong to this experiment, then one rollback reload. Stop without overwriting a concurrent foreign change.

Risks and limits remain as recorded in the proposal: Windows clock discipline affects the whole PC and can expose discontinuities to applications; configuration rollback cannot undo elapsed time. Public NTP/network/oscillator limitations remain. Passing clock evidence would still **not** authorize PAPER startup, financial activation, providers or installation promotion under this directive.

The old correction proposal remains byte-identical with **operator_authorized=false**. Approval of its read-only alternative has not been misrepresented as approval of its settings changes. No new elevation or corrective action will be attempted without separate permission.

## Validation and continuity

Existing clock tests: **49 passed, 0 failed, 0 skipped, 0.95 seconds**. No runtime source changed; no broad suite or native financial test was repeated. The runner's PowerShell parser passed before execution. Actual elevated execution provides the inspection evidence; tests do not substitute for it. Prior 62/479/native/installed evidence is retained separately.

Canonical roadmap, autonomous state, execution queue and recovery checkpoint record the one consumed read-only authorization, effective values, lower-bound refusal and separate pending correction decision. The source handoffs, active installation, protected financial state, all 21 historical decisions and seven phases are preserved. Unrelated tracked changes and untracked evidence remain intact. No cleanup/deletion; **0 bytes recovered**.

**Administrator inspection: COMPLETE. Configuration correction: NOT AUTHORIZED / NOT EXECUTED. Clock acceptance: NO. PAPER startup: NO. Production: NO-GO.**
