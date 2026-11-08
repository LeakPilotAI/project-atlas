# Read-only clock recheck — October 27, 2026, 20:52 Central

Prior successful synchronization is preserved as historical evidence, not a current health assertion.

## Actual current evidence

- Windows Time: Stopped; startup Manual (registry Start=3).
- Configured Type=NTP; peer unchanged: time.windows.com,0x9.
- Unrestricted read-only status and peers queries both returned service-not-started 0x80070426. Restricted queries initially returned access denied; they were not interpreted as clock status.
- Current local root dispersion, synchronization age, leap, stratum and last-error values are UNAVAILABLE. Earlier 09:06:21 successful synchronization and 7.8018211-second dispersion are historical, not fresh measurements.
- Three read-only diagnostic server replies at 20:52:05/07/09 Central: Leap0, server Stratum4; offsets -0.2157309/-0.2151305/-0.2163756 seconds; RTT 0.0338216/0.0308243/0.0343890 seconds. Server root dispersion 0.0100403/0.0100555/0.0100861 seconds. These are remote-server packet fields, not the stopped local service's dispersion.
- Selected Time-Service log entries include informational IDs35/37 from the morning and ID158 at09:23:25; ID158 concerns the VMIC provider, not proof of an NTP failure. The inspected Service Control Manager selection did not establish why or when W32Time stopped. Cause remains unproven.

## Exact unchanged Atlas requirement

`backend/app/services/quality_dips_personal_dependencies.py`, PersonalClockContinuity.sample, validates an externally supplied authenticated QD_PERSONAL_UTC_ANCHOR_V1. uncertainty_ms must be an integer (not bool), in [0,1000]. Anchor expiry must be within300 seconds, boot identity must match, monotonic time must not reverse and wall/derived UTC divergence must not exceed2 seconds. verify additionally requires sample freshness within1 second and unchanged uncertainty. It does not calculate uncertainty from NTP offsets or Windows dispersion. No installed derivation/accepted authority was established by this inspection.

Measured offset estimates clock displacement. Root dispersion is the advertised accumulated error estimate; total uncertainty also needs transport/asymmetry, local timestamp/rounding and holdover assumptions. A small offset or remote-server dispersion alone cannot authenticate the required local bound. No new hardcoded Windows root-distance gate is introduced, and no substitute anchor is created.

## Disposition and smallest next step

BLOCKED_CURRENT_CLOCK_SERVICE_STOPPED_AND_ACCEPTED_UNCERTAINTY_UNPROVEN. Under this read-only execution no service start, resync, source/configuration change or manual clock adjustment occurred. Request permission to start only existing W32Time, preserving Manual and configured peer, with NO explicit resync; observe its normal configured synchronization and fresh status. Starting the service may itself cause its normal NTP traffic. This is a diagnostic prerequisite, not a guaranteed fix for uncertainty. If fresh error estimates still cannot support<=1000ms, retain pause and identify a measured correction before requesting any setting change.

The existing QD-only commissioning grant remains unused. No account inception, provider activation, financial writer, V5 or Genesis access. No application source changed; existing tests were inspected, not rerun. Unrelated working-tree edits remain untouched. Independent source inspection is complete; no new financial readiness claim follows from these diagnostics.