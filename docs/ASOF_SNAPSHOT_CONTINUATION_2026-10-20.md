# As-of quote/bar snapshot correction — 2026-10-20

Continued automatically after receipt-vintage acceptance. Production remains
NO-GO; all 21 canonical decisions, startup denial and the existing native Goal are
preserved. No provider, Atlas, Docker, Genesis or protected-state operation occurred.

## Confirmed defect and repair

The isolated ReplayStore selected the newest retained event before testing whether
its receipt was known by the report clock. A newer future receipt could therefore
return NOT_YET_OBSERVED and hide an earlier eligible observation. The original
six-case reproducer failed for both quotes and bars in all three market sessions;
the original source and failing output are retained.

`scripts/observation_runtime/market_replay.py` now selects the newest event with a
known receipt. The scan is lazy and checks visited row/query identity, retained
digests and event/end/receipt chronology. Its explicit 10,000-candidate search
bound refuses rather than claiming absence when earlier eligibility is unknown.
The cursor closes on successful selection and failure. A large table does not
fail merely due to its total size when its first candidate is already eligible.

Freshness thresholds, session/date checks, delay-unit semantics, stale-price
suppression and separate reference values are unchanged. No earlier value is
silently promoted to fresh across a market-session boundary. Empty stores remain
UNAVAILABLE; stores with only future receipts remain NOT_YET_OBSERVED with no price
or reference leakage. Corrupt future-prefix evidence refuses, rather than being
silently skipped. No stored observations or journal formats are changed.

This changes only the isolated read-only fixture factory. It is not a production
provider/scanner correction, a coherent multi-symbol snapshot guarantee, real
monitoring completeness, external-writer exclusion or live-market acceptance.

## Exact validation

- Final selected Python regression: **279 passed, 0 failed, 0 skipped**, including
  17 new as-of selection tests plus the prior 262-case selection.
- Node consumers: **253 passed, 0 failed, 0 skipped** with unchanged frontend code.
- Targeted Ruff, compilation and Git whitespace checks pass. The existing updater
  PowerShell syntax acceptance from this same execution remains valid; no Windows
  source changed. No full-repository or global lint waiver is claimed.
- New tests cover all session paths, future receipts, previous-session/stale
  fallback, delayed quotes, empty/unobserved states, corruption, rehashed invalid
  chronology, a 10,000-future-event prefix, lazy cursor cleanup and the actual
  GET-only API/HTML without storage mutations. Existing actual API fixtures and
  legacy export compatibility tests still pass.

The original six failures remain. One additional adversarial fixture initially
tried collecting a premarket quote after the regular-session boundary; the strict
normalizer correctly refused it. Its collection timestamp was corrected without
weakening the session contract; that failure log is also retained.

## Readiness and exact continuation

Offline ingestion/storage/API/research/export/consumers support premarket, regular
and after-hours fixtures. Main Atlas/dashboard startup remains locked and untested
in this execution; current process/Docker health was not re-enumerated. The local
offline artifacts are usable, not authorization to start the full application.

Live collection still requires verified provider/exchange automated-use/session
entitlements, historical/storage/display rights, credentials without disclosure,
wire budgets and timestamp/delay/adjustment behavior, plus separately approved
observation-only runtime admission. No subscription/key or entitlement is assumed.
The shortest safe path remains those prerequisites followed by bounded read-only
acceptance denying PAPER/prediction/live/Discord actions; no startup bypass.

Next selected task: a consistent sanitized failure contract for the isolated ASGI
market-data factory. Corrupt/locked/over-budget stores currently raise an unhandled
exception rather than explicit no-store refused API/HTML responses. Reproduce with
synthetic sources, return truthful non-success without partial fresh data or stale
model reuse, preserve original exception evidence and all successful response
bytes. Do not modify production routes, authority or provider behavior. Then
continue independent Evidence Engine/AFI reliability work.

Evidence: `logs/diagnostics/asof-snapshot-20261020`; the approved updater verifies
backup equality, exact read-back and historical bytes outside its managed section.
All seven phases and all 21 decisions are retained in the master. AFI-1–10 remain
PENDING. E136 consent/recovery/no-backfill/quarantine, PM-V2 no-combo/stacking/
averaging/opposing-YES-NO, prediction PAPER exactly-once/predeadline/autoflat,
Gaming resource/normal-cadence requirements, PAPER_ONLY/MANUAL_ONLY and
Atlas/Genesis separation remain. No VPS or external scheduler is introduced.
