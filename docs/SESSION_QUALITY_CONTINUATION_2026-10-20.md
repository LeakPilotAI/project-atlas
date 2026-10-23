# Offline session-quality timeline

Production NO-GO. Previous goal turn made verified source/evidence progress; this
turn continues that work, not a completion or blocked audit. No services, provider
requests, Docker, Genesis, production storage/startup or trading/Discord activation.
All21 release decisions and the startup-lock hash remain unchanged.

## Working functionality

`session_quality.py` consumes explicit bounded replay history. It reuses Atlas's
exchange calendar, strict candle validation and existing session-history state
semantics. Completed-bar event time and first recorded receipt remain distinct.
Per-symbol windows group by New York exchange date and PRE_MARKET/REGULAR/
AFTER_HOURS, including winter UTC-midnight and early-close boundaries. Reports
provide observed counts, gaps only between first/last supplied bars, receipt-minus-
bar-end delay and latest completed-bar age at the explicit report clock. PAST_SESSION
is separate from current-session stale data; empty evidence yields NO_OBSERVATIONS.
Truncated input remains explicit. No missing minute is imputed or classified as a
missed market event, and no full-session monitoring is inferred.

Equivalent repeated event receipts count once using the earliest supplied receipt;
conflicting observations refuse. Unknown fields/authority claims, future receipt,
invalid OHLCV, provenance/session/date contradictions and unsupported calendar
input refuse. The source history as-of cannot be later than the report clock.

Optional lifecycle records require a caller-retained expected head, bounded exact
fields, consistent hashes/linkage, monotonic nonfuture observation times, exact
event/session identities and compatible state transitions. Existing synthetic
SessionHistory records are exercised directly. Interrupted or recovery-required
state remains non-clearing; later graceful shutdown cannot erase it. Recorded
completion is not current process exit proof. No source/release authorization,
independent rollback witness, external-writer exclusion or authenticated ownership
is established. Every report denies startup/recovery/trading/network permission.

The separate inert replay ASGI factory now serves `/api/market-data/quality` and
`/quality` for its explicit symbol universe. Both are read-only/no-store. The main
offline dashboard links to the quality view. HTML escapes values and has no scripts
or external resources. Main Atlas/Next startup and production routes are unchanged.
No server was launched. Actual in-process JSON/HTML are retained in diagnostics.

## Exact validation

- Initial15 new tests passed.
- Combined market/provider/calendar/research and existing bootstrap/history suite:
  246 passed,0 failed/skipped,30.86s.
- Six added adversarial lifecycle cases joined a focused21-case run, all passed.
  Distinct accepted cases across these overlapping runs:252, not267.
- Cases cover premarket/regular/after-hours, early close, DST, winter UTC midnight,
  gaps/receipt delay, first-receipt deduplication, conflicts, stale/truncated windows,
  missing evidence, actual complete/interrupted journal records, wrong heads,
  digest tamper, future evidence, replay, missing start and post-interruption shutdown.
- Targeted Ruff/compilation pass. Initial three style findings and a later test
  import ordering finding were corrected narrowly. No product test failed.
- Existing AFI, storage and frontend acceptance evidence is retained; no new full
  canonical-suite, real provider, native browser, crash or runtime claim is made.

Evidence: `logs/diagnostics/session-quality-20261020`; previous21 intended hashes
were verified before editing. The master checkpoint uses the approved updater and
checks backup equality, exact managed readback and byte-identical history outside
the managed section. All seven phases, AFI PENDING, Gaming objective, Prediction
Market Intelligence V2 and Atlas/Genesis separation remain intact.

## Next automatically selected task

Connect the actual quality JSON to the existing offline market frontend consumer:
strictly validate its schema/authority/time/window arithmetic and lifecycle scope,
preserve interrupted-state warnings and clear prior quality display on bad import.
Reuse the current controller pattern; no network fetch, Next production mount or
startup integration. Then continue independent Evidence Engine/AFI tasks. Live
data remains gated on provider rights, actual wire budgets and separately approved
runtime acceptance; do not substitute fixtures for those gates.

## Continued frontend and immutable export implementation

The selected frontend task was implemented immediately. The current Python API
response is pinned as a synthetic fixture and reproduced by the producer test.
`parseQuality` checks exact schema/fields and false permission flags, source/report
clocks, New York dates, chronological windows, count/gap/delay arithmetic and the
explicitly unauthenticated lifecycle summary. `createQualityController` preserves
interruption warnings and clears prior quality evidence on bad imports. The
existing market consumer remains compatible. These checks are consistency, not
independent provider/calendar/lifecycle authentication or native browser acceptance.

A mixed-session case reproduced alphabetical rather than chronological ordering;
the producer now sorts by first event time. Two frontend reproducers exposed a
retained model after display-callback failure. Both controllers now clear it and
preserve the original error; if refusal rendering also fails, AggregateError
retains both. This cannot guarantee a broken external renderer physically clears
its screen. Reproducers remain in diagnostics; corrected cases pass.

`quality_report.py` adds an explicit offline CLI over a reviewed portable bundle
root. A caller-pinned history hash and optional exact lifecycle head are required.
It reuses the existing immutable AFI research publisher for JSON, HTML and an input/
output-hash provenance sidecar. Publication and exact readback precede success.
Traversal, unknown/authorizing fields, wrong pins, invalid lifecycle and output
failures refuse. Later failure retains earlier outputs; no multi-file atomicity,
source authenticity, directory-wide exclusion, power-loss safety or recovery
authority is claimed. CLI errors are sanitized and never initiate collection.

Final combined selected Python suite264 passed,0 failed/skipped,35.85s. This includes
23 timeline and10 export cases plus the existing99 market/provider and132 synthetic
bootstrap cases. Earlier overlapping246/21/31 runs are not additive. Node166 passed,
0 failed/skipped; targeted frontend ESLint, Ruff and compilation pass. No full
canonical/AFI/storage suite rerun is claimed where code remained unchanged.

Actual API JSON/HTML and immutable export→frontend-consumer evidence are retained
in `logs/diagnostics/session-quality-20261020`. The previous report and fixture bytes
remain intact. All21 gate decisions, production NO-GO and full seven-phase roadmap
are preserved; the native Goal is not marked complete or blocked by this acceptance.

Next automatically selected offline task: a quote-quality companion to the bar
timeline, reusing the existing read-only quote snapshot contract. Keep bar-quality
V1 and fixtures compatible. Distinguish delayed/stale/missing/unobserved quote
references, receipt time and unverified delay units; never infer executable quotes
or live entitlement. Add actual producer/consumer evidence and no production wiring.
Then continue independent forecasting/Evidence Engine work while external gates
remain closed.
