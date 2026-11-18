# Atlas R24 — Alpaca IEX personal research rights evidence and target-symbol market-session follow-up

**November 18, 2026 | authorized Windows desktop MADDOG | selected immutable R24 | financial PAPER OFF / live-money OFF**

## Public provider-specific rights evidence materially improved

Alpaca's *Trading API Basic* is documented as free real-time **IEX-only** equities; the Basic WebSocket limit is **30 simultaneous symbols** and its market-data FAQ distinguishes IEX single-exchange observations from broader SIP/NBBO coverage:
- <https://docs.alpaca.markets/us/docs/about-market-data-api>
- <https://docs.alpaca.markets/us/docs/market-data-faq>
- <https://docs.alpaca.markets/us/docs/paper-trading>

A **dated Alpaca staff reply, October 15, 2026**, to a directly comparable noncommercial individual API-research question, broadly confirmed use of legitimately available Basic data for personal internal **local retention, replay, backtesting and derived research**. Actual original discussion, including specific limits in the user's question: <https://forum.alpaca.markets/t/sip-data-collection/19863>. That is useful direct provider-staff explanatory evidence beyond an outside commentator, but it is **not an individually executed account agreement, paid market-data entitlement, financial E1 issuer, or right to re-distribute** data. An Alpaca support FAQ expressly says developer platforms cannot redistribute Alpaca API data: <https://alpaca.markets/support/redistribute-alpaca-api>. Atlas must not publish third-party raw quote data into Discord or a remote service under an unsupported redistribution assumption; personal derived alerts also need the applicable terms reviewed.

Existing prior authenticated **one-time** selected R24 native IEX quote observation was properly pinned and consumed: SHA256 `4b34ef7b075c319b6c0e2061052375d508c87ff741e44475858de62094a37257`. It established actual source-only SPY IEX quotes (237 received, 217 admitted, 20 rejected, 198 distinct fresh callbacks), **zero received** quote frames for MSFT and AVGO. The three requested subscriptions were acknowledged; zero MSFT/AVGO frames do not distinguish limited exchange activity, session timing, account entitlement or a provider issue. Never reinterpret absent messages as actual recent prices, executable NBBO, or an entitlement denial. This result's original local consent and one-time diagnostic journal were NOT modified or replayed.

## One distinct, nonfinancial, actual-IEX market-hours coverage check prepared

Original selected R24 code-only source `5c3970b7150fd448f5f3c5a25f424687c704a2f9`, original selector SHA256 `afe5ae7e1e83088e14584cf942f51ba01792c375a5cc50130d1ce48c2c0747ad`. Uses the **unchanged actual installed native** `scripts/observation_runtime/alpaca_iex_probe.py` SHA256 `b050c52a4872699d026b6108d9691853a55988af18d19d45a6d0d8c3c4237fbc`, and unchanged native quote-only `backend/app/investment/alpaca_iex.py` SHA256 `af115f0281fae29e9e7d8f5e01ebcf3ef72fa2c46030fee593a737ba6927af79`. No release upgrade or copy of private credentials into the immutable installed R24 release.

The **NEW original data-only operator scope** is:
`APPROVE_ONE_ATLAS_R24_IEX_MSFT_AVGO_SPY_REGULAR_SESSION_60S_DATA_ONLY_NO_FINANCIAL_START`

The scoped, untracked diagnostic launcher is:
`D:\Work\Project Atlas\logs\diagnostics\atlas-r24-iex-msft-avgo-followup-20261118-r01\Approve-R24-IEX-MSFT-AVGO-Regular-Session-Data-Only.cmd`

Launcher SHA256 `9aae4b9631a15fe41dace064e7a0a3850ad9fb98026d84d1609fcee2236e538b`; bounded source-only wrapper `one_time_r24_iex_msft_avgo_regular_only.py` SHA256 `85804f5c03f23ca27917b7cbf1f391ed7e53c0796e184dfadb62f999c6e6f3c0`. It is a D-only one-shot local manual data-only diagnostics tool, **not installed operational R24 finance code, not a desktop shortcut, and not an automation**.

