# Atlas Alpaca IEX watermarked legacy probe authorization repair — November 9, 2026

**VERIFIED SOURCE-ONLY SAFETY FIX. Financial PAPER remains NO-GO (0/9 accepted gates). No provider access, private credentials, simulated orders or live trading.**

## Corrected issue

The older `scripts/observation_runtime/alpaca_iex_watermarked_probe.py` accepted an unscoped CLI invocation. Once an existing watermark was present, it would load `config/alpaca.env` and attempt the real IEX WebSocket connection. It could also exit successfully when the provider reported authentication and subscription but **no fresh quote callback was observed**. This contradicted the newer guarded data-only IEX probe, and was an unwanted alternate path into private provider access.

## Source change

- `bounded_observation()` now requires `confirm_scope='ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING'` and validates bounded symbol, duration and path types **before** starting the watermark lease, loading the Alpaca configuration or accessing provider connections. This is a diagnostic-scope check, **not** permission granted in this milestone.
- The CLI now explicitly distinguishes `--inspect` (no watermark inspection, credentials, provider or trades) and `--execute-data-only --confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING --watermark <pre-enrolled-path>`. Bare legacy CLI invocations cannot contact a provider; missing prior enrollment is refused before credential loading.
- A genuinely successful data-only probe now requires authenticated and subscribed provider state, clean disconnected final state, a positive provider quote count, `fresh_quote_observed_during_connection=true`, and **at least one actually accepted, non-replayed watermark callback**. No quote or failed authentication/subscription returns a sanitized refusal. The output still denies continuous executable market prices, independently accepted data rights, PAPER fills, live orders and startup.
- Existing replay watermark advances on each legitimately accepted callback; if a later session-final summary is inconsistent, the session is refused **without rolling back an already observed timestamp**, preventing accidental replay. A watermark is not a provider signature, accepted forward source or financial writer lease.

## Executed evidence

- Replaced older probe's direct/CLI tests with explicit scope checks, no-credential-before-scope, missing enrollment, invalid inputs, authenticated synthetic callback success and replay refusal, missing/contradictory provider quote evidence, and genuine no-quote refusal.
- Final combined test suites for the legacy watermark, new bounded probe/diagnostic receipt, existing IEX transport, and r12 data source admission: **121 passed, 0 failed**. All successful quotes in the suite are synthetic. No private Alpaca credential file was opened by the test run and no external IEX socket was opened.
- Selected installed native release **r12** remains unchanged. These are workspace source changes; separately reviewed native packaging and installation is required before the selected installed app incorporates them. The original r12 selector file SHA-256 remains `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`.

## Remaining decisive financial dependency

Obtain **separately scoped explicit permission** for one authenticated data-only Alpaca IEX quote probe using existing configured credentials, preferably during the regular U.S. equities session; independently verify provider authentication/subscription and fresh quote receipt. Then enroll a genuinely current Quality Dips forward publisher with native issuer/custody ACK and independent financial-clock authority. This source-only safety fix **does not close any of the nine financial operating gates**.

No changes to Project Genesis, native selector, Windows Time, desktop shortcuts, automatic startup, paid VPS, financial accounts/ledger/positions, simulated/live orders, or GitHub remote.
