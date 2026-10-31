# Unified multi-market PAPER integration — 2026-10-25

## Disposition

Source/disposable foundation verified; **complete operational integration is not
finished**. PAPER startup NO; production NO-GO. No operational account was
initialized and no real-market simulated trade occurred. All 21 historical gate
decisions, strict/manual contracts and seven roadmap phases remain unchanged.

The operator selected separate strategy accounts: Quality Dips **1,000 USD** and
Hyperliquid **1,000 hypothetical USDC**. These are proposed inception amounts,
not existing balances, funding transfers or independent acceptance. USDC is not
silently converted into USD. No combined cash/equity total is published.

## Implemented changes

| Component | Verified implementation | Remaining boundary |
|---|---|---|
| `investment/quality_dips_market_roster.py` | Bounded fixed-source public directory downloads; strict source-cut/schema/duplicate/flag checks; explicit exchange and symbol aliases; bounded research pages; actual `InvestmentUniverse` adapter requiring verified stock/ETF metadata; stable ranked IEX selection with open-position pins | Directory membership is research reference only. Instrument metadata, corporate actions, halts, source rights and authenticated current ranking remain separately required. No scanner/provider is started on import or GET. |
| `investment/alpaca_iex.py` | Independently supplied open-position symbol inventory required for rotation; immediate cache invalidation; exact new subscription ACK; old socket closes before new connection; 30-second minimum active rotation spacing; provider limit errors remain terminal | Client ceiling 30 is not proof of subscription entitlement. Actual observed subscription remains two symbols. |
| `services/paper_portfolio_risk.py` | Explicit versioned allocations, gross exposure, loss, concurrency and leverage limits; complete fresh two-account cuts; no duplicate/conflicting positions or double capital allocation; separate USD/USDC; signed funding/equity/fee/slippage consistency and margin buffer checks | An injected accepted custodian must authenticate cuts, conversions, source completeness and the policy. No default portfolio allocation or operational custodian exists. |
| `services/unified_paper_runtime.py` | Independent concurrent lane observation; closed stock sessions do not stop perpetual monitoring; no signal is healthy idle operation; bounded continuous supervision; exact installed-component lease; exclusive-custody/reservation/ACK ports; UNKNOWN/restart refusal; separate read capability; existing Control Center Stop response/transport contract | Lane financial planners, verified current-cut projection, durable cross-process portfolio custody and actual owned-process bindings must be supplied and accepted. Synthetic test doubles are not installed authorities. |
| `services/paper_market_observers.py`, `adapters/hyperliquid.py` | Read-only adapters over actual IEX/Hyperliquid caches. Hyperliquid mark snapshots explicitly lack executable bid/ask and settled funding history. No cache read starts/refetches a provider | Existing Hyperliquid public request gate remains default-denying; no live Hyperliquid observation was executed in this milestone. |
| Selected router/read host, original HTML/JS and Windows controls | Optional narrow unified read capability on existing selected GET; two market/session/signal states and explicit unavailable totals; existing styling/navigation; no additional poll or mutating research fallback; optional Control Center status; Stop compatibility with existing authenticated local transport | No operational registration, installation, default accepted session or native GUI activation. Genuine read-only HTTP/browser fixture executed; new unified control POST verified with ASGI transport, not an actual WinForms click. |

Entry checks retain the explicit $100 limit. A paired **EXIT-only** proof allows
an acknowledged appreciated position or margin-warning position to be reduced:
no new position identity, side reversal, quantity/exposure/risk/reservation
increase, account substitution or UNKNOWN evidence is allowed. Actual executable
prices, accepted strategy decisions and financial acknowledgements are still
required. A first broader patch was rejected by automatic approval review for
removing the entry cap; it was not applied. The accepted revision preserves the
entry check and tests the paired reduction path separately.

Normal Stop closes global new-entry admission before draining either lane and
delegates to accepted lane shutdown coordinators. Only explicit acknowledged
flat-and-drained outcomes from **both** lanes can yield FLATTENED. Missing prices,
UNKNOWN, disconnected feeds and emergency Stop cannot claim clean flattening.
No process name/port termination, process discovery or forced kill is introduced.

## Actual public-data observations

Two fixed HTTPS GETs retrieved Nasdaq's public symbol directory files. Both
reported provider-local source cut `1023202621:31`; no UTC timezone is invented.

| Source | Raw reference rows | Retained research references | Excluded | ETF-flagged retained |
|---|---:|---:|---:|---:|
| nasdaqlisted.txt | 5,625 | 5,274 | 351 | 1,289 |
| otherlisted.txt | 7,674 | 7,492 | 182 | 4,482 |
| Total | 13,299 | **12,766 distinct symbols** | 533 | 5,771 |

Non-ETF rows are EQUITY_REFERENCE, not guessed common-stock execution eligibility.
Symbol aliases are preserved rather than punctuation-guessed. OTC, unsupported
namespaces/exchanges, test issues and nonnormal Nasdaq status are excluded.
**Verified executable universe size is not established**; every directory row
has execution_eligible=false. This is not Robinhood coverage, actual ranking of
12,766 symbols, complete corporate-action history, or simultaneous live coverage.

