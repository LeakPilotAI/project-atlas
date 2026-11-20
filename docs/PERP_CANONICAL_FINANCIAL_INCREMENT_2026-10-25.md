# Canonical perpetual accounting increment — 2026-10-25

Base: f21f046fda215c29adff2f295c30f09d5435b385, branch
chatgpt/atlas-rebuild-v1. This is verified disposable engineering, not completion
of UNIFIED_PERP_FINANCIAL_COMPLETENESS or independent operational acceptance.

## Implemented in the existing financial system

`paper_financial_replay.py` explicitly dispatches the new
PAPER_EPOCH_PERP_FIXTURE_V2 / PAPER_PERP_COMMAND_V2 / PAPER_PERP_RECEIPT_V2
contracts to `paper_perp_transition.py`. Existing V1/manual/Quality Dips branches
and golden records remain supported. No second ledger, operational codec, issuer,
startup path or order route was created.

The new USDC-only fixture contract records hypothetical inception; long/short
entries; leverage and entry notional; initial margin reservation/release; partial
and final exits; separate entry/exit taker fees and cash-modeled slippage; explicit
hourly oracle-based funding on the quantity actually remaining; mark valuation,
maintenance requirements and funding-aware margin warnings. Book sides depend on
position direction: a long buys ASK/sells BID; a short sells BID/buys ASK.
Observed prices are not also adjusted for cash-charged modeled slippage.

Exact risk R is retained as a rational numerator/denominator. Only the explicitly
labeled display value may round; the 3R entry stop compares the exact ratio.
Money and quantity calculations still refuse unsupported arithmetic precision.
Evidence/clock/revision/liquidity conflicts refuse without mutating input state.

`paper_financial_audit.py` independently derives cash, costs, funding, margin,
inventory, source continuity, exact R and mark-risk values without calling the
transition. The existing EpochFixture transactions and native FinancialRecordStore
consume the new contract. FS2 event/receipt/intent/commit/ACK and FS3 native
projection/report interfaces are reused without changing their test-pin identity.
These remain explicitly disposable records; they cannot become operational pins.

`paper_daily_report.py` adds a version-3 report path with separate USDC cash,
funding, fees/slippage, reserved/available cash and remaining positions. Missing
funding intervals prevent COMPLETE reporting. Calendar boundaries include 23/25
hour New York DST days. COMPLETE financial reporting does not imply flat positions
or clean process shutdown; lifecycle remains NOT_EVALUATED. Valuation is unavailable
in the daily report rather than an invented equity total. Existing report bytes
remain protected by regression goldens.

## Real provider interface, not verified live evidence

The existing HyperliquidAdapter now has explicit read-only
`paper_execution_observation` and `paper_funding_observation` methods. They require
an already-created client, injected clock and existing durable request gate. No
gate, client, wallet, key or subscription is installed by these methods.

Fixed public /info requests cover metaAndAssetCtxs, l2Book and a bounded <=24-hour
fundingHistory window. The parser preserves Decimal strings and rejects missing,
stale, future, crossed, duplicated or mismapped book/history evidence. Current mark,
oracle and indicative funding are distinct from executable book prices and settled
funding. Public funding-rate history does not supply historical settlement oracle
prices; fee/account-tier acceptance is also absent. Those fields remain unavailable
and financial_execution_authorized remains false. No live Hyperliquid probe ran.

Primary references inspected: [funding and hourly oracle payment semantics](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding),
[public book schema](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint),
[perpetual metadata and funding history](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals).
Documentation is not provider-rights acceptance or authenticated account fee evidence.

## Validation and retained failures

Final combined selection: **476 passed, 0 failed, 1 skipped** (125.52s (0:02:05)).
The skip is NOT EXECUTED: Windows true-symlink privilege unavailable (1314).
The three new files contain 63 cases (31 canonical/report, 10 native, 22 public
book/funding). Counts are one combined run, not added overlapping runs. Native
long/short partial/funding/full exits, immutable report retries, six abrupt owned
child boundaries, UNKNOWN, concurrent canonical retries and V1/QD goldens passed.
Targeted Ruff passed; Hyperliquid adapter retains eight inherited findings, zero
new changed-line findings. Nine changed Python files compile. PAPER static audit:
577 runtime files, zero issues. No JS/UI/PowerShell source changed; no new browser,
GUI, actual-provider, power-loss or 24/7 operational acceptance was executed.

The original unsupported-USDC-schema failure was reproduced before implementation.
Two later adversarial failures exposed repeating-R arithmetic refusal and omitted
funding loss in margin warnings; both were reproduced and repaired. A sandbox
temporary-directory failure and an intermediate native regression failure caused
by missing ATLAS_D1_ATTEMPT were retained. The environment was corrected without
changing existing assertions. Earlier runs are not summed into final counts.
Private evidence pointers: logs/diagnostics/perp-financial-v2-current.txt and
logs/diagnostics/perp-native-v2-current.txt; none of those financial fixtures,
machine identities, subprocess records or logs is eligible for Git publication.

## Exact limitations and next work

This increment is INCOMPLETE against the complete perpetual runtime requirement.
Margin is an initial conservative reservation with cash-settled funding allocation,
not authenticated exchange withdrawable collateral. Flat synthetic maintenance
rates are not accepted exchange margin tiers. Maker fills refuse without a queue/
trade-evidence model. LIQUIDATION refuses rather than manufacturing an execution.
Scale-in/unfinished multi-fill entry orders, late historical funding recovery,
bankruptcy/backstop treatment, dynamic tiers, independently authenticated fee/rate/
settlement-oracle policy and operational perpetual codec admission remain unfinished.
Exact-hour entry/exit ordering without independent sequence evidence refuses.

The unified supervisor still has synthetic lane/custody financial ports. It does
not yet serialize FUNDING/MARK through canonical durable portfolio reservations.
Real scanner-to-writer adapters, complete writer ownership/drain and financial
dashboard consumption must be completed before unified runtime readiness claims.
No new browser/Control Center/24-hour soak was executed in this increment.

B1/C1/D1/E1 remain BLOCKED. Proposed accounts remain separate 1000 USD Quality
Dips and 1000 hypothetical USDC Hyperliquid; neither inception was published.
The fixture's notional/leverage choices are not operator-approved perpetual limits.
Real provider rights/budget, executable data, fee/margin/funding policies, conversion
evidence, custody/clock/issuer/writers and separate provisioning/inception/session
permissions remain required. The 13 real directories, Genesis, original UI,
startup locks, all seven roadmap phases and 21 decisions are unchanged.
PAPER startup NO; production NO-GO; no power-loss or independent custody claim.
