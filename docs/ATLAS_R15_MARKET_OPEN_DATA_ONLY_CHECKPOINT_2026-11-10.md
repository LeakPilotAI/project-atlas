# Atlas R15 — live-market data-only verification, November 10, 2026

## Result: verified free IEX delivery; Hyperliquid blocked; financial PAPER still NO-GO

**Selected Atlas release R15, native revision 14** remains unchanged. Data-only requests were conducted using the user's express approval for market-hour commissioning. They did not place any PAPER or real-money orders, log into broker trading accounts, modify native releases, or enroll financial writers.

### Verified Alpaca IEX market-hour delivery

Two real authenticated and disconnected IEX WebSocket observations succeeded during regular U.S. equities hours. Both have original, create-once, independently re-read sanitized receipts:

| Probe | Requested | Accepted provider quotes | Fresh callbacks | Immutable receipt SHA-256 |
|---|---|---:|---:|---|
| 20 seconds | MSFT, SPY | 5,572 | 2,250 | `7d685631b91baeb73b8c0e0298b5d32065eed42dbfac2b3a05734ec200b67f41` |
| 25 seconds | AVGO, NVDA, AAPL, AMZN, META, GOOGL, VOO, QQQ, IWM, MSFT | 19,998 | 8,230 | `6ff760b478b619f05b74ae1c32aa01ebb32968ac8e4e69408380d8648198412f` |

**25,570 accepted provider quotes in the two bounded samples; all ten second-sample symbols had fresh callbacks.** The connection was verified closed after each sample. This proves usable, authenticated **IEX single-venue delivery for the tested symbols**, not a continuous trading source, SIP/NBBO coverage, verified Robinhood tradability for every researched symbol, or independent provider rights for automated financial PAPER execution. Alpaca's free/basic IEX feed supports 30 concurrent symbols; the 13,487-symbol *research* universe would require at least 450 sequential rosters, not a simultaneous verified live universe. The correct final product must be engineered around accepted data entitlement/coverage rather than asserting that all 13,487 have current executable quotes.

### Hyperliquid — no accepted book

The one explicitly approved two-request BTC public-book probe ran with the exact `HYPERLIQUID_TWO_PUBLIC_INFO_REQUESTS_DATA_ONLY_NO_TRADING` scope, but returned the sanitized refusal `HL_SOURCE_OR_DATA_VALIDATION_REFUSED`. The original durable ledger advanced from **10/12** to **12/12 attempts**. No validated BTC public L2 book was accepted, and the error category is generic; **do not claim to know the underlying provider/server/parser cause without evidence**. The budget must not be silently renewed/reset, and no extra request is allowed under the consumed one-shot research lease.

The current exhausted-budget guard and selected-R15 data-only previews were tested **46 passed, zero failed**; they refuse before opening another request gate, NTP lease or provider transport when the budget is exhausted. The original R15 native code remains selected.

### Kalshi — discovery yes, executable depth no

A bounded unauthenticated Kalshi public API GET returned **30 open single-market listings**, all with creation timestamps within 48 hours (first page only). A subsequent strategy-policy scan of 50 open public markets identified **43 new single-market observation candidates after excluding non-activity policy failures**, but **all 50 lacked the policy minimum 24-hour volume and open interest**. The sampled public orderbook from one candidate had no executable YES or NO levels on either side. Atlas correctly refused to imply a fill from an empty book.

These are one-shot stdout observations **without a durable raw Kalshi source receipt**. They demonstrate public market discovery and the thin-market constraint, not profitable mispricing or Kalshi financial PAPER commissioning.

### Real remaining commissioning boundaries

The **PersonalPaper native custody still has zero activation children** and no accepted QD or Hyperliquid financial writer/account enrollments. Continuous operational finance clock/ledger/owned financial Stop, verified current quote rights/freshness/universe coverage, first supervised PAPER entries and exits, daily report/Discord financial evidence, and extended soak remain unaccepted. Kalshi new-listing YES/NO PAPER remains a later independent financial lane. The original two Atlas desktop shortcuts still control observation, not financial PAPER operations.

**Formal financial PAPER: NO-GO, 0/9 independently accepted operating gates.** The user-approved data-only observations cannot be used to automatically promote any financial activation or real-money order authorization. Project Genesis, native R15 selection, credentials themselves, paid services/VPS and OS boot configuration were untouched.

Create-only machine-readable checklist: `docs/ATLAS_R15_MARKET_OPEN_DATA_ONLY_CHECKPOINT_2026-11-10.json`, SHA-256 `728fbf4316d7e88203421c621887c100fa4db0225e6c06c8b1a25bf3bac4406d`.