**Specific restrictions:**
- No automatic start, no automatic retry/reconnect, **one IEX data-only WebSocket**, exactly **MSFT, AVGO and SPY** requested, maximum **60 seconds of quote observation**. No broker/account endpoints, trade APIs, paper account, wallet or live order.
- Date/time restriction in the executable **before** operator approval or credential reading: **Wednesday November 18, 2026, 14:33–20:50 UTC** (8:33 a.m.–2:50 p.m. CST). Premarket, after close or a later calendar date must **REFUSE WITHOUT CONSUMING** the new one-use scope.
- Requires genuine separate visible local typed exact scope **after** the specific market-hour guard. Only then reads existing `D:\Work\Project Atlas\config\alpaca.env` in the local process memory. No credentials or raw quote prices printed/persisted; sanitized per-symbol receipt counts only. Selected original R24 source/CPU guard/12-empty-native-account-root verification remains active.
- **Success requires fresh accepted quote callbacks for BOTH MSFT AND AVGO.** SPY is the positive feed-control symbol and cannot substitute for either target. If only SPY is fresh, original native receipt is retained, with outcome `IEX_TARGET_COVERAGE_PARTIAL_NO_FINANCIAL_ACCEPTANCE` and nonzero diagnostic exit; no original E1 grant even if both targets are fresh.
- Original prior user-approved receipt and approval remain consumed and independent. New distinct local consent/result are absent until operator manually approves and genuine source observation occurs. A newly consumed failed/partial scope is never silently retried.

**Safe checks actually executed:** Original selected R24 native Python `-I -B -S` ran the exact wrapper `--review`, PASS exit0 with **zero credentials read and zero network**. Scoped Ruff source lint PASS. A separate premarket `--operator-approve-and-run` negative run correctly refused with `IEX_REGULAR_MARKET_WINDOW_REQUIRED_NO_CONSENT` **BEFORE any consent file, credential access or socket**. Independent selected native R24 CPU-budgeted source E1 and exact original 12 financial root audit PASS, evidence `logs/diagnostics/atlas-r24-iex-msft-avgo-followup-20261118-r01/independent-selected-r24-iex-next-session-hold.json` SHA256 **`74463c9edaf753c9633a6fd97e57447de5df8203278a68ad18c04846217cdfcb`**; original E1 rights/budgets/connections **0/3**, accounts **0/2**, financial PAPER/live money OFF.

The test is not meant to run now while the market is closed. The operator may run the scoped CMD **manually** within today's allowed regular session and type the exact scope locally only after independent review. Its result then needs **separate readback from the native original receipt**, not inference from a success banner.

## Still genuine E1 / prelaunch blocking

- Alpaca Basic free IEX single-exchange user-specific account rights and automated personal/non-display/data-retention scope still need exact reviewer disposition. Staff guidance supports the intended individual research behavior but is not account-specific execution acceptance. Persistent MSFT/AVGO actual executable quote coverage remains unverified until the new user-approved data-only sample, if actually completed.
- Hyperliquid public source permissions, bounded continuous books, modelled fees/settlement/funding or explicitly accepted conservative intrahour-flat method; original one-time six-POST raw sample remains REFUSED due stale `HlPerp.nextFundingTime`. Never force acceptance by replacing stale timestamp with a guessed hour.
- QD SEC original MSFT/AVGO research verified but live current independent price/valuation/issuer still missing; any price and quote/data rights shared with Alpaca must be sourced/accepted accurately.
- Original 11 separate Stage A–K financial prelaunch acceptances still needed, including native original retained 5+7 Windows owner, two originally scoped local financial journals, actual two simulated account FS1/FS3 inceptions, approved source/cross-epoch reader, real <=8-second original Stop/FLAT and first supervised HL PAPER pilot. All original production finance namespaces are EMPTY.

**Status:** public personal research use case better corroborated; one regular-session source check safely prepared and premarket refusal tested. **E1 0/3, source connection 0/3, accounts 0/2, PAPER NO-GO and LIVE MONEY OFF**. Earlier rough **8–15+ substantive batches** remains conditional, not a reliable countdown until account/source rights and actual financial gates qualify. No paid feeds, VPS, C-drive Atlas scratch or auto-start.
