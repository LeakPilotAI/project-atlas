# Atlas IEX data-only diagnostic false-positive repair — 2026-11-09

**Implemented and tested in source. Selected native r12 image is unchanged. Financial PAPER remains NO-GO (0/9 formally accepted operating workstreams). No Alpaca credentials or provider accounts were accessed during this milestone.**

## Concrete defect repaired

Before this change, `scripts/observation_runtime/alpaca_iex_probe.py` could return exit **0** and a JSON payload even when a bounded IEX WebSocket run reported **`authenticated=false`**, **`subscribed=false`**, or **no observed fresh quote**. A successful socket attempt or positive asset catalog does not establish usable real-time equity quotes; the original CLI's exit code could be misread as evidence of quote availability.

The repaired CLI requires explicit `--execute-data-only` AND exact `--confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING` **before loading the existing private Alpaca configuration or opening an IEX socket**. Time and symbol roster must be bounded and validated first. The `--inspect` mode reports selected-r12 source readiness without reading credentials or connecting providers.

The credentialed execution (not invoked in this milestone) uses the existing IEX feed with zero reconnections, an authenticated WebSocket, exact subscription acknowledgement, and an `on_fresh_quote` callback. The callback admits only actual subscribed symbols, IEX source, non-empty provider timestamp, and explicit `paper_fill_authorized=false` and `live_order_authorized=false`. On completion, admission requires positive actual provider quote count, at least one callback event, `fresh_quote_observed_during_connection=true` and `connection=DISCONNECTED`. Otherwise exit **1** with a fixed non-secret refusal; never emit raw keys, quote prices, API headers, account details or transport errors.

On qualified data-only evidence, the JSON status is `BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY`, with the **subset of symbols actually observed**, not every requested or research-catalog symbol. It explicitly reports `single_exchange_not_nbbo=true`, `continuous_executable_prices_verified=false`, `provider_rights_independently_accepted=false`, `paper_fill_authorized=false`, and `live_order_authorized=false`. A one-time quote does **not** authorize QD or Hyperliquid simulated fills, PAPER accounts, or a continuously executable feed.

## Evidence generated this turn

- Existing code: `backend/app/investment/alpaca_iex.py`, with bounded authenticated single-IEX WebSocket subscriptions and quote freshness checks, reused without changing native r12 or its installed files.
- Fixed source: `scripts/observation_runtime/alpaca_iex_probe.py`.
- Tests: `tests/test_alpaca_iex_probe_cli.py` (now covers missing CLI scope before credentials, actual offline inspection, authenticated synthetic quote callback success, auth/subscription-only false positives, no fresh quote, changed provider callback, no subscription ACK, connection still open, and unsampled symbol refusal) plus existing IEX/source/watermark tests.
- **85 tests passed, 0 failed**. All successful feed samples in tests were simulated; **no live Alpaca IEX session or actual provider entitlement was checked**.
- Native selected r12 application remains release `2d4879878bf58bea5a3ed0a986b809791f638fec`, already physically deployed and selected. This modification is in the **workspace branch only** until a later separately reviewed native image update. Source changes must not be misrepresented as having altered the sealed selected native release.
- Local time on this run was approximately 4:42 a.m. Central, outside normal U.S. equity continuous trading hours. A live quote probe now would be particularly likely to encounter an empty quote interval; that is not proof the credentials or entitlement are invalid.

## Next practical action

Obtain an **explicit one-time, data-only scope grant** to use the existing local `config/alpaca.env` with the guarded probe during regular market hours. This is private credential access (unlike the offline tests) and must be separately approved; a generic request to continue coding is not credential permission. Run the existing script for a bounded sample, record only provider authentication, IEX subscription, and actual fresh event counts, with no prices or credentials in logs, and close the socket. Refuse empty/no-data results. Then independently enroll and verify an owned current QD forward scanner publication and its native custody; Alpaca asset discovery alone cannot close that gate.

The user's one-click Start/Stop PAPER requirements, independent financial-clock/ledger proof, provider rights, Hyperliquid accounts/feeds, simulated account inception, automatic Stop/flatten, dashboard/Discord and supervised soak are still outstanding. No financial authority, native selection or provider access was granted here.
