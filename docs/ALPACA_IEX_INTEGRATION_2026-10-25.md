# Alpaca IEX data-only integration â€” 2026-10-25

Base a3dbda4f921205ca7e91b32d4151cb90be7cfec3;chatgpt/atlas-rebuild-v1.
Authorized source integration, deterministic/disposable tests and bounded live
market-data probes. No order API, operational PAPER session or financial inception.

## Actual live result

Two sequential bounded read-only WebSocket probes (20seconds and8seconds) to
`wss://stream.data.alpaca.markets/v2/iex` both received authenticated and exact
MSFT/SPY quote-subscription confirmations, with0reconnects and0quote messages.
Final probe observed at 2026-10-25T09:59:13.571951+00:00. This is Sunday; the existing reviewed
NYSE calendar reports MARKET_CLOSED. Bid/ask, exchange quote timestamps and quote
latency are UNAVAILABLE, not zero. No latest/historical price was fabricated or
substituted. Authentication/subscription proves observed feed access; it does not
prove executable prices, accepted automated-use licensing or financial authority.
The sockets closed normally at their bounds; result.authenticated/subscribed
records historical success while nested cache flags are false/DISCONNECTED after
closure. No continuously running provider/service remains installed.

The private config is ignored/untracked. Its existing explicit
ALPACA_TRADING_ENABLED=false is required; true/missing refuses. UTF-8 BOM is
handled without changing the file. Keys/secrets are never included in repr,
errors, snapshots or probe output; no credential was installed or copied. The
preexisting .gitignore exclusion was preserved and included in publication.

## Implemented integration

- `backend/app/investment/alpaca_iex.py`: fixed-endpoint data-only authenticated
  WebSocket; exact host/path checked before sending secrets; no broker SDK or
  account/order endpoint. Private disabled frame logger; sanitized failures;
  bounded explicit symbols(up to30), exact subscription acknowledgement, terminal
  auth/entitlement/symbol/connection-limit refusal, bounded transport reconnects,
  re-authentication/resubscription and RFC6455 transport ping/pong. No wildcard,
  paid-feed fallback or eviction of other provider sessions. Explicit streams
  accept a bounded duration up to24hours and cancellation/stop; nothing auto-starts.
- Cache validates positive Decimal bid/ask, noncrossed bounded spread, positive
  integer sizes, regular quote conditions and timestamp order/freshness. Raw
  nanosecond exchange time and native round-lot sizes retained. Older/conflicting
  quotes invalidate admission; disconnect/reconnect cannot reuse an old generation.
  Malformed protocol errors clear connection admission. Missing data is unavailable.
- `scripts/observation_runtime/alpaca_iex_probe.py`: standalone explicit data-only
  probe capped at60seconds; reads only the ignored config, requests MSFT/SPY quotes
  and never imports backend lifespan, scanners or financial stores. These symbols
  are probe examples, not a financial-policy restriction.
- Existing `QualityDipQuoteService(alpaca_feed=...)` consumes this cache for the
  existing research overlay. No network calls or other-provider fallback occur
  from reads. Existing default research behavior remains compatible. The actual
  QualityDipScanner accepts the injected quote service; it is NOT started here.
  Unknown/unsubscribed/stale/closed-session quotes cannot trigger its ladder.
- `backend/app/services/quality_dips_iex_input.py` supplies existing QD_AUTO_L1_V1,
  V3/V5 next(timeout)/observation-frame and shutdown observe(position,timeout)
  interfaces. Existing ranking and monitoring decisions remain injected/verified;
  no rankings or thesis evidence are invented. Instrument identity, entitlement,
  actual round-lot share conversion, calendar/trading status and clock require a
  separate accepted execution-authority lease. No default verifier exists.
  Nanosecond source data are retained; the integer-second engine gets an additional
  one-second precision-uncertainty budget, never overstated freshness. Duplicate
  source-quote identity is stable across repeat delivery/reconnect. Existing risk,
  capital, cash, one-position, ASK-entry/BID-exit and2bpsfee+2bpsslippage logic reused.
- Selected-account router optionally attaches a cache-only market_data view, even
  when financial evidence is UNAVAILABLE. The accepted read-service host has an
  optional market_reader seam. Default route/startup registration remains unchanged;
  read-service financial enrollment is still required. No mutating research GET,
  provider refresh, financial POST or account initialization is introduced.
- Original HTML/JS show IEX bid/ask, lot sizes, raw timestamp, connection/auth/
  subscription state and fresh/stale/unavailable separately from financial state.
  IEX is clearly SINGLE EXCHANGE, NOT consolidated NBBO. Unavailable values never
  become zero. Same existing GET/polling; no additional polling or trade controls.
- Control Center optionally reads the injected cache and formats data readiness
  separately from PAPER authorization, which remains NO. Normal SHUTDOWN_FLATTEN,
  emergency separation, unknown/open-position preservation and owned shutdown are
  unchanged. No real Control Center or operational service was launched.
