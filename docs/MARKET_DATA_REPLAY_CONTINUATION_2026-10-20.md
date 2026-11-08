# Market-data readiness: integrated offline replay

Production NO-GO. All 21 release decisions unchanged. No runtime or Docker census,
provider request, service start, trading or notification occurred. Final authorized
configuration inspection recorded recognized key-presence Booleans only; no values
were disclosed, retained or used for authentication.

## Working increment

`scripts/observation_runtime/market_replay.py` provides an inert, separate ASGI
application factory. Explicit Yahoo-chart-shaped JSON fixtures flow through strict
USD minute OHLCV normalization, the existing bounded 2026–2028 exchange calendar,
SQLite transaction storage, restarted repository, read-only JSON response and
server-rendered HTML dashboard. Equity and ETF classes are explicit caller inputs,
not verified security-master membership. No default database, network client,
environment read, scheduler, trading dependency, startup integration or launch
command is provided. This is usable in-process replay functionality, not live data.

Bar event times are minute starts; incomplete bars are refused. Freshness uses
completed-bar end with an explicit bounded threshold, current session/date and
current caller clock. Receipt time never substitutes for event time. Invalid,
future, null, duplicate, conflicting OHLC and unsupported currency/interval data
are refused before writes. Repeated equivalent bars retain original provenance;
conflicting repeats fail and roll back the transaction. SQLite commit exceptions
propagate. Retained content checksums detect accidental changes, including receipt
metadata; they do not establish external authenticity, tail-loss detection,
malicious database protection or hardware durability. Caller-owned SQLite storage
is for disposable replay only, not an approved production persistence backend.

The dashboard explicitly labels synthetic replay and completed minute-bar closes,
never executable quotes. Stale prices are null, with separately labelled retained
reference close in JSON. Missing symbols are UNAVAILABLE. HTML escapes values,
has no scripts/external resources, restrictive CSP/no-store, and only GET routes.
There is no implied continuous coverage or gap imputation. No provider corrections,
splits/adjustments, consolidated tape identity or real-time entitlement is inferred.

## Existing path findings and shortest safe path

The main backend lifespan calls the unconditional production startup lock. It is
not authorized to start. The investment board endpoint performs ladder, PAPER and
forward-evidence state work and external quote scheduling; it is not an
observation-only read endpoint. Source configuration defaults include PAPER and
Discord-related enabled flags; independent central denials remain required. The
Next frontend has dev/build/start scripts, but that alone does not establish a
working authorized backend. No production configuration values were printed or
changed. The separate observation entry point reports offline capabilities only.

Existing Yahoo/yfinance and public Robinhood adapters are implementation evidence,
not permission evidence. Existing retained provider review has no established
automated Yahoo data entitlement, classic/RHJ endpoint-wide applicable rights or
account-wide wire budget. No new legal/provider claim is made offline. No API key,
subscription, feed plan, exchange entitlement or storage/display license is assumed.
Existing dispatcher limits logical calls; yfinance internal requests and other
consumers need actual aggregate transport accounting. Blocking worker drain and
runtime startup/backup/restore gates remain unresolved.

Premarket 04:00–09:30 ET, regular calendar open/close (including early close), and
after-hours until20:00 ET are implemented and fixture-tested. Holidays/weekends,
DST and unsupported calendar horizon fail closed. These windows do not establish
any provider's actual coverage, delay, exchange scope or opening/closing auction
semantics. The existing bounded calendar requires updates for unscheduled closures.

Shortest safe live-session path: select a provider and obtain applicable automated
access, exchange/feed coverage, pre/post-session and display/storage permission;
pin its actual schema/delay/adjustment semantics and aggregate wire budget; implement
and fixture-test an explicitly authorized read-only transport under a separate
immutable runtime/state boundary; obtain bounded startup/live-data acceptance
authorization with existing admission, persistence and lifecycle controls intact.
Do not bypass the startup lock or reuse the mutating investment endpoint. Current
local replay: tested. Main Atlas dashboard startup: BLOCKED. Authorized live data:
BLOCKED. Production readiness: NO-GO.

## Validation and preserved failures

36 new integration/failure cases; combined market/calendar/research/provider suite
95 passed,0 failed/skipped with explicit pytest_asyncio plugin. Covers all three
sessions, early close, DST, holiday/weekend refusal, restart and duplicate behavior,
stale/missing display, transactional rollback and commit failure. API and actual HTML
are exercised in-process via ASGITransport without a server/socket connection.
This is not a native browser visual or real server startup acceptance.

