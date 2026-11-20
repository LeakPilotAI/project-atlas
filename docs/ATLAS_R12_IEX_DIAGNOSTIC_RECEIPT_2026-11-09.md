# Atlas r12 data-only Alpaca IEX diagnostic receipts — 2026-11-09

**Implemented and verified in the development workspace. No live Alpaca connection, credential access or native financial source publication was performed. Financial PAPER remains NO-GO, 0/9 financial workstreams accepted.**

## Purpose and implementation

Atlas already has a bounded data-only Alpaca IEX probe that refuses a WebSocket handshake as evidence of current market data unless authentication, exact subscription acknowledgement, a valid fresh quote callback and clean disconnect all succeed. This milestone makes that *diagnostic observation* durable without turning it into provider-rights or financial PAPER acceptance.

- Added `scripts/observation_runtime/atlas_r12_iex_diagnostic_receipt.py`. It accepts **only** the existing probe's admitted `ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1` success packet and 1–10 exact requested symbols, plus a 32-character lowercase hex operation ID. It independently reuses the r12 bounded IEX observation validator.
- Receipt body stores only provider/feed identity, requested and observed symbol subsets, count of provider and actual callback observations, authentication/subscription/disconnect observations and explicit NO fields for clock certification, provider signature, independent rights acceptance, continuously executable prices, QD operational publication, PAPER account creation, simulated/live trading and startup. **No bid/ask values, private keys, API headers or account numbers.**
- Records use deterministic canonical JSON and SHA-256 to detect inadvertent/casual modifications. The digest is **not a provider signature or independent issuer authority**. Each receipt is created exactly once with `open('xb')`, flushed to disk, and immediately reopened for strict canonical/semantic verification. Existing or partial receipts are not overwritten or automatically adopted.
- Enhanced `scripts/observation_runtime/alpaca_iex_probe.py` with optional `--receipt-id <32 lowercase hex>`, **only** when the explicit `--execute-data-only --confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING` path is used. `--inspect` refuses a receipt ID and never reads credentials. The fixed per-user diagnostic output directory is `logs/diagnostics/atlas-iex-data-only-observations/` (ignored local diagnostics). Receipt recording takes place **after** a fully admitted real data-only probe, and any failure produces a fixed, sanitized refusal.
- Existing `--execute-data-only` without `--receipt-id` retains its original observation-only behavior. This code does not grant permission to load existing `config/alpaca.env`. An actual credentialed probe still requires separately scoped operator authorization and is preferable during regular U.S. market hours.

## Verified evidence and limitations

- Added `tests/test_atlas_r12_iex_diagnostic_receipt.py`: independent second Python-process readback; create-once and partial-write refusal; forged auth/subscription/freshness/observed-symbol rejection; tampering despite recomputed hash; unrequested symbols, trading authority and extra-field refusals; synthetic `alpaca_iex_probe.main()` success and duplicate refusal; and no credential-loader access without explicit CLI scope.
- Combined new receipt + previous Alpaca probe + r12 admission + existing IEX/feed integration regression: **118 passed, 0 failed**. **All provider data success was synthetic test data.** No real provider session occurred and no authenticated market-data entitlement has been established.
- The selected/native Atlas application remains revision r12 `2d4879878bf58bea5a3ed0a986b809791f638fec` with native selector file SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`. These workspace improvements must be included in a separately reviewed new native release before the selected application can use them.
- The real Quality Dips forward issuer/custody ACK and independent financial-clock authority are still missing. A successful local JSON receipt **cannot** certify a continuous operational feed, Alpaca contract rights, market-wide Robinhood coverage, or current executable quote availability. It is useful only as a diagnostic record of a bounded session.

## Next decisive commissioning action

Secure explicit one-time **data-only** permission to read the already-configured Alpaca credentials, and during normal stock-market hours run one short authenticated IEX quote probe using the guarded `--execute-data-only` scope and a fresh receipt ID. Verify genuine returned auth/subscription/fresh events, create and independently reopen the sanitized diagnostic receipt. Fail closed on no quotes, unsupported subscriptions or transport/entitlement errors. Then independently enroll an owned current Quality Dips source publication/issuer/custody ACK and qualify separate financial time, PAPER account, Stop and data-rights gates.

No Project Genesis, live trading, simulated financial orders, native selection or release install, private account, Windows Time, desktop shortcut, paid VPS, or GitHub push changed.