- `backend/pyproject.toml` explicitly declares the installed WebSocket data-client
  dependency. No software installation or Windows configuration change occurred.

## Validation (final results, no overlapping addition)

-84Pythonpassed0failed0skipped:39new deterministic IEX cases plus existing35engine,
  7quote-service and3production-lock regressions.
-107Pythonpassed0failed0skipped: disjoint native read-service, selected-account
  integration and passive Control Center regressions. All native resources/listeners
  were disposable and confined to new test roots.
-Total191distinct Python passes across those two selections.
-37frontendpassed0failed0skipped:32existing plus5new IEX cases. DOM/fetch harness;
  no new genuine browser execution claimed in this milestone.
-Positive, stale, malformed, crossed, zero-size, unknown conditions, nanosecond
  order/conflict, disconnected/reconnected, authentication/entitlement/limits,
  credential redaction/BOM, exact redirect-host refusal, cache-only router reads,
  market closure and runtime observation-input cases covered.
-The existing canonical engine executed a disposable ASK entry followed by BID
  shutdown exit, cash899.96 then1009.916, preserved exact Decimal costs and identical
  retry result. This was synthetic evidence, not an actual provider fill.
-Compilation8Pythonfiles;new modules and changed lines lint clean;JS syntax;
  PowerShell parsing2files;PAPER policy audit572runtimefiles0issues;diff checks.
-Whole-file Ruff still reports39preexisting findings in legacy quote/scanner code.
  Baseline and current diagnostics were compared:39before/39after,0new or changed
  findings. These unrelated legacy findings were not silently fixed or suppressed.

Original failed attempts retained privately: Windows BOM fixture default encoding,
new cash-string formatting assertion, one frontend helper-name error and native
read-host monkeypatch compatibility. The compatibility defect was fixed by retaining
its original build_app call shape when no optional market cache is supplied.
Final tests pass; no original failure evidence deleted. No privilege-dependent
symlink/power-loss or operational security acceptance was claimed.

## Limits and remaining first-session prerequisites

1. During a regular market session, observe actual fresh usable IEX bid/ask/size/
   timestamp and reconnect/staleness behavior. Quote latency remains unmeasured.
   No fallback to SIP/NBBO, last trade, guessed liquidity or paid feed is allowed.
2. Accept provider terms/entitlements for this internal autonomous simulated use;
   authenticate instrument mapping/round-lot sizes, trading status/halts and current
   calendar. Current subscription lists are explicit and bounded; unsubscribed
   ranked symbols are unavailable, not secretly subscribed or financially allowed.
3. Complete actual B1/C1/D1/E1 scoped acceptance and install/bind real issuer/session,
   current-pin custody, clock continuity, all-writer ownership, decision/monitor
   reader, retained-close and data-cache interfaces. Same-user/D:-only rollback and
   clock limitations remain explicit. Feed authentication grants none of those gates.
4. Separately authorize one-time hypothetical inception into the existing account,
   operational bridge/resource verification and bounded autonomous PAPER launch.
   The13 real directories remain untouched. No real account exists by test success.
5. Supervise first authorized session, truthful reports/overnight continuity,
   graceful shutdown and failure/recovery, then seven sessions and30â€“60-session
   validation. No live-money routing will be implemented.

Official references checked for implementation:
-https://docs.alpaca.markets/us/docs/streaming-market-data (auth,subscriptions,errors)
-https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data (quote schema,round lots)
-https://docs.alpaca.markets/us/docs/market-data-faq (IEX single-exchange scope)

All21historical decisions/seven phases,original theme,strict/manual contracts,
startup locks,financial history and Genesis isolation preserved. No Genesis,
Docker,brokerage order,protected store,financial writer or operational startup
was accessed or activated. B1/C1/D1/E1 BLOCKED;PAPER startup NO;production NO-GO.

## Exact publication file inventory

.gitignore
backend/pyproject.toml
backend/app/investment/alpaca_iex.py
backend/app/investment/quality_dip_quotes.py
backend/app/services/quality_dip_scanner.py
backend/app/services/quality_dips_iex_input.py
backend/app/api/quality_dips_selected_paper.py
backend/app/static/quality_dips.html
backend/app/static/quality_dips_selected_paper.js
scripts/observation_runtime/alpaca_iex_probe.py
scripts/observation_runtime/quality_dips_read_service.py
scripts/windows/Atlas-Background-Controls.ps1
scripts/windows/Atlas-Control-Center.psm1
tests/test_alpaca_iex.py
tests/quality_dips_selected_frontend.test.cjs
docs/ALPACA_IEX_INTEGRATION_2026-10-25.md
docs/ALPACA_IEX_CONTINUATION_2026-10-25.md
docs/ATLAS_AUTONOMOUS_STATE.json
docs/ATLAS_AUTONOMOUS_EXECUTION_QUEUE.md
PROJECT_ATLAS_MASTER_ROADMAP.txt
