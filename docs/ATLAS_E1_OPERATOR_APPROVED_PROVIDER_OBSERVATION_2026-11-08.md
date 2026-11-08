# Atlas E1 first operator-approved data-only provider verification — 2026-11-08

**Status: BOUNDED ACTUAL PROVIDER CONNECTIONS COMPLETED; PARTIAL CONNECTIVITY VERIFIED; FINANCIAL SOURCE / E1 ACCEPTANCE STILL NO-GO.** This is factual read-only commissioning evidence, not operational PAPER account authority, not a successful two-lane PAPER session, and not permission for real orders.

## Permission and scope

- Operator said "I approve everything" in direct response to an offer to perform the outstanding **read-only Alpaca IEX and Hyperliquid source checks**. This execution interprets permission narrowly for bounded, data-only connectivity and durable public request-budget accounting; it does not override a technical refusal, permit wallet/account signing, turn on live orders, authorize native financial inception or repoint desktop shortcuts.
- Git checkpoint at start: `2fdf23bd` on `chatgpt/atlas-rebuild-v1`; installed selected V4 `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`, selector revision 9. No installed code was replaced.
- Date: **Sunday 2026-11-08**, outside the regular U.S. equity trading session; always distinguish connection/authentication from actual executable market evidence.

## Actual Alpaca IEX provider evidence (read-only)

- Ran the existing `scripts.observation_runtime.personal_clock_iex_probe` with explicit symbols `MSFT`, 10 seconds, and configured trusted peers `time.cloudflare.com,0x8 time.google.com,0x8`.
- Output: `authenticated=true`, `subscribed=true`, `connection_closed=true`, genuine Windows clock verified, **452 ms** uncertainty; `fresh_validated_quote_count=0`, `market_session_verified=false`, `native_publication_supplied=false`, `forward_research_observed=false`, `forward_paper_session_qualified=false`, and both financial and live order authorizations false. Exit **0**.
- Source permission/connection for this IEX symbol is supported; executable stock price acceptance, breadth of the Robinhood-eligible stock universe, forward-source QD ranking and a full PAPER session are **not** supported by this weekend observation.
- Provider documentation: https://docs.alpaca.markets/us/docs/market-data-faq describes free live **IEX single-exchange** coverage, not full SIP/all-market free quotes; https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api records free Basic's 30-symbol websocket limit. Do not infer full real-time coverage of every eligible Robinhood security from a successful MSFT subscription.

## Actual Hyperliquid public-data evidence and durable capacity

- The existing `HyperliquidAdapter` was used with only documented `POST https://api.hyperliquid.xyz/info` public metadata/books/funding history requests. `connect_http_only`, **no private account**, no wallet signing, no WebSocket and no exchange order endpoints.
- Dedicated create-only, durable request budget: `logs/diagnostics/atlas-e1-hl-public-20261108-r9-budget.sqlite`, strict seven logical attempts. Actual ledger recorded **7 attempted, 0 remaining**. No reset, adoption, over-budget retry or second budget was created.
- First BTC metadata+book observation consumed **2** attempts; native clock uncertainty **489 ms**. Strict public-book validator refused a `ValueError`. No raw response or exact reason was retained from this probe; do **not** assert the cause was latency, exchange error or a specific parser bug.
- An exact-shape diagnostic consumed **2** further attempts (native clock **459 ms**): returned 235 metadata instrument rows and 235 asset contexts, a public BTC L2 book with 20 bids/20 asks, fields `px/sz/n`, **31 ms** observed book timestamp age, and a **passing** `_paper_execution_observation` strict parser. This proves one bounded BTC public market-book observation; not persistent quality, perpetual funding settlement or account-specific fees.
- Final bounded checks consumed the final **3** attempts (native clock **467 ms**): ETH strict book validation refused `ValueError`; BTC hourly funding-history validation refused `ValueError`. Neither failure was bypassed. SOL public book never independently validated within the seven-request budget.
- Host-only evidence files (ignored, no public credentials):
  - `logs/diagnostics/atlas-e1-hl-public-20261108-r9-result.json`; SHA-256 `f676aef978dd70a946e3216b4d0305d719fd5d9914bbd4adf51a8bdaef18ccb0`.
  - `logs/diagnostics/atlas-e1-hl-public-20261108-r9-contract-diagnostic.json`; SHA-256 `f935aa8025b4e16e64a3220467e150fc7c30004de754dc296222c95683bb4e82`.
  - `logs/diagnostics/atlas-e1-hl-public-20261108-r9-final.json`; SHA-256 `8eff60ef2768f9d09f7d653cf0da353391ae170c0a3d3e6ac3a1f7b0f3015301`.
- Official API contract https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint documents maximum 20 price levels per book side. All exchange data here remains public-market **observation**, not executable PAPER quote/mark/fee/funding source acceptance.

## Important simulated fee discrepancy

- Current V4 Hyperliquid *unaccepted draft* `docs/ATLAS_TWO_ACCOUNT_V4_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json` has proposed `maker_bps=1` and `taker_bps=2` with `fee_schedule_id=PENDING_E1_VERIFIED_FEE_SCHEDULE`. Those placeholders are **not verified**.
- Hyperliquid's publicly documented **perpetuals base tier** lists **0.015% maker = 1.5 bps** and **0.045% taker = 4.5 bps** before any account-specific volume, staking, referral and other discounts: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees . The current proposal would understate fees by **0.5 bps maker and 2.5 bps taker per side** relative to that publicly documented base.
- Illustration: for a $100 entry and $100 exit both charged at taker rates, current 2-bps proposal computes $0.04 total versus $0.09 at the published 4.5-bps base, **$0.05 difference**, ignoring spreads/slippage/funding/margin and discounts. Do not take simulation P&L at face value until a reviewed cost schedule is selected and both account manifest/policy/report digests are recomputed.
- Public fees are a conservative reference, **not verification of the user's private account tier**. Do not access a private wallet or trade account to fetch a discount, and do not silently rewrite already pinned V4 enrollment drafts.

## Offline tests, open work, and immutable safety status

- Existing Alpaca IEX, clock-qualified IEX, Hyperliquid public-book parser/storage, durable budget and gate acceptance tests: **121 passed, 0 failed**, one preexisting Starlette/httpx test-client deprecation warning. These tests are **not** a live E1 gate pass.
- **E1 not yet accepted.** Missing: current weekday accepted IEX executable quote linked to enrolled QD source; broader eligible-stock source coverage/rights under free plans; repeated stable strict BTC/ETH/SOL Hyperliquid book observations; accepted continuous funding settlement and fee schedule; actual finance writer/process custody; bounded native simulated account inception. Existing provider-budget ledger is **exhausted** and must not be circumvented by another ledger or a blind retry.
- **Next actions:** make an explicit decision on documented conservative HL PAPER fees / separate tier proof and resolve required funding settlement evidence; perform new distinctly bounded public checks only after a reviewed request budget and clear cause (not repeated attempts without new evidence). The first full IEX executable-price acceptance must occur during an eligible market session. Then finish exact V4 account writer/acceptance/inception and approved final Start/Stop/flatten/soak.
- Formal nine-gate acceptance stays **0/9**; no financial positions were touched, no PAPER Start/Stop performed, no live orders, no desktop shortcuts altered, no Project Genesis access, no automatic Windows startup or VPS.
