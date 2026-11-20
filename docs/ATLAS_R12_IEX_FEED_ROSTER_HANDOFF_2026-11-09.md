# Selected r12 Alpaca IEX roster-to-feed integration — November 9, 2026

**SOURCE-ONLY / READ-ONLY TEST MILESTONE. Financial PAPER remains NO-GO, 0/9 operating gates accepted. No new native release was installed or selected.**

## What was implemented

New `scripts/observation_runtime/atlas_r12_iex_rotation_bridge.py` bridges the existing 13,487-symbol Alpaca research catalog and the 30-symbol research rotation plan to the **existing production `IEXFeed.request_roster()` data-only transport API**. The bridge does not open provider connections, load private credentials, publish a forward scanner record, advance a research cursor, or initialize a PAPER trading account.

- Uses the exact catalog schema, canonical content digest, research-only permissions and deterministic rotation planner. Maximum 30 symbols in one subscription request.
- Requires an `IEXFeed` constructed with a callable position-symbol reader; never installs or replaces one. The reader's exact current pinned list must match any supplied monitored symbols and remain stable across the handoff. This is a **source-code ownership guard**, not independent account custody authority. Until real native financial ownership is accepted, its result explicitly states `position_owner_independently_accepted=false`.
- Constructs the existing `QD_IEX_ROSTER_V1` with the pinned symbols first and the remaining research rotation. It invokes `IEXFeed.request_roster()` rather than introducing a second subscription protocol.
- On a changed roster, existing `IEXFeed` invalidates its previous quote cache, transitions to `DISCONNECTED`, and increments roster revision; it cannot claim current/fresh prices until a later separately authorized socket connects and receives new authentication and exact subscription acknowledgments. If monitored symbols change during the handoff, the adapter refuses and disconnects.
- During an active feed session, existing `IEXFeed` refuses another rotation within 30 seconds; the adapter propagates that refusal and retains the earlier roster without forcing a reconnect.
- The result remains `OFFLINE_DATA_ONLY_ROSTER_HANDOFF_NOT_CONNECTED`, with **all** provider authentication, fresh quote, entitlement, independent position authority, financial account, source publication, paper execution, live trading, and startup flags false. The CLI `--inspect` demonstrates only an in-memory feed with a synthetic pin reader, and returns deliberate NO-GO exit code 2.

## Verification

New `tests/test_atlas_r12_iex_rotation_bridge.py` calls the **real** `IEXFeed` in memory with synthetic source events and a local fake clock. It checks an authenticated synthetic `S000` quote becomes unavailable after rotating a pinned roster, independent rejection of unauthorized or changed position ownership, complete 67-symbol coverage without premature duplicates, no missing/invalid catalog acceptance, and the real active-session 30-second rotation limiter.

Combined adapter + catalog/rotation + existing Alpaca IEX/feed/probe and source-admission regression: **113 passed, 0 failed**. No tests authenticated to Alpaca, published native source data, or submitted any order. The actual installed selector `D:\AtlasRuntime\selection\r0012.json` remained SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`.

## Next financial prerequisites

This completes a source-only **data-subscription safety adapter**, not the source acceptance gate. A separately scoped one-time authenticated data-only Alpaca IEX probe during regular market hours must demonstrate actual quote delivery and entitlement. Then Atlas needs an independently admitted native forward publisher with issuer and custody ACK, trustworthy continuous financial clock/storage, QD/HL isolated PAPER account creation, real Stop/flatten with durable financial reconciliation, read-only dashboard and Discord events, and supervised operational reliability.

**The selected r12 image remains frozen**; these new workspace files are not installed into that selected release. No Project Genesis, desktop shortcut, Windows Time, paid VPS, private account, simulated/live trade or GitHub push was touched.
