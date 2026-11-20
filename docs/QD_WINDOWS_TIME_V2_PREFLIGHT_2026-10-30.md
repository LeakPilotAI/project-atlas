# QD Windows Time V2 preflight — October 30, 2026

Base: `13cc83a2c9f9f674a5fab97fa7b362060a0fc9d6`. Authorization: **QD-WINDOWS-TIME-V2-PREFLIGHT**, bounded read-only review and at most one necessary administrator inspection; offline corrections allowed. **Read-only preflight complete. No experiment or Windows configuration change occurred.**

## Actual Windows evidence

Normal-permission inspection and the existing `_WindowsProbe` were refused when reading the Windows Time registry parameters: `Requested registry access is not allowed`. No retry with modified permissions or alternative clock declaration was used. The single explicitly authorized UAC inspection then completed successfully: **one elevation, 5.550 seconds total, elevated child exit 0, retained owned child exited**. Its four bounded `w32tm /query` modes were configuration, source, peers and status. An owned D:-resident Python child ran the existing source-pinned native probe, unchanged uncertainty validator and actual `LocalWindowsClock` binding. The capability was revoked before that child exited; no trust credential or persistent operational authority was installed.

The read-only elevated evidence was collected **07:13:22–07:13:24 Central**. Before/after selected registry/source/service snapshots were identical. Effective configuration returned exit 0 and confirmed:

| Setting | Fresh observed value | Effective origin |
|---|---|---|
| Service / startup | Running / Manual | Read-only service snapshot |
| Configured source / type | `time.windows.com,0x9` / NTP | Local |
| MaxPollInterval | **15 — restored original** | Local |
| UpdateInterval | **360000 — restored original** | Local |
| MinPollInterval / SpecialPollInterval | 6 / 64 | Local |
| PhaseCorrectRate / FrequencyCorrectRate | 1 / 4 | Local |
| LocalClockDispersion | 10 | Local |
| NtpClient Enabled | 1 | Local |

One peer was Active, client mode 3, peer stratum 4, reachability 31, ValidDataCounter 7, zero resolve attempts and LastSyncError `0x00000000`. The peer output reported HostPoll/PeerPoll exponent 4 while the status output reported Poll Interval exponent 7 (128 seconds). These are separately retained Windows runtime reports, not proof of a particular request schedule or reason to alter the effective configuration. Peer authentication was **NoAuth**: no cryptographic authentication of the remote NTP source or independent UTC certification is claimed.

## Genuine Atlas clock acceptance

The unchanged validator accepted **964 ms**, and a separate genuine `LocalWindowsClock` construction and operational runtime-binding check also accepted **964 ms**. No fixture or offset-only substitute entered either path.

| Input at native acquisition | Observed value |
|---|---:|
| Leap / system stratum / last error | 0 / 5 / 0 |
| Last successful sync, Central | 07:12:59 |
| Synchronization age | 25.0689543 seconds |
| Root dispersion contribution | 794.1868 ms |
| Half root delay | 16.21785 ms |
| Absolute phase offset | 19.4121 ms |
| Measured wall/QPC skew | 0.007 ms |
| Drift over sync age | 12.53447715 ms |
| Drift over 240-second validity | 120 ms |
| Drift during 0.761068-second collection | 0.380534 ms |
| Fixed margin | 1 ms |
| Combined sum / rounded ceiling | 963.73876115 / **964 ms** |

The existing **1,000-ms bound, 120-second source-age limit, continuity checks and native acquisition semantics remain unchanged**. Local authentication binds actual Windows evidence to that live process; it does not add an authenticated remote UTC service. Successful synchronization alone was not treated as acceptance.

This is a time-limited measurement, not permanent clearance. The temporary capability was explicitly revoked and its process exited; the snapshot cannot authorize a later session. Fresh runtime evidence is still mandatory. The ordinary execution context's registry refusal remains a deployment-access issue to validate in the eventual installed runtime. This inspection does not establish that ordinary installed operation needs administrator rights, diagnose a Windows ACL defect or authorize any permission/configuration change.

## V2 code and evidence review

The original 78 guard cases were reviewed and re-executed. They include actual module invocation and the successor's extracted scope/effective wrappers, with timestamp advancement through application and restoration. They exercise the original failure and distinguish static configuration from the one narrowly permitted `LastKnownGoodTime` advance. They also preserve refusal for source/service/configuration changes, partial application, target conflicts, failed restoration and missing readback/evidence acknowledgements. These are offline tests, not a completed native experiment.

