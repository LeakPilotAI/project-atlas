# W32Time recovery and deployment resume V1 — service-start permission refusal

Starting checkpoint **4fd24d862b1c28a0db9e4008114d881b6182bf38**, branch `chatgpt/atlas-rebuild-v1`.

**The single authorized normal-permission service-start attempt failed with Windows “Access is denied.” Execution stopped at Phase 2 as instructed. No operational deployment or release selection occurred.** This was a Windows service permission refusal, not an automatic approval-review rejection or a measured clock-quality failure.

## Actual recovery and service attempt

Recovered the canonical roadmap, autonomous state, previous clock-refusal report and exact reviewed handoff. HEAD/branch matched the directive. The handoff raw SHA-256 remained **ca4b2bfe48d53d3ce0318dcdff089394b04cbbebbd774736c3bebede0644a7ed**. The unrelated research-test edit and all historical evidence were preserved.

One ordinary Windows PowerShell `Start-Service -Name W32Time` call was made through the normal service-control interface. No UAC administrator start, alternative service-control method or retry was attempted.

| Measurement | Actual result |
|---|---|
| Attempt began | **2026-11-02 07:27:21.7218938 UTC** |
| Attempt and post-check finished | **2026-11-02 07:27:22.5193607 UTC** |
| Service before / after | **Stopped / Stopped** |
| Startup mode before / after | **Manual / Manual** |
| Configured source before / after | **time.windows.com,0x9 / time.windows.com,0x9** |
| Configured type before / after | **NTP / NTP** |
| Start requests | **Exactly one** |
| Start result | **CouldNotStartService — Cannot open W32Time service — Access is denied** |
| Configuration change | **None** |

The required service preconditions passed before the attempt. The caller could inspect the service and configuration but could not open the service with the access needed to start it. The tool permission allowing execution outside its restricted process context did not grant Windows administrator rights. The exception occurred at `ServiceController.GetServiceHandle`/`Start`.

Because the service did not start, no passive synchronization observation window or fresh Atlas clock acquisition followed. **Current accepted uncertainty and evidence age are unavailable.** Historical 196 ms or other passing measurements were not reused. The unchanged limits remain **1,000 ms** uncertainty and **120 seconds** evidence age.

No forced synchronization, source/startup/registry change, service reload/restart, manual clock adjustment or firewall change occurred. The grant's one normal start attempt has been used; it does not authorize an automatic administrator retry.

## Operational outcome

- The intended application remains **2c039af29dfefd1df77e0caa3db3fdf5ed188118**. No payload was modified or recopied.
- The reviewed support identity remains **5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc**, deployment manifest **7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3**, archive **dc6269c8b7ff6babcf73340c5aa5987a128ae1d76e6092ce1def653814af01bf**. No substitution was made.
- `D:\AtlasRuntime\launchers`, `D:\AtlasRuntime\support-installations` and `D:\AtlasRuntime\selection` remain absent. **Zero new operational entries or payload bytes.** No new support intent, receipt, ACK or selector record.
- Full native release/resource/ACL/ACK/dependency/rollback preflight and installed acceptance were **not executed** after the mandatory service failure. Prior receipt/source checks are not substituted for that future preflight.
- **No first Open, dashboard/browser check, Stop timing, restart or final Stop.** No host process, HTTP request, port or lifecycle handle was created. The short-lived diagnostic PowerShell process returned; no owned runtime required shutdown.
- No selection changed, so no rollback was necessary. Previous releases and desktop shortcuts were not modified or executed.
- No financial service, account enrollment/inception, custody mutation, provider connection, PAPER session, live order or automatic startup. Protected financial directories, historical journals, credentials and Genesis were not accessed.

Private diagnostic evidence is under `D:\Work\Project Atlas\logs\diagnostics\qd-w32time-recovery-deployment-resume-v1-20261102`; it is excluded from Git. The operational 600-second/8,192-entry/64-MiB deployment stages never began. This attempt did not repeat a consumed native-copy or lifecycle grant.

## Validation and preserved findings

No product code changed and no pytest/native lifecycle suite was rerun. **Eighteen scoped checks passed, zero failed:** fourteen focused service/source/history checks and four final roadmap/state preservation checks. They verified the actual service refusal and unchanged configuration, exact reviewed package, absent operational destinations, unchanged unrelated edit, preserved state values, single roadmap marker pair, unchanged raw prefix/suffix and complete archived prior checkpoint. These are evidence checks, not a newly passing financial regression suite.

The earlier native suite remains **224 passed / 1 failed / 0 skipped**, with two genuine disposable Stops **1.8311834 s / 1.8491529 s** before its post-lifecycle harness failure. Six offline correction tests and the previous twelve preservation checks remain historical evidence, not new operational acceptance. All 21 decisions, seven phases, B1/C1/D1/E1, original UI and personal sole-operator authority are preserved.

## Smallest next action

The service needs a Windows identity with **Start permission**. The operator may start only existing W32Time from an administrator Windows session while leaving Manual startup and `time.windows.com,0x9` unchanged, or separately authorize **one administrator-elevated start attempt** through the normal Windows approval path. No resync or configuration change is needed merely to resolve this permission failure.

After reporting that it is running, explicitly resume the same reviewed nonfinancial deployment scope: collect fresh genuine clock evidence, permit only bounded passive settling, then complete every original preflight before support installation/selection/two lifecycle cycles. A successful start alone is not synchronization or clock acceptance. If clock or any preflight refuses, stop without deployment. This report grants no retry, provider access, financial activation or PAPER authority.

**PAPER: NO. Production: NO-GO.**