Sources: [Nasdaq directory definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)
and [SEC filing SR-NASDAQ-2026-062](https://public-inspection.federalregister.gov/2026-16097.pdf).
The latter describes certain public FTP information as free for any purpose;
this is not blanket acceptance of every third-party field, historical provider,
continuous research usage or redistribution entitlement. Deployment use-rights
review remains explicit. HTTPS/content binding is not a financial issuer signature.

An additional **8-second real IEX observation** authenticated and received exact
MSFT/SPY subscription acknowledgement, with **0 quote messages, 0 reconnects**.
Observation ended at Unix UTC `1792925196.6646714`; socket closed normally. Sunday
market closure means fresh bid/ask, exchange timestamp and latency remain
UNAVAILABLE. No brokerage/account/order endpoint was contacted. Credentials stayed
in the existing ignored file; no credentials were printed or published.

## Validation

- Final combined selection: **180 passed, 0 failed, 0 skipped**. It covers the four
  new test files and Alpaca, existing autonomous accounting, trading-domain,
  native read-service, passive Windows GUI source and production-lock regressions.
  **63 new cases**; this is a selected regression suite, not every repository test.
- Frontend: **40 passed, 0 failed/skipped**, including 3 new multi-market cases;
  DOM/fetch tests do not replace the separate genuine browser observation.
- Windows PowerShell: **5 behavior assertions and 2 syntax checks passed**. No
  real WinForms window/action or operational process shutdown was exercised.
- Genuine owned native loopback HTTP: included in the combined run. Synthetic
  source/projection/report bytes compared exactly before/after reads and owned
  graceful closure. Command POST refused; legacy mutating research GET absent.
- Genuine in-app browser: saw stock CLOSED / perpetual OPEN, two healthy synthetic
  connections, no validated signals, and unavailable consolidated amounts. Existing
  financial fixture timestamps were stale to the real browser: amounts correctly
  remained UNAVAILABLE. After the host closed, Refresh showed all financial/market
  data UNAVAILABLE. These are disposable observations, not operational scanner or
  trade evidence. A final table overflow wrapper was added after the capture;
  final JS/DOM assertions passed, but that wrapper was not separately browser-soaked.
- Compilation of 8 changed runtime Python modules, JS syntax, targeted Ruff and
  static PAPER policy scan passed. Scan: **576 runtime files, 0 issues**. The
  existing Hyperliquid adapter retains **8 inherited Ruff findings, 8 before/after,
  0 new changed-line findings**; it is not described as whole-file lint-clean.
- Initial sandbox async run stalled after progress output and was interrupted via
  its exact test session, not process-name termination. One native HTTP attempt
  correctly skipped without its required explicit confinement variable; another
  selection typo collected zero tests. These outcomes are retained privately,
  not counted as final passes. Native permitted reruns produced the results above.
- No new true-symlink/restricted-token attack, power-loss, 24/7 soak, regular-session
  quote, live Hyperliquid feed, actual Genesis coexistence or operational acceptance
  result is claimed. Original evidence and preexisting untracked work are retained.

Private evidence pointer: `logs/diagnostics/unified-paper-current.txt`. Raw public
directories, machine/process identities, native fixtures, screenshots, credentials
and test logs are excluded from Git publication.

Native margin stress is explicitly denominated in USDC; the separate portfolio
loss ceiling is USD. No USD loss is subtracted from USDC collateral. Both existing
USD risk constraints and the proposed native USDC ceiling remain; accepted
conversion evidence is still required. An earlier documentation currency-change
patch was rejected and not applied; the accepted correction preserves currencies.

## Concrete unfinished work — not another completed-demo claim

1. Extend the **existing** Hyperliquid canonical financial contract/replay/audit
   and native publication path with independently reconcilable collateral,
   margin reservation/release, partial-position funding settlements, maker/taker
   cost evidence and mark-based liquidation-risk reporting. The current selected
   handoff explicitly has funding_modeled=false; existing R/P&L is not proof of
   correct leveraged cash accounting. No replacement ledger should be built.
2. Bind actual existing QD/perp strategy planners and financial writers to the
   unified admission ports under a complete cross-process writer/custody lease.
   Current tests use synthetic ports; genuine read HTTP does not prove unified
   financial dispatch is complete or atomic across stores.
3. Supply authenticated Hyperliquid executable book, mark, funding history,
   instrument units, margin tiers and fee schedule, with accepted provider rights
   and bounded request budget. Existing mark/allMids values must never become
   fabricated executable prices or funding settlements. Funding is hourly;
   initial margin depends on leverage, and liquidation risk uses mark evidence:
   [funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding),
   [margin](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining),
   [liquidation](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations).
4. Complete metadata/current-ranking/corporate-action/halts/calendar authority and
   rate-bounded existing research scanner wiring; validate actual regular-session
   IEX price/size evidence. Do not label public reference discovery as eligible fills.
5. B1: independent two-account scope/inception/historical exclusion disposition.
   C1: actual complete writer/resource/process ownership, drain and exclusion.
   D1: accepted issuer/session, clock/current custody and recovery, with explicit
   same-user/D:-only limitations. E1: provider rights, recovery and supervised trial.
   All remain BLOCKED; no gate is self-promoted by these tests or preferences.
6. Only after those prerequisites: separately authorized actual resource/dependency
   installation, QD inception, separately enrolled Hyperliquid account resources,
   approved data access and bounded supervised launch. Existing 13 QD directories
   were not accessed or changed. No new account, key, ACL, service or bridge installed.

The next engineering continuation is the first item, not a repeat of directory,
dashboard or IEX authentication demonstrations. It remains unfinished work, not
an external approval falsely presented as an implemented financial capability.
