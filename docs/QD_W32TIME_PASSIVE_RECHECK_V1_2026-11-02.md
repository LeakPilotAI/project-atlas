# W32Time passive recheck V1 — genuine clock acceptance

Starting checkpoint **2915d4794b4befcc691783b80e85ad8bb4e99f87**, branch `chatgpt/atlas-rebuild-v1`.

**Atlas accepted fresh installed-runtime clock evidence at 185 ms.** This satisfies the unchanged 1,000 ms uncertainty and 120-second source-evidence-age requirements for this observation. The temporary capability was immediately revoked. No deployment or financial authority was granted or used.

## Bounded read-only execution

The authorized ceiling was 300 seconds. The first observation passed, so collection stopped after **3.639 seconds**, including the following detailed OS query. There was no reason to continue polling after acceptance.

The exact D:-resident application interpreter and installed `LocalWindowsClock` implementation performed genuine operational-mode acquisition. A token check confirmed the diagnostic was **not running as administrator**. No mock, injected evidence, substituted clock implementation, validator modification, service control, resync, configuration change or system-time adjustment was used.

Private raw evidence is retained at `D:\Work\Project Atlas\logs\diagnostics\qd-w32time-passive-recheck-v1-20261102` and excluded from Git. Process identity details remain private.

## Accepted evidence

Collection completed at **2026-11-02 07:44:32.6181739 UTC**.

| Required field | Actual accepted observation |
|---|---|
| Initial uncertainty | **185 ms** |
| Final uncertainty | **185 ms** |
| Lowest observed uncertainty | **185 ms** |
| Number of acquisitions | **One; passed** |
| Source evidence age | **16.3538423 seconds** |
| Source | **time.windows.com,0x9** |
| Leap / stratum / last sync error | **0 / 5 / 0** |
| Last successful synchronization | **2026-11-02 01:44:16 Central** |
| Root delay | **0.0326090 seconds** |
| Root dispersion | **0.0321482 seconds** |
| Phase offset | **0.0054892 seconds** |
| Collection interval | **2.2932175 seconds** |
| Binding domain | **LOCAL_WINDOWS** |
| Capability after observation | **Revoked** |

The immediately following separate OS query confirmed W32Time **Running**, configured type **NTP**, configured and effective source **time.windows.com,0x9**, Leap 0, Stratum 5 and Last Sync Error 0. Its source age had advanced to **17.7904917 seconds**; this is not the age used in the accepted construction. It reported state machine **Sync** and runtime poll interval **7 (128 seconds)**. No startup-type change was issued; no new startup-configuration query was required to obtain this clock evidence.

## Trend and uncertainty interpretation

The preceding bounded diagnostic ended at **1,922 ms**; this new observation accepted **185 ms** without any Atlas service or configuration operation. Reported dispersion fell from the preceding **1.7754289 seconds** to **0.0321482 seconds**. The observations support an improvement during normal Windows synchronization. There is only one sample in this new run, so it cannot establish within-run stability, oscillation or long-term reliability. It does not establish a Windows configuration defect.

The largest **measured source-quality term** is root dispersion, **32.1482 ms**. Half the root delay contributes **16.3045 ms**, and absolute phase offset contributes **5.4892 ms**. Offset alone is not the uncertainty bound.

The largest **overall budget allowance**, approximately **129.324 ms**, is the unchanged conservative 500 ppm holdover model applied to source age, the planned 240-second capability lifetime and collection interval. Of that allowance, **120 ms** reserves the planned lifetime. The model also includes measured wall/QPC skew and its existing 1 ms margin, then rounds upward. The actual unchanged validator returned **185 ms**; no alternate bound was substituted. This remains conditional local Windows/NTP evidence, not cryptographically authenticated remote UTC or protection against hostile same-user code.

## Preservation and next boundary

No product code changed and no previous regression suite was repeated. The diagnostic process exited, the temporary capability was revoked, and no application host, provider, financial service, operational directory, release selection, account or desktop shortcut was activated or changed. No Genesis access. Historical failures, unrelated work, all 21 decisions, seven phases and B1/C1/D1/E1 remain preserved.

This is a clock-only milestone. **Full read-only deployment preflight remains pending**: exact installed application integrity, support package, native identities/ACLs, original receipts/ACKs, dependencies, namespace/resource limits, selector and rollback readiness, provider-disabled configuration and financial isolation must still be verified. Fresh clock authority must be reacquired for that future work; this revoked observation is historical evidence only.

After that preflight passes, obtain the operator's requested confirmation before any operational installation, selection or launch. This diagnostic authorizes none of those actions. No configuration correction is recommended on the basis of this passing observation.

**PAPER: NO. Production: NO-GO.**
