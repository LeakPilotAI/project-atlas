# Atlas Hyperliquid historical settlement oracle original-consensus guard — 2026-11-09

**Status: versioned operational source/financial-planner admission strengthened OFFLINE; no genuine settlement oracle provider/issuer yet. PAPER NO-GO.**

## Verified provider semantics and original blocker

The Hyperliquid official info API `fundingHistory` returns `coin, fundingRate, premium, time`: **no historical settlement oracle price**. The separate `metaAndAssetCtxs` `oraclePx` is a **current** market value, not evidence for an hourly funding settlement already past. Public candle, mark, and ticker prices are also not substitutes. HyperCore funding cash is based on an oracle price in force when the actual funding event settles, and historical oracle provenance needs a block/action cut or independently authenticated equivalent. Official API references: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals and https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle .

Before this milestone, the original `PerpSourcePublication.prepare_capture` accepted a tiny five-field `{symbol,settlement_at,price,source_id,revision}` historical oracle packet if a separate injected verifier returned `True`. That packet had **no event times, original consensus block/action references, or rate tie**. The original `PerpSourcePlanner.next_proposal` similarly accepted a rate history and an arbitrary alleged oracle from its source if its authority returned `True`. On an operational financial source, neither shape should be enough to state that it is the correct hourly oracle.

## Exact source-only implementation

Added `backend/app/services/hyperliquid_consensus_settlement.py::require_consensus_settlement_oracle` with strict source schema `HL_CONSENSUS_SETTLEMENT_ORACLE_V1` for the configured native HyperCore BTC/ETH/SOL perps. The original packet MUST now declare: instrument, USD-like settlement price, UTC hourly settlement, exact rate, positive source revision, original oracle update and funding settlement block heights, original event timestamps, separate 64-digit lower-hex action digests, and fixed venue. The source must show oracle event occurred at or before settlement event/block, oracle update within 60 seconds before the hour, and funding settlement in the first 30 seconds after the hour. It must tie the exact `funding_rate` to the same original hourly rate record from the existing strict public `fundingHistory` parser, **without interpreting `settlement_oracle=None` as zero**. Invalid type/shape, changed rate, missing original event, late/out-of-order event, future oracle, or current-only quote refuses. This is a **deliberately strict operational contract**, not a claimed fact that the free provider exposes these historic values.

The guard is called for `PAPER_EPOCH_PERP_OPERATIONAL_V1` at BOTH:
1. `backend/app/services/paper_source_publication.py::PerpSourcePublication.prepare_capture` before accepting and archiving an alleged historical oracle;
2. `backend/app/services/perp_source_planner.py::PerpSourcePlanner.next_proposal` on any due financial funding event, BEFORE invoking the separate issuer verifier or proposing a PAPER funding command.

**CRITICAL:** These checks validate claims' structural/temporal consistency only. `source_id` and SHA256-like action digests alone are not proof of signed consensus or completeness. The existing independent `verify_settlement` and `verify_settlement_source` authorities MUST verify original event provenance, last oracle update in force, source rights, issuer custody and authenticity, matching confirmed on-chain actions, provider identity and financial clock before operational acceptance. No such trusted source has been provided or commissioned. This source update **cannot independently verify the actual latest oracle in force**. It prevents unproven abbreviated/current-oracle input from silently becoming a financial funding command.

Disposable `PAPER_EPOCH_PERP_FIXTURE_V2` remains untouched: synthetic five-field historical oracle and prior event/ledger/report replay continue for existing tests. Existing R12 installed native files remain unchanged, so this commit is not a selected financial runtime update.

## Tests

Added `tests/test_hyperliquid_consensus_settlement.py`: strict synthetic versioned oracle with original block timing; 17 malformed/mismatched claims; 4 inconsistent funding-rate rows; actual `HyperliquidCurrentProducer` existing publisher fixture confirms operational five-field rate+price refusal, independent authority still required even when event fields are shaped, and disposable old publisher capture still reads the historical fixture; original `PerpSourcePlanner.next_proposal` exercised via isolated in-memory ports ensures invalid event proof never calls the issuer nor proposes funding, and valid synthetic shape still needs/uses issuer verifier.

Expanded existing current producer, strict funding publication lag, funding recovery, core perps finances, operational modeled fees and book refusal suite: **183 passed, 0 failures/skips** after intermediate fixture-port correction. AST parse of all four edited/created Python files passed. `git diff --check` passed.

## Unfinished critical path

A verified original HyperCore consensus stream or approved free historical oracle source, containing original price action and hourly settlement action with independently qualified timing and fees, still needs source enrollment and acceptance. The public `fundingHistory` endpoint alone cannot supply it. The next operating milestone is genuine provider rights and bounded data sampling through a reviewed current native source and qualified financial clock, followed by independent USD/USDC account inception, owned long-running financial writer and supervised Stop/flatten. The historical V4/V5 HL public request budgets remain exhausted and must never be silently reset. Full financial PAPER is **NO-GO (0/9 independently accepted workstreams)**.

No credentialed provider/wallet/real funding session, simulated or live financial order, paper account mutation, native selected R12 installation, Windows clock/shortcut/boot, VPS, Genesis, or GitHub push occurred.