One additional defect was confirmed in the prepared native payload's declaration condition: PowerShell treats a nonempty string such as `binding_verified='false'` as true. The already strict injected transaction flow did not have this defect, but its tests alone did not cover this native condition. An in-memory replay of the exact old condition reproduced that incorrect acceptance; the missing-bound and boolean-bound controls in that replay refused. Raw reproduction results are retained, not hidden.

The native wrapper now delegates to the pure **`Assert-AtlasTimeQualification`** helper. It requires exactly the seven declaration fields, exact boolean `true`, integer bound below 1,000, exact string nonce/domain/source/hash bindings, positive integer QPC counters/frequency and a nonfuture observation no older than five seconds. It does not manufacture clock authority; a separately reviewed parent still must authenticate the actual local capability and proof. The module's canonical source pin was refreshed in the successor. The default refusal and restricted two-setting write names remain intact.

**Thirty new offline cases** exercise the actual extracted native qualification wrapper: valid and exact boundary values; string/integer/false acknowledgements; missing/extra fields; boolean/string/float/negative/excessive bounds; synthetic-domain substitution; source/nonce/hash substitutions and arrays; future/stale/string/boolean/zero counters; invalid frequency; and nonfinite time. No Windows effects execute in these cases.

Rollback still records target readback separately from full scope and receipt verification, refuses to overwrite conflicting target values, never rewinds synchronization timestamps and cannot turn failed/incomplete verification into experiment success. The actual native apply/reload/rollback/parent-watchdog lifecycle remains **NOT EXECUTED** under V2. The new read-only Windows result verifies current target restoration, not a retrospective full-run success.

## Validation and preservation

- **295 distinct pytest cases passed, 0 failed, 0 skipped, 13.57 seconds**: all prior 78 guard cases, 30 new declaration cases, Windows clock/IEX boundaries, PAPER policy and roadmap archival checks. The prior milestone's separate 17 dependency cases and complete 282-case evidence remain preserved; they are not counted as new executions here.
- Three PowerShell source/test files passed syntax parsing; changed Python test passes Ruff. PAPER static audit: **642 sources, zero issues**, no startup authorization.
- Offline replay still accepts the original recorded 64.5331075-second timestamp advance and restored cut. All **nine original files / 97,221 bytes** and the original private payload match their prior SHA-256 hashes.
- Original report, `UNRESOLVED_ROLLBACK_NOT_CONFIRMED_STOP` / exit 42 and `rollback_verified=false` remain unchanged. The 26-second aborted experiment and its 1662/1656-ms refusals are not relabeled. The new current readback is separately dated evidence.
- Private read-only reservation/child/final receipts are `logs/diagnostics/qd-w32time-v2-admin-*-v1.json`; native diagnostics and refusal are `qd-w32time-v2-preflight-readonly-v1.json`; offline regression output is `qd-time-v2-preflight-regressions-v1.txt`. Raw evidence and earlier warnings/failures remain retained; no machine SID is committed.
- Roadmap uses the tested archival updater. Previous checkpoint bytes, seven phases, 21 historical decisions, B1/C1/D1/E1 technical gates, personal sole-operator policy, protected accounts/journals, unrelated work and Genesis isolation are preserved.

## Decision and next authorization boundary

**No further Windows Time configuration experiment is justified by this preflight. No configuration change is recommended now.** The restored settings produced genuine qualifying evidence without a reload, restart or resync. One passing snapshot does not establish long-term clock reliability or explain the entire history of uncertainty variation; the latest small phase offset is the immediate measured reason the combined envelope now fits the threshold.

V2's reviewed guards are ready for a future separately authorized test if clock evidence later demonstrates a need; its full native lifecycle has not been accepted. This read-only authorization is consumed for the single elevated inspection and never permits applying 6/100 or another tuning change.

The next useful authorization would be a **bounded installed-runtime read-only clock/access and readiness validation**: exact reviewed D: candidate and owned processes, no active replacement, no settings changes, no provider traffic, no financial writer or account mutation. It should establish whether the intended ordinary process can obtain its own fresh native clock capability. Actual promotion/resource enrollment, accepted current research and executable entitled IEX evidence, once-only inception and the 60-second PAPER pilot remain behind their existing explicit scope and technical gates; none may run under this preflight. Any later Windows tuning requires a new, exact setting/reload/deadline/rollback approval, not reuse of this query grant.

**Current-state readback: COMPLETE at the recorded cut. Clock sample: ACCEPTED 964 ms, temporary capability revoked. V2 experiment: NOT EXECUTED. PAPER startup: NO. Production: NO-GO.**
