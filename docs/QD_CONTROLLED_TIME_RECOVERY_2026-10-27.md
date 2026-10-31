# Controlled Windows Time recovery — October 27, 2026

## Actual recovery

Verified branch chatgpt/atlas-rebuild-v1, entry45e05b7d742ba833f06b7a38c0150ae7199502be. Preserved deferred native changes. Read roadmap, recovery state, existing clock binding and QD commissioning grant. No V5 work.

Baseline at21:32Central: W32Time Running/Manual, Type NTP, configured source time.windows.com,0x9. SystemLeap3/Stratum0/error1/LocalCMOS/no successful synchronization; zero dispersion unset. DNS succeeded, three read-only NTP diagnostics returned offsets -167.1060,-164.7807,-164.1614ms. These were not accepted as uncertainty. Relevant Time-Service events and complete baseline were retained privately.

A durable create-new one-shot reservation preceded the recovery. Exactly ONE elevated w32tm /resync was issued to the unchanged configured source at21:32:32Central. It returned exit0 and semantic output 'The command completed successfully.' Service was already running, so no start/restart was necessary. No retry, source/registry/startup setting change or manual clock adjustment occurred. This recovery authorization is consumed.

## Genuine post-recovery clock evidence

- Service Running/Manual; registry Start3; configured Type NTP and time.windows.com,0x9 confirmed unchanged by explicit postflight assertions.
- Leap0, Stratum5, LastSyncError0, source time.windows.com,0x9, StateMachine1 Hold.
- Last successful synchronization: October27,2026,21:32:32Central.
- Source age at the detailed read:15.3076162seconds; real successful-sync timestamp present and consistent.
- Root dispersion:7.9358214seconds. Root delay:0.0341518seconds. Phase offset:-0.1656588seconds.
- Read-only signed Windows tool collection succeeded. Detailed QPC interval:1.2464776seconds; wall/QPC discrepancy22.8microseconds. Those local interval measurements are not UTC accuracy evidence on their own.

## Exact failed acceptance field

Synchronization, source, timestamp and local collection now succeed. **Uncertainty fails.** Required bound<=1000ms. The independent detailed read budget is:

| Term | Seconds |
|---|---:|
| Windows root dispersion |7.9358214|
| Half root delay |0.0170759|
| Absolute phase offset |0.1656588|
| Full local collection interval |1.2464776|
| Read margin |0.001|
| Source-age plus240second validity,500ppm allowance |0.12765380810|
| Sum |9.49368750810|

Rounded upward: **9494ms**, refused by the unchanged implemented budget. A separate actual LocalWindowsClock operational construction, using its own fresh collection duration, refused with **CLOCK_UNCERTAINTY_EXCEEDED:8947ms**. These are two separately collected read budgets, not inconsistent reports from one observation. No second resync was involved. Root dispersion alone exceeds the threshold, so reducing collection overhead cannot make this evidence pass.

No operational anchor was issued. The existing downstream PersonalClockContinuity validator was not supplied an invented anchor. Its earlier synthetic acceptance/refusal tests remain valid; this actual run establishes a real acquisition refusal, not successful financial clock acceptance. No threshold, budget term or validator was changed.

## Commissioning and account results

Financial activation stopped at this mandatory failure. D:installation/enrollment, once-only1000simulatedUSD publication, QD/IEX provider connection,60second autonomous pilot, financial reconciliation, desktopStart/Stop and financial restart acceptance were NOT EXECUTED. Account uninitialized; cash,positions,fees,slippage,equity and P&L are UNAVAILABLE, not a fabricated1000balance or FLAT state. No owned financial runtime started, so there was no financial shutdown to claim. The separate existing QD commissioning grant remains valid and unused. No Hyperliquid,V5,live orders or Genesis.

## Independent permitted work and remaining correction

Independently recomputed the detailed Decimal sum and asserted9494ms, root dispersion>1second, exactlyone recovery request, no anchor and no commissioning. Those assertions passed. Actual postflight service/configuration checks passed. Source unchanged; the previously verified349passed/0failed/0skipped/18deselected regression result is retained and was not unnecessarily rerun. Private baseline, one-shot reservation, command receipt and post-binding evidence are ignored local diagnostics; no raw private evidence is published.

The remaining technical requirement is a genuine lower Windows synchronization error estimate whose complete existing bound is<=1000ms. Leave the service running and retain the normal configured poll; a later read-only check can observe legitimate updates. No immediate improvement is promised. Another explicit resync, registry/poll/source/startup change or new time provider is NOT authorized by the consumed grant. Do not relabel dispersion, lower LocalClockDispersion, subtract error terms or use spot offsets to force a pass. No particular configuration correction has been demonstrated as necessary or sufficient by this attempt; a separately scoped change would require evidence and operator approval. No new framework or external-reviewer requirement is introduced.

Roadmap/recovery state updated through the existing archival updater. Original history, unrelated working-tree files, account restrictions and all historical decisions preserved. PAPER not started; production NO-GO.