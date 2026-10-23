# Offline quote-quality companion acceptance

Previous goal turn and this turn made source/evidence progress. Production remains
NO-GO; all21 release decisions, startup denial and seven-phase scope are preserved.
No Atlas/Docker/provider/Genesis operations, protected state changes, trading,
Discord, Git mutations, external scheduler or daemon. Runtime state was not freshly
censused. This acceptance does not complete the roadmap or unblock live collection.

## Working functionality

`quote_quality.py` consumes the existing isolated ReplayStore.quote_snapshot
contract. It validates exact record fields, source/type/currency/session identity,
event and receipt timestamps, age, finite reference values and expected current-
price refusal. It emits metadata only, never prices or execution eligibility.
FRESH/STALE and nonzero vendor delay remain separate evidence: a DELAYED reference
can also have a stale event. Reported delay units remain explicitly unverified;
they are never converted to seconds. Recorded receipt-minus-event delay is a
separate measured timestamp difference, not independently verified network latency.

UNAVAILABLE and NOT_YET_OBSERVED retain null times/delays/staleness, not fabricated
zero values. Counts describe only the latest supplied reference per explicit
symbol, not feed coverage, market inactivity or downtime. Provider service health
stays NOT_OBSERVED even on successful HTTP200. Provider freshness, completeness,
network/startup/recovery/trading authority are always false.

The inert replay factory serves read-only/no-store JSON at
`/api/market-data/quote-quality` and escaped script-free HTML at `/quote-quality`.
The offline overview links to it. No server, Next route, startup integration or
provider transport was launched or enabled. Existing bar-qualityV1 code, fixtures
and exporter remain compatible and unchanged.

The actual API response feeds a new checked frontend fixture. `parseQuoteQuality`
validates exact fields/flags/counts, timestamp/delay arithmetic, unavailable data
redaction and consistent stale/delayed states. `createQuoteQualityController`
clears failed imports/render models and preserves both errors if refusal rendering
also fails. No prices, fetch, local storage or production mount are introduced.
These are consistency checks, not independent calendar/provider authentication or
native browser acceptance. Existing market and bar-quality controllers still pass.

## Exact validation

- Initial10 new Python cases passed.
- Broad existing market/provider/calendar/bar-quality/export/bootstrap group plus
  those10 cases:274 passed,0 failed/skipped,33.24s.
- Six added session/boundary cases joined a final focused16-case run:16 passed,
  0 failed/skipped. Distinct accepted Python cases across overlapping runs:280,
  not290. New cases16; existing264 regressions retained.
- Node185 passed,0 failed/skipped (19 new cases; prior166 retained).
- Cases cover actual API/HTML and producer-fixture equality; fresh/stale/delayed/
  missing/unobserved states; delayed+stale distinction; future receipt, bad age,
  unverified units, Boolean price, duplicate symbols, unknown authority and leaked
  unavailable data; premarket/regular/after-hours, early close, winter UTC midnight,
  closed-weekend missing evidence and unsupported calendar horizon.
- Targeted Ruff, frontend ESLint and Python compilation pass. Initial style-only
  findings were corrected; no product test failure occurred. Existing global lint
  debt is not waived or broadly rewritten. No full canonical suite claim.

Evidence: `logs/diagnostics/quote-quality-20261020`. Current actual API/HTML artifacts
use the final- prefix; earlier captured examples remain intact. New fixture
provenance records byte consistency with current reviewed source, not authenticity.
The approved roadmap updater verifies backup equality, exact managed readback and
byte-identical preservation outside the managed checkpoint. Prior28 intended file
hashes were verified before editing; old bar-quality fixture bytes remain pinned.

## Remaining gates and next task

Real U.S. equity/ETF collection still requires applicable automated-use/exchange/
session/display/storage permissions, actual wire-level budget enforcement, provider
schema/delay/adjustment acceptance and separately approved runtime admission. A key
or public endpoint is not entitlement proof. In-process synthetic dashboard/API
acceptance is separate from technically accepted main Atlas startup, which remains
blocked by existing controls. No service or port ownership claim is made here.

Next automatically selected task: immutable quote-quality export using the existing
reviewed bundle reader/research publisher. Require explicit caller-pinned snapshot
bytes and preserve the current bar-qualityV1 CLI unchanged. Validate source clock,
scope and refusal, publish JSON/HTML/provenance with exact readback, and retain
partial failures without false success. Demonstrate actual export→frontend parsing.
No new authorization framework, transport, default storage or production wiring.
Then return to independent Evidence Engine/AFI work across the full roadmap.

## Continued immutable quote export

The next task was implemented in the same execution. `quality_report.py` now
supports explicit `--quote-quality` mode and
`ATLAS_QUOTE_QUALITY_REQUEST_V1` with now, snapshot and caller-pinned snapshot SHA.
Snapshot mode/permissions/schema and exact source/report clock agreement are
mandatory. Only quote_rows are examined; provenance explicitly marks bar evidence
NOT_AUDITED. No repricing of old snapshot ages or cached missing evidence as current
is permitted. Existing raw references become price-free quality output.

JSON/HTML/provenance share the existing checked publisher and readback contract.
Later publication failures retain earlier immutable evidence without COMPLETE.
No multi-file transaction, source authenticity, crash recovery or namespace
power-loss guarantee is claimed. The old bar request remains the default and
refuses quote requests without the new flag. The shared output helper was factored
without changing old bar report/HTML/provenance bytes: the retained previous actual
export reproduced identical names and all three byte payloads in a fresh output
directory. Prior evidence was read only.

Nine new quote-export tests plus16 quote and10 bar-export cases passed35 focused.
Final combined regression289 passed,0 failed/skipped,33.50s. Node185 remains passed;
targeted lint/compile pass. New cases this turn25 Python/19 Node. Actual
API snapshot→pinned export→existing frontend consumer passed. No full canonical,
real runtime, native browser or provider/entitlement claim.

Next selected task: connect retained, receipt-vintage-filtered minute history to
the existing descriptive `analyze_market` research pipeline at an explicit decision
clock. Require a dated/provenanced previous-session close and refuse future/unseen
evidence; preserve existing scanner/C1–C4 and signal calculations. Keep bar-close
references distinct from executable quotes, unknown RVOL/history explicit, and
unobserved session volumes distinct from proven zero activity. Demonstrate actual
storage→analysis→frontend evidence without orders, forecasts fabricated from future
data or a new provider path. Continue independent Evidence Engine/AFI tasks after.
