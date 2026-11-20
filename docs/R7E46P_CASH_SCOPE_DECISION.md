# R7E46P cash-scanner scope decision (PROPOSED, NOT APPROVED)

Classification: intentional R7E44G source repairs with historical source/test
approval; explicit acceptance in the combined production release remains missing.
The current P execution is not that acceptance. No cash-scanner code is changed.

Committed comparison reference: HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0.
Historical roadmap R7E44G: 2135 passed / 3 xfailed; source regression GREEN,
runtime certification pending. O observed MARKET_OPEN cycle13:30:40UTC on2026-10-16,
about40s after opening, with6valid/17insufficient/14stale. This is evidence of a
particular opening, not acceptance of all calendar behaviors.

Exact existing differences versus committed reference:
1. `_age_ok`: future cached timestamps no longer satisfy a freshness TTL.
2. `plan_fetches`: the first regular-session price fetch is forced if last price
   predates session open, without forcing extra fundamental/valuation fetches.
3. Scanner sleep: wake at the next calendar opening rather than always sleeping
   the closed-session interval; retain60s minimum and configured open interval.
4. Calendar: explicit2026-2028NYSEholidays/early closes/DST-aware bounds, weekends,
   system-offline handling and fail-closed unsupported horizon. Unscheduled closures
   still require calendar maintenance.

Proposed operator decision, ready for explicit acceptance:
"Accept these four existing R7E44G cash-scanner behaviors in the next whole-source
release candidate, preserving current session restrictions and rate-limit settings.
This is scope acceptance only. It does not authorize Atlas restart, extended-hours
activation, trading/Discord authority changes, live benchmarking, or deployment."

Alternative: provide a specifically verified accepted baseline and explicitly
approve an isolated narrowed/restored candidate. Do not revert to the six-hour
sleep merely because the committed reference contains it; that reintroduces a
verified readiness defect. Source is preserved until a decision is recorded.

Required evidence remains calendar/DST/holiday/opening tests, independent timestamp
and first-open-fetch tests, manifest source hashes and future separately approved
live acceptance. P reuses the existing meaningful G regressions; no mirrored tests
are added solely to restate the implementation.
