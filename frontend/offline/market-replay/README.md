# Offline market replay consumer

`view.cjs` validates actual `ATLAS_MARKET_REPLAY_V1` exports from the isolated
`market_replay.create_replay_app` factory. `createController(display)` is an inert,
dependency-injected presentation adapter: failed replacement input clears prior
evidence before refusal. No network, storage, fetch loop, production route or
trading actions exist. No integration into Atlas startup/Next pages is authorized
or implied. The separate Python ASGI factory renders the working HTML dashboard.

The fixture in `tests/fixtures/market-replay-v1/api.json` is the actual deterministic
in-process API response retained in market-readiness diagnostics, not a provider
response or live-market evidence. Bar closes and quote references remain separate.
FRESH means fresh at the recorded replay clock, never current wall-clock freshness.
This consumer validates temporal/numeric/schema consistency, not independently
authenticated provider data, licensing, exchange calendars or consolidated coverage.
Its thresholds match the API factory's180-second bar and30-second quote defaults;
custom repository thresholds are not this response contract.

Run `node --test frontend/offline/market-replay/view.test.mjs` from the repository.
These are producer/consumer and presentation-state tests, not native browser visual
acceptance. Production remains NO-GO and all21 gate decisions remain unchanged.

`parseQuality` and `createQualityController` additionally consume the actual
`ATLAS_SESSION_QUALITY_V1` response. They check denied permissions, report/source
clocks, exchange-date windows, count/gap/delay arithmetic, chronological ordering
and explicitly unauthenticated recorded lifecycle scope. Reconciliation warnings
are never converted into authority; a failed replacement clears old windows.
Exchange-date formatting uses the platform's America/New_York timezone support;
this consumer does not independently authenticate the exchange holiday calendar,
provider timestamps or lifecycle chain. The Python producer does that bounded
calendar/chain-consistency validation. No network or production mount is added.

`parseQuoteQuality` and `createQuoteQualityController` consume the separate
`ATLAS_QUOTE_QUALITY_V1` companion. Missing/unobserved metadata stays null; vendor
delay units stay unverified. DELAYED and event staleness are independent. The
consumer refuses count/time/authority contradictions and raw price fields, clears
failed replacement/render models and preserves display errors. It does not verify
provider availability, actual exchange entitlements or executable quote quality.

`parseRetainedResearch` and `createResearchController` consume
`ATLAS_RETAINED_RESEARCH_V1`, produced from receipt-vintage-filtered retained bars
and an explicit available dated prior close. They preserve unknown RVOL/unobserved
session volumes, check derived-change arithmetic and refuse future/incomplete or
overstated evidence. This is synthetic descriptive analysis, not forecasting,
corporate-action reconciliation, source authentication or execution authority.
The existing scanner calculations and bar-start freshness policy are unchanged.

`verifyResearchReplay` and `createReplayController` accept the immutable replay
browser envelope produced by `research_replay_export`. SHA-256 verifies the exact
UTF-8 payload before parsing (no cross-language float re-encoding). Every planned
decision, including unavailable/refused decisions, remains visible in the total.
Denominator, clocks, nested denied permissions and counts are checked. Async
superseded loads cannot restore old evidence; failed rendering clears the model.
This checks payload consistency, not independent provider authenticity or source
reproduction. Use the Python self-contained verifier for input-to-output replay.
Neither consumer starts a server, fetches data, mounts the production dashboard,
or authorizes startup. Native browser visual acceptance is still outstanding.

`verifyResearchComparison` and `createComparisonController` accept the actual
paired-export browser envelope. Native WebCrypto verifies exact payload bytes;
strict pair totals/status matrix, metric difference arithmetic, null availability
and denied authority are checked before display. Missing baseline evidence cannot
be converted to a zero difference. Bad replacements/rendering and late loads clear
or preserve the correct model. Both original source archives remain necessary for
Python reproduction; hashes alone are not provider authentication. No forecast
winner or profitable strategy is inferred. This is an offline consumer, not a
production Next.js dashboard mount or native-browser visual acceptance.

`verifyVintageReplay` and `createVintageController` additionally consume explicit
`ATLAS_VINTAGE_REPLAY_BROWSER_V1` exports. The legacy consumer refuses this new
envelope. Receipt counts split first events, value corrections and unchanged
confirmations. Prefix heads and integer/string decision-audit commitments are
checked separately from selected research identities; future receipts cannot
rewrite an earlier decision. Native WebCrypto verifies exact payload bytes and
portable per-decision audit JSON. Actual CLI and in-process API fixtures are
producer-tested. The source archive must still be reproduced by Python; receipt
times are caller declarations, not authenticated provider arrivals. There is no
production route, provider connection, startup permission or runtime sandbox.

