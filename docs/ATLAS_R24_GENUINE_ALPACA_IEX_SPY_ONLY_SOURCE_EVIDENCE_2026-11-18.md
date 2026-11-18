# Atlas R24 — genuine authenticated Alpaca IEX, SPY-only data observation

**November 18, 2026 | MADDOG | selected native R24 code-only | financial PAPER OFF / live money OFF**

## Original operator-approved, fully consumed data-only attempt

Operator reviewed and independently typed exactly `APPROVE_ONE_ATLAS_R24_ALPACA_IEX_MSFT_AVGO_SPY_45S_CREDENTIAL_READ_DATA_ONLY_NO_FINANCIAL_START` into the visible Windows terminal. The original native R24 `alpaca_iex_probe`, using the existing D-drive `config/alpaca.env` in process memory, authenticated with the public IEX-only Alpaca quote WebSocket `wss://stream.data.alpaca.markets/v2/iex`, subscribed to the requested symbols **MSFT, AVGO and SPY**, and ended the one-shot session with a CLOSED connection. Data-only scope: one WebSocket session, up to 45 seconds of quote observation, no reconnects, no account or broker order endpoints, no source publishing, no financial PAPER/live money. Original wrapper runtime **58.985 seconds** includes selected native source/preauth checks in addition to the bounded 45-second source observation; this total process duration must **not** be misrepresented as 59 seconds of market data.

Original one-shot local scope is **CONSUMED**; no automatic retry or replay is allowed. Operator-visible final outcome was **`IEX_AUTHENTICATED_FRESH_DATA_ONLY_OBSERVED`**, original create-only sanitized result `logs/diagnostics/atlas-r24-iex-account-source-20261118-r01/local-iex-credentialed-data-only-result.json`, SHA256 **`4b34ef7b075c319b6c0e2061052375d508c87ff741e44475858de62094a37257`**. Original local scope decision SHA256 **`4604d2cc6bb48a2adcfa18c96608344599ca14e904e1e26e6f0c4af9c415b5d1`**.

The exact distinct original `atlas_r12_iex_diagnostic_receipt` single-use receipt, operation `b3738a676d1e41d48eb021f020cde27c`, was durably written under `logs/diagnostics/atlas-iex-data-only-observations/receipt-b3738a676d1e41d48eb021f020cde27c.json`. Original **body SHA256 `9c8da0173c9021ac26be526c47ea5a283182045dafd0d642178c75d8299f0574`**. This is an *unkeyed hash and a local transport accounting record*, not a signed provider license or full financial source authority. No actual quote prices or credential bytes were saved.

### Exact observed per-symbol market messages

| Exact selected IEX symbol | Total quote messages received | Accepted provider quote messages | Rejected | Independent new fresh-quote callbacks |
|---|---:|---:|---:|---:|
| **SPY** | **237** | **217** | **20** | **198** |
| MSFT | **0** | **0** | **0** | **0** |
| AVGO | **0** | **0** | **0** | **0** |

The source test confirms **actual IEX authentication, exact subscription acknowledgment for all three, and strict fresh SPY events**. It does NOT prove fresh provider quote data for **MSFT or AVGO**, even though both were requested and acknowledged. Zero received quote messages alone does not establish why those symbols were silent; do not fabricate a feed entitlement denial, quote status, halt, market hour, or trade.

The original R24 IEX parser rejects stale, incomplete, malformed and invalid one-sided messages; SPY's 20 rejected frames remain counted, not treated as accepted data. There are 217 total accepted frames and 198 *distinct fresh callback* deliveries; these counts are different by design and should not be equated with 198 separate provider connections or continuous subscriber availability. Exact current quote values, wider market consolidated NBBO, persistent resilience, and specific user account storage/non-display rights remain **unverified**. The original provider public documentation for Alpaca Basic supports free single-exchange IEX market data and personal paper-trading algorithms, but is not an E1 authorization issuer: <https://docs.alpaca.markets/us/docs/about-market-data-api> and <https://docs.alpaca.markets/us/docs/paper-trading>.

## Independent installed selected R24 verification, no second provider request

A **separate selected original R24** isolated `python.exe -I -B -S`, original `NativeR17CpuBudget` host guard, **installed R24** original `atlas_r12_iex_diagnostic_receipt.read_receipt`, selected probe module, original exact E1 rights checker, 12-native-root inspector, verified the exact original result/consent SHA-256s and independently reopened original diagnostic receipt bytes. The first readback harness initially assumed `read_receipt` returned a nested raw body; its actual contract returns a **sanitized validated summary**. Only the new, nonfinancial diagnostic harness was corrected to independently reopen the original canonical receipt after native validation. No real original receipt or selected source was modified. Independent run exit **0**, status `INDEPENDENT_ORIGINAL_IEX_SPY_OBSERVATION_RECORDED_NO_E1_ACCEPTANCE`, receipt `logs/diagnostics/atlas-r24-iex-account-source-20261118-r01/independent-selected-native-iex-spy-e1-readback.json`, SHA256 **`f4b0b4361a3b86c841f6e3599d5631438a3a5296402a51c1416d965774162b14`**. No second data feed call or credential read occurred in the independent check.

Verified original selected revision 24 envelope SHA256 **`afe5ae7e1e83088e14584cf942f51ba01792c375a5cc50130d1ce48c2c0747ad`**, original source probe SHA256 **`b050c52a4872699d026b6108d9691853a55988af18d19d45a6d0d8c3c4237fbc`**, and **12/12 actual native financial namespaces EMPTY**. Original E1 provider rights, data budgets and operational connections **0/3 accepted**. Original two simulated account inceptions **0/2**. The consumed observation does not create finance clock ownership, recurring source continuity, accepted Quality Dips current issuer/valuation, durable original financial Stop/FLAT or first supervised Hyperliquid PAPER pilot.

## Concrete next requirements and execution estimate

1. Independently establish the existing Alpaca user's exact Basic/IEX account permissions, any applicable **automated non-display, local quote retention, derived ranking and display scope**. A documented provider permission or user-specific account agreement may be used; a successful login alone is **not** evidence of all such rights.
2. A *distinct future explicit local data-only scope* during the regular US equity session may be justified to investigate actual MSFT/AVGO fresh quote coverage. This is a **new future authorization**, not replay of consumed local consent, and remains separate from any E1 issuer acceptance; do not start it automatically.
3. Independently accept genuine Hyperliquid source-currentness, funding economics / flat-first method and source-bounded request rights; qualify original QD WATCH underlying valuation/current quote rights. Original real Stage B–K financial retained Windows owner, two scoped journals and simulated account inceptions, current source readers and actual native durable Stop/FLAT still pending.

**Impact:** real authenticated SPY-only IEX source transport verified. **No genuine original E1 financial source acceptance was promoted: 0/3.** Months of ongoing PAPER testing begin only **after** original supervised financial launch, not before. Current estimate remains **8–15+ substantial additional batches** before the FIRST safe supervised financial PAPER launch, *conditional on external account permissions/source availability and actual original financial owner/Stop gates*. It may take more if an external source right is not available.

**No C-drive Atlas scratch/storage, paid data feed, VPS, source selector change, private account queries, broker orders, wallet, auto-start, financial PAPER or live money authorized by this data-only checkpoint.**
