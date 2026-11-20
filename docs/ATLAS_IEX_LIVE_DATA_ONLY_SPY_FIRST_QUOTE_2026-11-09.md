# Atlas first real Alpaca IEX Quality Dips data-only sample — 2026-11-09

**Outcome: bounded live IEX sample succeeded, but DOES NOT authorize financial PAPER.**

## Approved exact scope

The user approved **one 20-second credentialed Alpaca IEX quote-observation session** during regular U.S. equity-market hours, using the existing local `config/alpaca.env` with trading explicitly disabled. The bounded entry was `scripts.observation_runtime.alpaca_iex_probe --execute-data-only --confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING --seconds 20 --symbols MSFT SPY --receipt-id <new one-time 32-hex ID>`. The session started during regular Monday November 9 equity trading, after 08:30 Central. It ran once, with zero retries; no private credentials printed or changed, account balances/orders/positions accessed or any PAPER/live financial order submitted. The network probe closed cleanly.

## Actual provider observations

- Process return code: **0**; observed status `BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY`.
- Authenticated: **true**; exact IEX subscription acknowledged for requested symbols: **true**.
- Provider quote observations processed in bounded feed: **5,108**. Fresh accepted quote callbacks: **2,041**. These are different counters and not an indication that both symbols produced accepted callbacks.
- **Requested MSFT and SPY; fresh callback observed only for SPY.** MSFT must remain `NOT_VERIFIED_IN_THIS_SAMPLE`; do not claim its venue quote events, liquidity or entitlement failed. Exact absence cause unverified. An IEX subscription acknowledgment is not an accepted fresh MSFT quote.
- Scope was single venue IEX, **not consolidated SIP/NBBO**, continuous executable bid/ask, full Robinhood symbol coverage, or quote-eligibility acceptance for paper fills. Alpaca IEX alone is not proof of every asset listed by Robinhood.
- The sanitized, create-once diagnostic receipt is `logs/diagnostics/atlas-iex-data-only-observations/receipt-14cd7c6f05ff438390197099d82da615.json` (this ignored diagnostic receipt contains no raw quotes or keys). Operation ID `14cd7c6f05ff438390197099d82da615`; body SHA256 `49439e0bf64608daf8bb106de6189d2d19e462a4e6c40875503949bf933d0cff`. Independent `read_receipt` in a fresh process: `DIAGNOSTIC_DATA_ONLY_RECEIPT_VERIFIED_NOT_FINANCIAL_AUTHORITY`; `native_forward_source_published=false`, `paper_execution_authorized=false`.
- Actual postprobe selected-r12 financial assessment: `NO_GO`, **0/9 financial workstreams accepted**, `startup_authorized=false`, `simulated_orders_authorized=false`, `live_trading_authorized=false`. Verified native selected R12 remains CODE-ONLY. Existing source git SHA `e16c4d495ff9acdd91faf9e0f609aadcd7ad6b27` during this sample.
- Follow-up read-only and mocked/no-network suites for `test_alpaca_iex_probe_cli.py`, `test_alpaca_iex.py`, `test_atlas_r12_iex_diagnostic_receipt.py`, `test_atlas_r12_financial_readiness.py`, `test_alpaca_iex_watermarked_probe.py`: **115 passed, 0 failures**.

## Precise advancement, limitations and next actions

**A real Alpaca IEX credentialed data path and at least one genuinely fresh SPY quote callback are now empirically proved in a deliberately bounded sample.** This is a materially stronger source observation than the prior offline code/roster tests. It does **not** grant Alpaca provider data rights/redistribution terms, prove continuous 30-symbol rotation, accepted financial-clock uncertainty, QD scanner issuer/publication/custody, current independent research valuation, account initialization, executable paper fills, actual Stop/flatten, startup automation, or continuous runtime.

The source validation gate remains blocked until a separately qualified ongoing source connection can ingest both intended assets with independent freshness, symbol coverage/rights, durable publisher identity and data provenance. To determine why the short sample contained no accepted fresh MSFT callback, inspect **offline** the source validation/rejection logic and/or request a new separately authorized bounded data-only sample; do not infer an absent MSFT feed or silently reconnect from this consent. No native financial acceptance gate or QD forward source was promoted.

Continue Hyperliquid separately as 24/7 PAPER market (subject to its independent source/clock/account/Stop gates); the U.S. market-hours window was needed only for this Quality Dips equity quote diagnostic. Kalshi remains separate new-listing-only YES/NO and uncommissioned.

This document and roadmap addition are a **source-only milestone**. Do not mutate native r12 selected files, local broker credentials, Windows settings, desktop shortcuts, Genesis or GitHub remote without separate verified steps.
