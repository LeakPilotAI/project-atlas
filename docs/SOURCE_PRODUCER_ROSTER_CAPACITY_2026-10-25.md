# Authenticated source producers, native roster and bounded lifecycle acceptance

Date: 2026-10-25. Base: d817e55b6d47cb1929e7a3860c9f0957ac1d500e.
Scope: source and disposable native acceptance only. No protected account, provider connection, credential, operational inception or startup was used. All 21 decisions and seven phases remain unchanged. PAPER startup NO; production NO-GO.

## Implemented source engineering

- `backend/app/services/paper_source_publication.py`: authenticated current-source publication ports for the actual Quality Dips candidate adapter/scanner publication and actual Hyperliquid adapter caches. Exact schemas, immutable source revisions, independently injected current-head/publication authentication, durable archive CAS/ACK, freshness, clock continuity, changing-cache and rollback refusal. No default issuer, archive enrollment or clock authority.
- `backend/app/services/quality_dip_scanner.py`: opt-in publication of the original scanner rows and timestamp; existing default behavior preserved. No operational registration or mutating research GET integration.
- `backend/app/adapters/hyperliquid.py`: passive versioned book/metadata/candle/ticker/funding/trade caches; current raw payload reparsing. Optional explicitly authenticated transport reuses existing public WebSocket pump and request gate for BTC/ETH/SOL trade messages. Default subscription behavior retained. Disconnect invalidates trade continuity. Tests mock transport; no live provider requests executed.
- `backend/app/services/paper_market_observers.py`: optional actual source-bound observer, refusing changed cache/current evidence rather than manufacturing a counterparty lane.
- Executable maker evidence binds the original admitted book/metadata, visible queue, original source revision/digest, exact opposite-aggressor public trade identities, quantities and timestamps plus an independently accepted complete-window/queue witness. A resting order, mark touch or public print alone is never proof of a fill. Funding requires authenticated historical settlement oracle evidence; current oracle is not substituted.

Provider schema inspection used public documentation only: [WebSocket subscriptions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions), [notation](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/notation). Trade IDs are not assumed contiguous; coin/time/tid identify observed prints. Public data does not authenticate a complete private maker queue or settlement history by itself.

## Writer/resource/process contract

`backend/app/services/unified_writer_roster.py` requires 15 exact roles: QD_DECISION, QD_SOURCE, QD_PROJECTION, QD_REPORT, QD_COORDINATION, QD_RANKING_PUBLICATION, PERP_SOURCE, PERP_PROJECTION, PERP_REPORT, PERP_ORDERS, PERP_FUNDING, PERP_MARK, PERP_MARKET_PUBLICATION, GLOBAL_CUSTODY, SESSION_RESERVATION.

Eight explicit exclusion receipts are required: legacy investment, prediction, manual perp, journal, research mutation, inception publisher, recovery writer, and legacy scanner financial mirror. Exact native resource IDs, PID/creation/image, account/session/component equality, fresh complete observations, no unknown writers/operations, zero active operations and stable final drain are checked. It produces the existing owned-close roster contract; no process enumeration or termination was added.

The confined native test observes actual test-owned resources via Windows file handles and actual self-process identity. Its acceptance/exclusion receipts are synthetic. It does not prove operational exclusion or independently accept the real roster. Same-account malicious code remains outside this coordination guarantee.

## Capacity and restart

Existing native financial, report and control capacities remain bounded at 128. New existing-only authenticated capacity reads never initialize, reset, repair or acquire a financial writer latch. Before reservation, global and financial headroom must cover acknowledgement, remaining position settlement/exits and final shutdown; resting-order custody reserves pending-fill acknowledgement and cancellation capacity. Report headroom triggers the existing graceful Stop before normal polling consumes required final-report capacity. Missing headroom refuses before financial effects. Incomplete cuts, UNKNOWN and unfinalized sessions retain existing restart refusal.

This implements bounded safe refusal/Stop, NOT rollover or indefinite 24/7 capacity. A seven-day trial needs an accepted workload/capacity bound or separately reviewed immutable continuation design. No protected state is reset or adopted. Subprocess tests demonstrate process-crash recovery, not physical power-loss durability.

## Validation actually executed

Final relevant selections (overlap; do not sum as distinct tests):

| Selection | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Broad financial/perp/discovery/FS1-FS3/startup/archive, 28 files | 622 | 0 | 1 |
| Actual QD source/V5/native/Stop/runtime/HTTP, 10 files | 155 | 0 | 0 |
| New source/roster/native crash/capacity plus existing actual two-lane/order/HTTP/owned-close, 11 files | 89 | 0 | 0 |
| Final capacity and source-bound native follow-up | 9 | 0 | 0 |
| Operational QD codec/runtime compatibility | 32 | 0 | 0 |
| Operational perp codec compatibility, correctly confined root | 30 | 0 | 0 |
| Original selected-account JavaScript frontend | 42 | 0 | 0 |