`createController.loadResponse(status, body)` binds the explicit transport status
to either the existing successful replay or `ATLAS_MARKET_DATA_REFUSAL_V1`.
Refusals require empty quote/bar arrays, denied authority and matching reason/code.
They clear old prices and leave `current()` null. Invalid, contradictory or
malformed replacements also clear the model and preserve rendering errors.
`parseMarketRefusal` accepts the actual in-process ASGI failure fixture; it does
not infer provider health, permissions or automatic retry authority. No HTTP
client, polling loop or production dashboard mount is added.


## Portable market evidence viewer

Build an explicit new self-contained HTML file with the installed Node runtime:

`node frontend/offline/market-replay/build.mjs <new-output.html>`

Open that generated file locally. Atlas, Next.js and Docker are not needed or
started. Select one local JSON export (maximum1MB): the API replay snapshot,
quote-quality report, retained descriptive research, immutable replay/comparison
browser companion, or sanitized market-data refusal. The page reuses the existing
validators, never fetches, never stores data and never executes imported HTML.
Unknown schemas, authority claims and failed replacements clear prior evidence.
FRESH refers only to the recorded report clock. Production remains NO-GO.

File reads and verification can finish after Clear or replacement; revision guards
prevent late results restoring old evidence. They do not cancel uninterruptible OS
file reads. If DOM cleanup itself fails, the public loader rejects explicitly;
close the file rather than treating the screen as accepted. Opening evidence does
not verify provider rights, source authenticity, original archive reproduction,
complete coverage, forecasting skill or trading permissions.

The builder exclusively creates a new `.html`, flushes, verifies bytes through its
open descriptor and checks the final file identity. Existing or partial outputs
are never overwritten or deleted. A failure preserves evidence; select a new path
after investigating it. This is not backup, power-loss certification, a protected
runtime release or exclusion of privileged concurrent filesystem modification.
No desktop shortcut, startup lock or production page is changed.

The file-only viewer requires a modern browser with File.text, TextEncoder and
WebCrypto for hashed companions. DOM/VM and native cryptographic/filesystem tests
are recorded; native browser visual/CSP enforcement acceptance is still outstanding.

## Export-to-import map

These are offline Python functions, not authorization to run a server or provider.
Use only caller-supplied fixtures and isolated stores under the existing contracts.

| Import | Existing producer |
|---|---|
| `ATLAS_MARKET_REPLAY_V1` | `market_replay.create_replay_app`, in-process `/api/market-data` response |
| `ATLAS_QUOTE_QUALITY_V1` | `quote_quality.quote_quality` |
| `ATLAS_SESSION_QUALITY_V1` | `session_quality.session_quality` |
| `ATLAS_RETAINED_RESEARCH_V1` | `retained_research.retained_research` |
| `ATLAS_DESCRIPTIVE_REPLAY_BROWSER_V1` | `research_replay.browser_replay` |
| `ATLAS_VINTAGE_REPLAY_BROWSER_V1` | `bar_vintages.browser_vintages` |

Select the entire hashed browser envelope, not its inner `report_json` string.
Original archives remain necessary for independent source reproduction. Raw
provider payloads, SQLite databases and credentials are not supported imports.
The generated page also lists comparison and sanitized-refusal schemas. Invalid
session labels are refused using the same bounded 2026–2028 calendar; no silent
reclassification or coverage inference occurs. Calendar updates must be explicit.

The market report now includes explicit symbol selection for bars/quote references.
It defaults to all supplied symbols and keeps the full-report freshness summary
unchanged. Missing symbols remain selectable. Selection never changes loaded
source evidence or report counts, and resets on replacement, refusal or clear.
Other report families retain their own existing scopes. This is local display
functionality, not an authority or provider-source verification boundary.

New builds also show SHA-256 and UTF-8 byte length of the decoded imported text.
This is not an original-file byte attestation or authenticated provider identity;
File.text decoding may differ from original bytes. Whitespace changes the digest.
The identity clears on refusal/replacement/clear and cannot be restored by late
loads. New identity-enabled pages require WebCrypto; no fallback hash is invented.
