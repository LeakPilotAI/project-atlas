# Windows Time approved start-only result — 2026-10-27

## Scope and actual actions

Operator approved starting existing W32Time, leaving Manual startup and time.windows.com,0x9 unchanged, observing normal synchronization and inspecting stop causes. Direct Start-Service lacked Windows service-control permission. One standard Windows UAC net.exe start W32Time succeeded (exit0). No explicit resync, manual time adjustment, source, service configuration, scheduled task or firewall change was performed.

## Clock evidence

At20:59:14 Central, Operational257 recorded service startup. System37 and Operational264 reported receiving valid time data from the configured hostname. Its resolved address differed from the morning; hostname configuration did not change. At the final status read, about86 seconds after startup:

- Service Running; startup Manual; configured Type NTP, peer time.windows.com,0x9.
- SYSTEM clock status: Leap3, Stratum0, Source Local CMOS Clock, Last Sync Error1, Last Successful Sync Time unspecified, State Machine0 Unset.
- RootDelay and RootDispersion both0. These unset values DO NOT establish zero uncertainty.
- Time since Last Good Sync Time displayed85.9165630s, but without any successful system sync timestamp and with Leap3. It is not accepted synchronization-age evidence.
- PEER view: Pending; last-success timestamp20:59:14/error0, but ValidDataCounter0, Reachability0, Mode0 and peerStratum0. Successful packet/provider activity is not successful system-clock synchronization.
- Existing SpecialPollInterval32768seconds. Final peer timer32682.070366seconds (~9h04m42s). No wait through that entire interval, retry loop or background task was installed.

Current uncertainty is UNESTABLISHED, not measured as zero or asserted greater than1second. No accepted anchor was issued. Atlas's unchanged validator still requires authenticated integer uncertainty_ms0..1000, bounded expiry, boot match and monotonic/wall continuity. Previous morning Leap0/Stratum5 and7.8018211second dispersion remain historical evidence. Earlier diagnostic offsets are not used as uncertainty proof.

## Why stopped

System1074 records a user-initiated PC power-off at09:39:48Central, System6006 event-log shutdown at09:39:58, and System6005 event-log startup at20:32:57. Today's service absence is consistent with that shutdown/reboot and Manual startup. Both existing Windows time tasks, SynchronizeTime and ForceSynchronizeTime, are Disabled. Service triggers include domain-join and custom state-change starts; no stop trigger was shown. Failure-recovery actions specify restart delays60/120seconds; they do not establish a crash occurred.

No W32Time-specific crash/stop entry was found in the selected Service Control Manager event query, and no Operational258 stop entry was returned for the inspected day. Thus repeated unexpected service termination is NOT established. The PC power cycle explains loss of the earlier running service across sessions; the exact cause of any other stop remains unknown. Operational263 morning configuration-update notifications were retained as events, not attributed to a particular actor or claimed as unauthorized configuration differences.

Microsoft documents Manual/triggered behavior on workgroup systems: https://learn.microsoft.com/en-us/troubleshoot/windows-client/active-directory/w32time-not-start-on-workgroup . That explains a possible normal mechanism, not proof that a scheduled task stopped this machine's service. No documented remedy involving trigger deletion or Automatic startup was applied.

## Disposition / legitimate next step

BLOCKED_RUNNING_BUT_UNSYNCHRONIZED_AND_UNCERTAINTY_UNPROVEN. Leave the approved existing service running with unchanged configuration. A later read-only check after its normal scheduled poll is permitted, but no immediate completion or<=1second quality is promised. A single explicit resync would need new operator authorization and might restore system synchronization, but would not by itself prove the required uncertainty. No time-source/configuration correction is justified as a proven fix from present evidence; do not reduce LocalClockDispersion or invent an anchor.

The existing QD-only commissioning authorization remains unused. No operational account, financial publication, provider, trading service, V5 child or Genesis access. No application code changes or unrelated regressions were necessary. Private raw status/peer evidence: logs/diagnostics/qd-clock-start-only-20261027.json (excluded from publication). Previous recheck and synchronization reports preserved.