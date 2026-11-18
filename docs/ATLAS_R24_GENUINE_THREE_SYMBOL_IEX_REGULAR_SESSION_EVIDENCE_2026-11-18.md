# Atlas R24 — original authenticated real-session IEX three-symbol source observation

**2026-11-18 | MADDOG Windows Desktop Commander | original selected R24 | financial PAPER OFF and live-money OFF**

## Exact original one-time operator-approved market-session execution

The operator opened the pin-verified R24 native data-only launcher during Wednesday, November 18, 2026 **08:33–14:50 US Central** and locally typed one distinct visible approval:

`APPROVE_ONE_ATLAS_R24_IEX_MSFT_AVGO_SPY_REGULAR_SESSION_60S_DATA_ONLY_NO_FINANCIAL_START`

The local approval was consumed exactly once; **do not replay**. The actual selected R24 `alpaca_iex_probe.py` used the preexisting, unchanged `D:\Work\Project Atlas\config\alpaca.env` credentials solely for one authenticated read-only `wss://stream.data.alpaca.markets/v2/iex` WebSocket session, three requested symbols **MSFT, AVGO and SPY**, zero reconnects, no broker account queries, orders, native finance publisher or wallet. It collected **at most 60 seconds of IEX quote observation**, plus original selected-native source/release checks (the persisted wrapper's full elapsed time **74.5 sec**, not 74.5 sec of source observation).

Original create-once local result:
`logs/diagnostics/atlas-r24-iex-msft-avgo-followup-20261118-r01/local-iex-credentialed-data-only-result.json`
**SHA256 `fadc90a32eff079f0c115438aef166dee0c3b98dee0d766cd503f494aa93a2e5`**

Exact new local human-scoped consent SHA256 `0048a5c6e01c21de329dd3959d2899497f4fbd04e9b4ca1dba1a2963c878eecf`.

The original installed native diagnostic receipt:
`logs/diagnostics/atlas-iex-data-only-observations/receipt-2356343d3f594754a9b5736ac3b4968c.json`,
file SHA256 `8e0f5235e33d7404ef55100da6b1b461056ca39559c8a69af976ecf77a7a9763`, original canonical body SHA256 `61bd1ccd14c45a109b236b055ff1a5c0689a54bf17d0366a701fdf6115bb8fde`.

### Actual per-symbol original accepted provider quote counts

| Actual requested symbol | Received IEX quote messages | Admitted after original R24 strict source parser | Rejected | Distinct fresh callbacks |
|---|---:|---:|---:|---:|
| **MSFT** | **2,353** | **2,353** | **0** | **1,459** |
| **AVGO** | **982** | **454** | **528** | **269** |
| **SPY** | **15,413** | **15,230** | **183** | **6,806** |
| **Total** | **18,748** | **18,037** | **711** | **8,534** |

Actual session status `IEX_MSFT_AND_AVGO_BOTH_FRESH_DATA_ONLY_OBSERVED`, exact authentication and all-three subscription ACK present, real fresh source callback for every requested symbol, original source connection **CLOSED** at completion. The previous 45s source-only test on the same date had MSFT/AVGO **zero** messages, SPY-only; this new distinct permitted regular-session test resolves the missing **transport/quote availability proof for MSFT and AVGO**, not an account/financial acceptance. A quote callback is not a trade fill or source continuous uptime.

**New and material AVGO data-quality risk**: **528/982 = 53.7678% of received AVGO quote frames were rejected** by the original R24 quote parser. The local receipt deliberately stores only sanitized aggregate counts and no original raw price fields/rejected frames; therefore the exact rejection reasons **cannot** be independently inferred from this receipt. The parser has independent spread, tick timestamp, condition, size, exchange and duplicate/out-of-order checks. Treat AVGO price-feed quality and executable quote continuity as **UNACCEPTED**, do not guess that the cause is provider data or blame ticker market state. Existing financial gates must not accept 454 admitted AVGO frames as continuous safe source quality; a future separately reviewed, source-only diagnostic would need **bounded reason-code aggregates (no raw data retention)** to distinguish parser false rejections from genuinely unusable quote messages. No new network request was made in this checkpoint after the consumed operator session.

The terminal prints a legacy literal `IEX_R24_ONE_SHOT_SCOPE_CONSUMED_START_45S_DATA_ONLY` inherited from the older 45-second diagnostic wrapper. That banner is **stale wording**, not the operational source duration. Actual independently pinned follow-up wrapper sets `SECONDS=60` and passes `--seconds 60` to the native probe, and its review explicitly printed max 60 seconds. The original one-time source/receipt are preserved unchanged, not retroactively altered for display purposes.

## Independent original selected-R24 source, receipt and financial hold check

A **separate** actual selected native release `python.exe -I -B -S`, using only installed R24 source and packages and `NativeR17CpuBudget` CPU guard, called original selected `atlas_r12_iex_diagnostic_receipt.read_receipt` validator, reopened the separate canonical original receipt bytes and exact local result/consent, SHA-pinned all original identities, cross-checked complete 3×4 counters, original E1 documentary checker, and native twelve-root custody inspector. Full readback **PASS exit0**, no second provider query, no private configuration access and no financial native write.

Independent result under `logs/diagnostics/atlas-r24-iex-msft-avgo-followup-20261118-r01/independent-original-selected-r24-iex-msft-avgo-three-symbol-readback.json`, **SHA256 `940529d037cd4a190e21e8bcc4df5777dd4bb77f0c0502fc13587bc811f54f4b`**.

Exact selected R24 source `5c3970b7150fd448f5f3c5a25f424687c704a2f9`, `r0024.json` SHA256 `afe5ae7e1e83088e14584cf942f51ba01792c375a5cc50130d1ce48c2c0747ad`; original installed `alpaca_iex_probe.py` SHA256 `b050c52a4872699d026b6108d9691853a55988af18d19d45a6d0d8c3c4237fbc` and `alpaca_iex.py` SHA256 `af115f0281fae29e9e7d8f5e01ebcf3ef72fa2c46030fee593a737ba6927af79`. All **12 original real financial namespace roots remain distinct and EMPTY**. Original E1 rights **0/3**, original source budgets **0/3**, original activated operational connections **0/3**, simulated financial accounts **0/2**, original financial retained owner/journals/actual Stop **not commissioned**, and financial PAPER/live-money **OFF**.

## Critical next decisions

1. **Alpaca user-specific Basic/IEX local automated non-display/personal archival/derived indicators and private alerts rights** need genuine provider-account approval rather than a successful WebSocket handshake. Official Alpaca public Basic IEX $0/month docs and staff's October 15, 2026 forum answer support personal noncommercial research but are not a substituted account contract. A support draft exists in the correct Atlas `viralaiandtechnology@gmail.com` mailbox; it needs updating because its original MSFT/AVGO zero-quote question has been superseded by the new observation. Sending requires separate user review.
2. **AVGO rejection attribution and publisher source continuity** are not proven by the one-shot data-only sample. Do not infer all MSFT/AVGO/13,487 universe current prices, SIP/NBBO, 24/7 coverage or executable fills from this brief IEX source check. No further data-only approval is automatically created.
3. **Hyperliquid and QD other original E1 provider acceptance** remain distinct. The previous six public Hyperliquid INFO requests were consumed and genuinely REFUSED for stale observed provider next-funding timestamps; new receipts cannot just infer a future timestamp. Original HL flat-first stop policy is code-only, not financial funding settlement or user account fee acceptance.
4. **Native financial stages B–K**: retained owner/clock, two coordination journals, original two 1,000 USD/USDC simulated account inceptions with independent approvals, accepted QD WATCH/HL source publisher and reader, real original financial Stop/FLAT <=8 seconds and first supervised intrahour-flat HL PAPER pilot. No live money for months after PAPER.

**Verdict:** actual three-symbol IEX authenticated source availability is **proven**; remaining AVGO parser quality and individual rights/genuine finance commissioning are NOT. Original E1 0/3 and account inceptions 0/2 unchanged. A planning range of **8–15+ substantial verified acceptance batches** to first supervised financial PAPER remains conditional on provider agreements and real financial gates; do not reduce it solely because data-only callback counts improved. Preserve all original protected source pins and historic R23 edits; D-drive only, no VPS, paid feed, C-drive Atlas scratch, or automatic startup.
