# Atlas — genuine selected R21 market-open data acceptance audit
November 13, 2026. Stock-market-open checks on local Windows 11 desktop MADDOG, main project D:\Work\Project Atlas.

## Real original R21 observations (NO FINANCIAL EFFECTS)

Atlas original selected installed immutable source release: `119dd8626da32e74bd7f86db9de1c1a8fd2c20ac`, native selector rev 20. Actual original in-process Windows Job and original two-peer independently qualified NTP, original authorized *data-only* credentials loader (`ALPACA_TRADING_ENABLED=false`) and four bounded HTTPS Alpaca data `quotes/latest?feed=iex` GETs per probe. The original selected R21 process did not call paper or live order APIs. All four required symbols are MSFT, AVGO, SCHD, VTI, **single-exchange IEX** not consolidated NBBO. Source/probe output is sanitized: no raw stock prices or API secrets.

### First market-open original R21 probe
Receipt: `logs/diagnostics/atlas-r21-selected-job-iex-marketopen-20261113-r01.json`
SHA256: `42c3f4826b55a03b54cc6d65a6e4cb73215f84ba188a0d6c14a41348eb5270f7`

| Symbol | Bid + ask present | Original quote fresh under selected conservative rule | Conservative upper bound quote age | Raw floor-relative source age |
|---|---|---|---|---|
| MSFT | yes | yes | 1394 ms | 0 s |
| AVGO | yes | yes | 3419 ms | 2 s |
| SCHD | yes | no | 485 ms | -1 s |
| VTI | yes | no | 1098 ms | -1 s |

Actual result: 4/4 both-sided, 2/4 fresh, 2/4 fresh AND both-sided. All financial quote admissions FALSE, source issuer FALSE, account/paper authorization FALSE.

### Second independent real-market original R21 probe
Receipt: `logs/diagnostics/atlas-r21-selected-job-iex-marketopen-20261113-r02.json`
SHA256: `36145aecf81114cc57fb5198944aec853245b0d947d87187e9164d3cd2848c33`

| Symbol | Bid + ask present | Original quote fresh under selected conservative rule | Conservative upper bound quote age | Raw floor-relative source age |
|---|---|---|---|---|
| MSFT | yes | no | 1015 ms | -1 s |
| AVGO | yes | yes | 1384 ms | 0 s |
| SCHD | yes | no | 717 ms | -1 s |
| VTI | yes | no | 341 ms | -1 s |

Actual result: 4/4 both-sided, 1/4 fresh, 1/4 fresh AND both-sided. Four actual GETs succeeded; no financial source accepted.

### Technical finding: provider event vs independent UTC quantization

Current `atlas_r20_native_iex_latest_readonly.inspect_quote` uses the **integer-floored seconds** from the original independently verified `NativeVersionSafePaperOperatorClock.sample()`, then multiplies by 10^9 to compare with high-resolution provider UTC timestamps. A valid provider event later in the current UTC second may appear as a *negative* source age relative to the beginning of that second. `source_age_seconds=-1` on the observed quotes is therefore **ambiguous**, not proof the provider response was stale or that it genuinely occurred in the future.

The installed R21 policy appropriately refuses to declare such an ambiguous sample fresh. It also reports a conservative age upper bound that accounts for 1-second quantization plus the verified 139-ms NTP uncertainty. This can produce a tiny positive upper-bound age yet still refuse freshness because the earlier age lower constraint fails; do NOT silently flip the freshness decision by dropping the negative-time guard or by using Windows wall-clock authority.

A legitimate future *source-only* improvement would require an independently issued and same-process authenticated **sub-second UTC monotonic-anchor clock sample**, verify that precision via the original selected clock and account owner, then assess full UTC timestamp interval including uncertainty. A price timestamp alone cannot prove a quote was observed before receipt; any arrival-order uncertainty and NTP bound remain conserved. This is NOT installed in R21. No source freshness condition, quote price, one-venue executable fill or current original market-source rights were forged by this execution.

## First-party provider context

The Alpaca official docs `https://docs.alpaca.markets/us/docs/about-market-data-api` describe the free Basic Trading API for personal users as **IEX-only for real-time equities**, 30 WebSocket symbols and no all-exchange SIP NBBO. Their `https://docs.alpaca.markets/us/docs/paper-trading` describes free paper simulation and paper-only account IEX data eligibility. Atlas's authenticated REST calls prove this original API credential can GET these four IEX latest quotes, but DO NOT independently prove all client/account licensing restrictions, operational financial source publication, firm-issued fair-value estimates, exchange-wide execution quality, or native PAPER approvals.

Hyperliquid real original R21 public data-only completed-hour funding REST check already obtained 3 coins x3 funding records in a prior receipt. Per official `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals`, public `fundingHistory` supplies `coin`, `fundingRate`, `premium` and `time`; it does not provide an independently signed original hourly settlement-time consensus oracle. Public base fee rates do not provide user-account-specific fees. The original historical S3 archive is requester-pays; user's free-data policy forbids purchasing it.

## Operational PAPER state

R21 code-only installation and selector are verified, as are its real Windows Job, exact 5 QD + 7 HL writer roster, NTP, the two source-only original SEC-watch and source-epoch-readback modules, and authenticated one-venue IEX transport during regular market hours.

**Still not accepted/commissioned:** current originating QD executable valuation issuer with original independently sourced estimates; actual source rights and approved financial quote semantics; original 2 preinception coordination journals; original initial READ_ONLY+INITIALIZE_SIMULATED_ACCOUNTS activation; exact two once-only $1,000 USD and 1,000 USDC native simulated inceptions; distinct post-inception CONNECT_APPROVED_DATA activation and original native research source genesis; accepted multi-epoch original source readback+reader switchover beyond 127 publications; Hyperliquid historical settlement-time signed consensus oracle and account-specific fee evidence; separately granted STOP-FIRST AUTO_PAPER+SHUTDOWN_FLATTEN activation, native owned financial session and emergency Stop/flatten/restart acceptance. Legacy desktop readiness checker is intentionally hardcoded NO_GO; it is not a dynamic progress percentage. The original financial roots remain 12/12 empty. PAPER financial trading and LIVE capital remain disabled.

**Next valid action:** engineer and independently verify original trusted sub-second NTP sample and formal free IEX quote licensing/session admission; separately resolve genuine originating valuations and Hyperliquid funding settlement provenance *before* first financial account initialization. Do not bypass existing source/financial admission on the basis of IEX HTTP GETs or SEC-only WATCH research. Keep all generated logs, tests and documents only under main D-project, preserve existing protected D native roots and do selective Atlas C-temp cleanup after execution.
