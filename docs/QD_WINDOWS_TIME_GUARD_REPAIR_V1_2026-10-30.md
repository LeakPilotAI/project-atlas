# Windows Time experiment guard repair — October 30, 2026

Base: `e0de68d1ff4129352c5f41d3fd98e2de2b6d4233`. Scope: **QD-WINDOWS-TIME-GUARD-REPAIR-V1, offline source and disposable tests only**. The guard defect is corrected and tested. No Windows Time query, registry access, service operation, reload, synchronization request, administrator elevation or system change occurred in this increment. No provider, installation promotion, financial activation, PAPER session or Genesis action occurred.

## Defect and correction

The original private payload's `Assert-Scope` compared every `W32Time\Config` row except the two approved settings as immutable configuration. It therefore classified the Windows-maintained `LastKnownGoodTime` FILETIME advance as `FOREIGN_CONFIGURATION_CHANGE_LastKnownGoodTime`, both during observation and after restoring the settings. The original runner and executed payload remain unchanged.

`scripts/windows/Atlas-WindowsTime-ExperimentGuard.psm1` separates three kinds of evidence:

- **Static configuration:** exact registry name set, value kinds and values; exact service/startup/source/type/client settings; and the complete effective-configuration output, allowing only the two approved target lines to differ. Source, service and configuration changes still refuse. Only the original and approved pairs, 15/360000 and 6/100, are supported. Unexpected policy origins, missing or duplicated effective fields, extra names and malformed values refuse.
- **Expected synchronization state:** only the specifically named `LastKnownGoodTime` row may advance. It must remain a positive, valid REG_QWORD FILETIME integer, must not regress and may advance at most 420 seconds relative to the original snapshot (300-second experiment plus at most 120-second baseline age). There is no `Last*` or timestamp wildcard. Peer synchronization observations are runtime evidence, not immutable configuration. Neither timestamp advancement nor peer progress authenticates clock accuracy. The guard never writes or rewinds runtime timestamps.
- **Restoration evidence:** `target_restore_readback_verified`, `full_scope_verified`, `evidence_complete` and `rollback_verified` are separate facts. A successful target readback cannot hide a foreign source, missing effective readback or failed evidence acknowledgement. The experiment cannot report success after an incomplete rollback or verification. Foreign target values or kinds prevent overwriting another actor's setting.

The pure module also provides a transaction flow with exactly injected snapshot, effective-query, write, reload, observation, clock-verification, evidence-recording and remaining-budget ports. It has no native implementation or default authority. It freezes original evidence and port references, records intent before effects, handles partial application, permits at most one apply reload and one conditional rollback reload, and requires exact boolean acknowledgements. Budget values must be finite and non-increasing. Blocking-time enforcement remains the responsibility of a separately reviewed native adapter and retained-parent watchdog; the injected offline flow is not itself a process supervisor.

The clock validator and operational uncertainty arithmetic are unchanged. The experiment's success declaration still requires a bound **below** 1,000 ms and fresh evidence; this does not relax Atlas's existing 1,000-ms/120-second operational requirements. Synthetic evidence never grants operational authority.

## Prepared successor, not an executed experiment

`scripts/windows/Atlas-WindowsTime-ExperimentPayloadV2.ps1` is a source-only successor that delegates the actual scope/effective wrappers to the repaired module. It pins the module's canonical UTF-8/LF text, compiles those verified characters without reopening the module path, separates target and full rollback results, and checks baseline synchronization freshness. Default invocation refuses **before Windows access**. It requires explicit new-run bindings; its opt-in switch is not an authorization grant.

Tests extract only the successor's two guard wrapper definitions and exercise them against disposable snapshots. They also execute its default refusal, without an opt-in switch or administrator privileges. **The successor's real Windows effects, elevation/parent watchdog and complete native lifecycle were NOT EXECUTED.** No old launcher was activated, no new trusted launcher installed and no previous grant reused. The frozen 638-source promotion handoff and active installation remain unchanged; this source increment is not an installed release.

