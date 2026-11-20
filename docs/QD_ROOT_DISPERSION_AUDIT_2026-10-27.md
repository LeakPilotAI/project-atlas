# Root dispersion and Atlas budget audit — 2026-10-27

## Current facts

Entry75cb8a17239247e63699573d2fca6fba8a3a55a8;branch chatgpt/atlas-rebuild-v1. Unrelated native edits preserved. No resync, service restart, Windows setting/source change, provider activation, financial account access or Genesis access in this increment.

Windows remains Running/Manual,NTP,time.windows.com,0x9;Leap0/Stratum5/error0. Last successful sync21:32:32Central. Root dispersion remains7.9358214s,root delay0.0341518s,phase offset-0.1656588s,StateMachineHold1. PeerActive/Client,ValidDataCounter1,Reachability3,HostPoll10. A peer timer read showed32533.407seconds until next normal poll. Current native binding's fresh status query showed source age493.2346258seconds and refused CLOCK_STALE_OR_NEGATIVE_QUALITY: the age exceeds its unchanged120second cap. The negative-quality alternative is not present here. Root dispersion independently still exceeds1000ms. No anchor issued;QD commissioning unused/account uninitialized.

Settings:SpecialPollInterval32768seconds(9h6m8s);MinPollInterval10(1024s);MaxPollInterval15(32768s);peerflags0x9 include SpecialInterval0x1 plus Client0x8. LocalClockDispersion10;HoldPeriod5;FrequencyCorrectRate4;PhaseCorrectRate1;UpdateInterval360000;UtilizeSslTimeData1. NtpClient Enabled/InputProvider1;VMIC also Enabled/InputProvider1 but earlier native events describe unsupported environment, and the selected source is NTP. No evidence makes VMIC or SSL seeding the cause of the current estimate. Recent Operational264/265/266 match the previously approved21:32recovery;263 notifications are retained without inventing an actor or an unobserved setting change.

## What contributes to dispersion?

Three read-only packets from the currently selected public peer168.61.215.74 advertised upstream root dispersion0.0100555/0.0100708/0.0101013seconds and root delay0.0000610seconds;RoundTrips29.039/34.3387/31.8644ms. This is a contemporaneous comparison, not a reconstruction of the exact packet Windows previously selected. Local7.936seconds is therefore not simply the current server's10ms advertisement. Stripchart is diagnostic and does not populate W32Time's filter or synchronize the PC.

NTP's root error estimate combines upstream quality with local filtering, jitter, measurement precision, residual offset and aging. The RFC5905 clock filter starts with an eight-slot dummy register. New valid packets replace dummy entries; elapsed time alone does not replace them. Its illustrative dummy contributions after1..8valid samples are7.9375,3.9375,1.9375,0.9375,0.4375,0.1875,0.0625,0seconds. **Leading inference:** one valid Windows sample, Hold state and a7.936second estimate are consistent with an underfilled filter perpetuated by infrequent polling. This is not a proven extraction of Windows internals: read-only status/events expose neither its full filter register nor exact per-term allocation. Do not subtract an assumed dummy contribution to force acceptance. [RFC5905 section10](https://www.rfc-editor.org/rfc/rfc5905.html#section-10).

Microsoft defines LocalClockDispersion as internal-clock accuracy when sources cannot be acquired;its10second setting is not proof that this synchronized estimate equals that value. Setting it to0 would not demonstrate improved accuracy and is not recommended. [Windows Time tools/settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings).

## Atlas calculation audit and source correction

No units error: Windows quality values are seconds, QPC nanoseconds divide by10^9, and the final sum multiplies by1000 with upward Decimal rounding. Root-delay is halved as a distance allowance. Existing anchor validator,1000ms ceiling,120second source-age cap,source/authentication/boot/restart checks and declaration shape remain unchanged.

The previous estimator did overcount query latency: it added the entire PowerShell execution time as UTC displacement, although actual UTC and QPC were collected locally and their disagreement measured. Corrected only that interpretation. New model NTP_QUALITY_WITH_MEASURED_SKEW_AND_QUERY_AGING_V2:

root_dispersion + root_delay/2 + abs(phase_offset) + measured_wall_QPC_skew +0.001 +0.0005*(source_age+validity+collection_elapsed), all in seconds, rounded UP to milliseconds.