An initial regression run had60 pass/17 fail because plugin autoload was disabled
and the async plugin was not explicitly loaded; the corrected run passed77. Native
Windows execution was required because sandbox asyncio local socketpair setup
stalled; trace and interrupted logs remain. The guard blocks external connections
and production data/.env reads. Targeted Ruff and Python compilation pass. Git
whitespace check passes with inherited line-ending warnings. No PowerShell source
changed. No full application suite or real operational acceptance is claimed.

## Continued implementation after first checkpoint

Coverage now reports missing minutes between the first and last observed bar in
the latest session/date, with a bounded10,000-row read and explicit WINDOW_LIMIT.
This does not establish completeness since session open. Readback binds row keys
to content. Observations before recorded receipt time are withheld, including
reference fields and coverage; future receipt records cannot contribute to coverage.

Timestamped quoteResponse-shaped fixtures now have a separate persisted table,
API quote_rows and dashboard section with event time/source/delay. The current
session's preMarket/regularMarket/postMarket fields are mandatory; regular close
does not substitute for a missing pre/post quote. Missing delay metadata refuses;
nonzero reported delay always suppresses a current price. Delay units remain
explicitly unverified fixture metadata rather than a false vendor seconds claim.
Out-of-order older events cannot override a newer retained event. Quote references
are not executable bid/ask prices. This exercises three session quote paths, not
actual vendor schema certification, entitlement or wire behavior.

Forecast run_bundle now supports opt-in continuation_output_prefix and CLI
--continuation-output-prefix in bundle mode only. Before any append, the explicit
relative mapping must identify the exact reviewed output directory. Export retains
original forecast/data/source references and existing history, adds exact new
outcome references with their actual dataset/source, binds verified updated heads,
and sets every next append to null. Full revalidation and publication/readback
precede successful requested-export acknowledgement. No multi-file transaction,
rollback witness, recovery permission or automatic append/retry is introduced.
Failure retains earlier immutable outputs. Default bundle results are unchanged.

6 new continuation tests passed with12 existing bridge cases (18 combined), then
the full AFI suite552 passed,0 failures/skips. Existing Node131 passed,0 failures/
skips. These are separate suites, not additional market cases. Targeted Ruff and
compilation pass. Sample actual ASGI JSON/HTML are retained in diagnostics. Roadmap
checkpoint verifies backup equality, exact readback and outside-section byte
preservation; canonical21 decisions and startup-lock hashes remain unchanged.

The historical API now returns bounded retained bars in ascending event order,
respects observation receipt vintage, restricts symbols to the explicit replay
universe, validates checksums and labels incomplete retained history without full
session coverage claims. JSON responses are no-store. Four additional cases pass,
including exact current ASGI response equality with the frontend's actual fixture.

The separate frontend consumer validates the actual ASGI export, exact schema and
row fields, authority denials, OHLCV/quote distinction, event/receipt ages, provider
delay and bounded gap arithmetic. Invalid replacement input clears prior display
and in-memory evidence.13 new Node cases plus131 existing cases pass144 total.
No Next route, fetch loop or native browser claim is introduced. ESM test imports
resolve5 initial CommonJS lint findings without waiving rules; targeted ESLint
passes from the frontend configuration root. An earlier root-directory ESLint
configuration lookup failure is retained.

Presence-only inspection of backend/.env and root .env found no nonempty literals
under the six explicitly checked licensed-provider credential keys. This does not
exclude other configuration or process environment, validate credentials, prove
that a subscription is absent, or establish entitlements. Yahoo/Robinhood public
adapters remain the source-reviewed equity paths; their applicable automated-use
and display/storage rights and actual HTTP fan-out budgets are unresolved.

Evidence: `logs/diagnostics/market-readiness-20261020`. Next priority: bounded
PaperBook snapshot/ledger acknowledgement adjudication with fault reproduction,
leaving multi-file/restart limitations explicit. Do not repeat the already
implemented pending-limit/prediction corrections. Live-provider permission remains
an external gate, not a reason to stop other authorized offline development. Native Goal is preserved, with its last
reported status BLOCKED; no duplicate Goal or external continuation mechanism was
created. Continue within the resumed user-authorized turn.