The new source/roster/native selection contains 54 new cases: 30 source publication, 10 roster, 2 actual source-bound native two-lane, 4 abrupt publication crashes, 1 actual native resource roster and 7 capacity cases. Existing cases overlap between selections; no grand distinct-count claim is made. The one skipped true-symlink test remains NOT EXECUTED because Windows privilege 1314 is unavailable.

Source publication subprocesses exit abruptly before publication, after immutable record, after pin and after ACK. Unpinned or unacknowledged tails refuse; acknowledged evidence is readable; native financial effects are unchanged and never blindly replayed. Existing native order/global crash/race and owned-child tests also pass in the 89-case selection.

Retained failures include initial fixture setup defects, a mocked WebSocket dict/text mismatch, a restricted Windows asyncio initialization stall, a first GUI automation visibility failure, and a combined codec invocation using the wrong confined basetemp for perp (32 passed/30 setup errors). The perp suite then passed 30/0/0 under its required separate root; no confinement assertion was weakened. A lint utility encoding failure was fixed by explicit UTF-8, and one new lint branch warning was corrected. Diagnostic roots and original failure evidence remain local and excluded from Git.

New Python modules/tests pass Ruff; changed legacy files have no additional Ruff findings against HEAD (preexisting findings retained). Changed/new Python AST compilation, original startup/UI/Control Center byte checks, PowerShell parsing, static PAPER release audit and Git whitespace checks pass. No live-money routing added.

## Genuine Windows GUI and browser evidence

The automation tools could not see the first test-owned Windows form although Windows reported it responding. That initial automated GUI attempt is NOT EXECUTED, not PASS. Exact owned-window graceful cleanup succeeded; no global/name/port termination was used.

After explicit user agreement, a fresh original Control Center form was started with disposable synthetic account dependencies only. The user clicked the existing graceful Stop, then Close. The actual loopback Stop response reached FINISHED / FLATTENED / FLAT, both native financial/report cuts and global FINAL reconciled, and the exact form exited 0. This is a genuine human-assisted original WinForms acceptance, not an automated click or operational ownership approval. Start/Gaming/operational workers were not invoked.

A separate genuine in-app browser opened the original `quality_dips.html?mode=selected-paper` through the dedicated loopback read host. It displayed independently denominated USD/USDC accounts and exact remaining quantities. Synthetic fixture dates were ahead of the real clock, so the original UI honestly showed STALE/CLOCK_UNCERTAIN. Native/source file hashes were identical before and after browser reads. The fixture then reached acknowledged flat/drained shutdown in both lanes and closed its listener. A screenshot was shown in the conversation; no saved screenshot or complete browser-network trace is claimed.

Private evidence stays under the existing confined `logs/diagnostics/perp-order-custody-*` root: `source-final.xml`, source/crash fixtures, the GUI `gui-stop-result.json`/`acceptance-result.json`, and browser `acceptance-result.json`. Machine identities, pins, wrapper tokens, raw source receipts, screenshots containing financial fixtures and logs are not published.

## Exact remaining acceptance and next action

- B1 BLOCKED: independent acceptance of both new account/epoch scopes, separate hypothetical 1,000 USD and 1,000 USDC, policies/cost assumptions and legacy exclusions. Local arithmetic does not authenticate undisclosed history.
- C1 BLOCKED: enroll and independently verify the actual 15-role resource/process roster and all eight exclusions, complete live reservations/drain, retained-child ownership and failure handling. The new verifier is source engineering, not a real ownership receipt.
- D1 BLOCKED: accepted local profile issuer/session/clock, durable current-head/source publication custody, native enrolled resources, backup/recovery and explicit same-user/D:-only rollback limitations. Test `DurableArchive` is not an installed operational protected archive or trust root.
- E1 BLOCKED: permitted provider/entitlement and authenticated IEX/session/calendar/halts evidence; Hyperliquid current executable source, continuity/queue model and historical settlement oracle; accepted capacity policy; installation/inception/session-release authorization and supervised recovery acceptance.

Next bounded decision: accept a maximum session workload/capacity envelope or authorize a reviewed immutable continuation protocol, and provide separately accepted source-publication custody/issuer/clock/transport and actual roster evidence. Then perform explicitly authorized dependency installation/account inception and read-only acceptance before autonomous trading. No automatic seven-day trial starts from these tests. First run must demonstrate both healthy sources, account-specific risk, acknowledged reports, safe incomplete Stop, restart refusal and owned closure, then obtain explicit seven-day trial release. Extended validation follows; no live-money phase exists.

All independently eligible changes in this bounded source/fixture increment are complete. The overall task is BLOCKED, not VERIFIED. BLOCKED_WAIT records missing real authority/evidence and accepted capacity scope rather than recycling completed source tests. Do not rerun completed accounting, codecs, Stop or these source bindings as a new milestone.