Query duration now ages the quality estimate at the same conservative500ppm rate;actual wall/QPC skew is explicitly included and must be<=10ms. The collector retains its high-resolution discontinuity check and12second query deadline. No caller can omit the measured-skew input. Native read and refresh paths both supply actual before/after measurements.

Root dispersion may already contain residual-offset and aging terms under the NTP model. Those extra Atlas terms remain deliberately conservative because exact Windows composition cannot be verified here. No advertised dispersion,phase orholdover term was silently subtracted. The500ppm allowance remains an explicitly conditional personal OS/NTP model, not certified physical clock accuracy.

Replaying the unchanged private recovery cut with its original1.2464776second collection and22.8microsecond measured skew changes9494ms to8248ms. It STILL refuses. This replay is an offline arithmetic audit, not fresh operational evidence. Root dispersion alone rounds up to7936ms. Improving collection speed cannot solve that dominant error.

## Can normal waiting solve it?

Only additional genuine accepted samples might reduce a startup filter estimate;idle waiting alone does not improve accuracy and aging can increase uncertainty. The local estimate stayed unchanged between source ages234.5,298.1 and493.2seconds. With a32768second poll and120second source-age requirement, most of every poll interval necessarily refuses as stale, even if dispersion later improves. New packets under the existing schedule may improve the estimate over hours/days, but cannot sustain the requested desktop pilot freshness. No immediate/pass guarantee is made from a model of another implementation.

## Smallest supported correction — PROPOSED, NOT APPLIED

Keep the source time.windows.com,0x9,Manual startup,MaxPollInterval15 and every other Windows/Atlas setting unchanged. Proposed two DWORD changes:

1. HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config\MinPollInterval:10 ->6.
2. HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient\SpecialPollInterval:32768 ->64.

Then one w32tm /config /update reload, NOT /resync. This changes normal background poll cadence, not the claimed accuracy. MinPollInterval must also change because modern Windows bounds SpecialPollInterval by Min/Max poll values;changing only32768 to64 could be clamped to1024seconds and still conflict with120second freshness. Microsoft documents64second values and /config /update for accuracy-oriented configurations;this narrow proposal does not adopt its other startup,frequency,SSL orclock-update changes. [Microsoft high-accuracy configuration](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/configuring-systems-for-high-accuracy), [poll setting semantics](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings).

**Exact operator decision required:** authorize those two settings and one reload, retaining old values privately, then at most15minutes of read-only observation of normal samples (at most16native clock checks). No manual resync, service restart, source/startup change or other registry value. Normal NTP traffic becomes more frequent for this PC,including outside Atlas;this is a real system change requiring consent. No proprietary provider/data subscription is involved. If reload does not bring a new normal sample within150seconds, stop observation and report rather than resync/restart. No claim of successful correction until new actual evidence passes unchanged gates. Proposed failure rollback, only if also approved:restore these exact two original values and reload once;preserve evidence. Never adjust LocalClockDispersion ordata quality fields. A64second cadence is a reasoned small corrective experiment,not proof that this public source/environment meets the target.

If genuine clock acceptance passes,continue the SAME previously approved QD-only installation/once-only1000simulatedUSD/currentresearch-IEX/60secondpilot/reconciliation/ownedStop/restart sequence subject to all other mandatory checks. No renewed financial permission is requested here.

## Verification

Focused clock checks:66passed,0failed,0skipped,3session tests deselected. Relevant broader suite:355passed,0failed,0skipped,18deselected in12.93seconds;includes risk/accounting,inception,personal runtime,current pins,reports anddesktop policy. Focused66case rerun after adding the diagnostic model identifier also passed in2.16seconds;these overlap and are not summed. Ruff/AST checks pass. Six added cases demonstrate latency-versus-error semantics,invalid/skewed/missing measurements and continued refusal of the actual7.9358214second dispersion. Existing synthetic exact-budget assertion updated only after verifying57.001ms rounds UP to58ms under the corrected formula;no test weakened to accept real high dispersion.

Prior349passes,original failure evidence,all clock attempts and existing historical records retained. Private current signed-tool evidence is logs/diagnostics/qd-root-dispersion-diagnosis-20261027.json;not published. No financial balance,position,equity orP&L exists to report. PAPER not started;productionNO-GO.