## Tests and evidence

| Validation | Actual result |
|---|---|
| Final guard, Windows clock, IEX clock boundary, PAPER policy and roadmap archive regressions | **265 passed, 0 failed, 0 skipped**, 12.34 seconds |
| Focused personal dependency clock/anchor regressions | **17 passed, 0 failed, 0 skipped; 3 unrelated cases deselected**, 1.74 seconds |
| Distinct final pytest cases | **282 passed, 0 failed, 0 skipped**, including **78 new cases** |
| PowerShell 5.1 syntax parsing | Three new module/payload/test files accepted |
| Ruff | Changed Python test passes |
| PAPER static policy audit | **642 runtime sources; 0 issues; startup unauthorized** |
| Retained-receipt replay | Repaired scope and effective guards accept the recorded restored cut; target readback verified as historical evidence only |
| Original evidence integrity | All **9 original files / 97,221 bytes**, plus original private payload, retain their recorded SHA-256 hashes |
| Real Windows experiment / administrator actions / financial operations | **0 / 0 / 0** |

The new cases execute the actual PowerShell module with in-memory interfaces. They cover timestamp and peer progress; malformed, backward and excessive timestamp movement; unknown/removed/replaced keys; unauthorized polling/source/service/startup/client changes; array/type coercion; effective-only changes; interrupted first and second writes; failed apply reload; failed rollback writes/reload/query/snapshot; incomplete effective restoration; failed and non-boolean evidence acknowledgements; conflicting foreign targets; restoration of originals without rewinding runtime state; clock domain/source/authentication/freshness/uncertainty refusal; budget exhaustion/reversal; and caller mutation of captured inputs. Actual Windows security privileges and native lifecycle acceptance are not inferred from these mocks.

Private test outputs remain under `logs/diagnostics/qd-time-guard-*`: initial 58-, 71-, 136- and 257-case successful increments are preserved, not added to the distinct final count. The 136-case run's seven unregistered-async-marker warnings are retained; the final run explicitly loads the existing pytest asyncio plugin and has no such warnings. No selected test starts an operational writer or provider. `qd-time-guard-retained-replay-v2.json` records the offline replay and hash verification without publishing private machine identifiers. No original receipts were rewritten or deleted.

## Historical failure and remaining boundary

The original experiment is still **ABORTED after 26.000 seconds**, with original `UNRESOLVED_ROLLBACK_NOT_CONFIRMED_STOP` / exit 42, parent refusal and `rollback_verified=false`. Its target settings were recorded restored to **15 / 360000 (Local)**, but its full automated verification did not complete. Its **1,662-ms and 1,656-ms** clock results remain refused historical measurements. No conclusion about tuning efficacy is established.

The repaired guard accepts the retained timestamp advance of **64.5331075 seconds** and the historical restored snapshot. That is an offline implementation check, **not** a fresh system readback, proof of the timestamp writer, retrospective success or current clock clearance. No live system state was acquired in this task. The prior one-run authorization remains consumed.

The next commissioning action is operator review of this source successor, followed by a **new narrowly bounded authorization** covering fresh current-state/rollback preflight and, if desired, one corrected Windows Time experiment with exact settings, deadline, evidence and rollback requirements. No new experiment or administrator reinspection may run under this offline grant. Qualifying actual clock evidence, accepted current research/source custody, fresh entitled executable IEX observations and scoped operational installation/resource acceptance remain necessary. No account inception or pilot is eligible from these offline results.

Canonical history is updated using `Atlas-Roadmap-Checkpoint.ps1 -ArchivePriorCheckpoint`; the previous managed checkpoint remains verbatim in the master roadmap. All seven phases, 21 historical decisions, personal sole-operator policy, B1/C1/D1/E1 technical gates, prior installation and unrelated work remain preserved.

**Offline guard repair: COMPLETE. Native V2 acceptance: NOT EXECUTED. PAPER startup: NO. Production: NO-GO.**
