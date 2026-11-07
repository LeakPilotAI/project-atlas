# Hyperliquid PAPER partial-position V2 — offline contract

Base: eac71e591aef3c427fe8f1c32d9105efe0357a06, branch chatgpt/atlas-rebuild-v1. Local tracked tree initially clean. No applicable backend repository instructions found; frontend is untouched. This milestone is explicitly authorized source development and disposable integration, not protected runtime integration or PAPER startup.

## Scope and identity

Reuse BTC/ETH/SOL, existing 1 USD risk, maximum three positions, manual-only entry and existing 3R session stop. This adapter creates no entries, changes no risk controls and grants no authority. Existing entry guards remain mandatory. Exit price evidence must identify the matching symbol and source, be fixture-verified, no more than 30 seconds old, and not future-dated. Finite positive exact-decimal quantity/price and nondecreasing execution timestamps are required. Funding, margin, venue liquidation, actual balances and unrealized equity are not modeled.

Shared position identity is `hl-fixture-v2:` plus SHA256 of canonical JSON containing explicit fixture namespace and immutable original trade UUID, symbol, side, entry price, risk price, initial quantity, fee/slippage rates, entry clock and currency. Mutable journal revision/hash does not alter the identity. A new namespace or trade UUID does. This is a deterministic local correlation contract, not proof of ownership or authenticity.

The V2 baseline separately pins the journal SHA256/row revision, manual snapshot SHA256 and complete selected open-position inventory. The caller first uses actual ManualPerpStateStore.load to reject pending/temp publications and verifies supplied source bytes with the existing handoff contracts. No function discovers or opens native runtime paths. Baseline sidecar initialization is exclusive; a partially initialized store fails subsequent reads rather than resetting itself.

## Versioned events and financial semantics

`HYPERLIQUID_PARTIAL_REQUEST_V2` requires explicit position ID, stable fill ID, expected global sidecar revision, exact decimal quantity, timestamp, session ID and source-bound price receipt. Unknown fields/schema versions, stale revisions and changed duplicate requests refuse. The same fully acknowledged request returns its stored receipt without applying the fill again, including after restart. Reusing an ID with different financial content refuses.

`HYPERLIQUID_PARTIAL_EVENT_V2` stores the request, exact existing `PAPER_PARTIAL_FILL_V1` ledger row, derived accounting, monotonically checked local revision, previous digest and event digest. Replay verifies intent/event equality, identity, sequence, digest chain, every original position, every committed fill, independent finalization accounting and recorded remaining quantities. Missing, extra or contradictory ledger evidence refuses. A digest chain is tamper detection against unmatched changes, not authenticated authority or independent rollback resistance.

Existing `replay_partial_fills` remains the accounting producer. Original size and entry cost basis are retained; only committed exits reduce remaining quantity. Fees and slippage keep the existing 2bps/2bps per-side entry-notional convention. Entry costs are allocated per closed quantity, not charged again on retry. The V2 view exposes separately allocated entry fee, exit fee, entry slippage and exit slippage, remaining entry notional, realized currency P&L and trade-R on original risk. Partial fills are neither new positions nor a second risk allocation. Eventual full close requires the existing ledger's fill and finalization commit plus a durable V2 acknowledgement.

## Cross-store protocol and failure handling

1. Lock the sidecar transaction, verify pinned baseline, all prior acknowledged operations and isolated ledger consistency.
2. Validate the new request and replayed remaining quantity before mutation.
3. Commit a durable PENDING intent before invoking the existing ledger append. One pending operation blocks every new adapter mutation and projection.
4. Existing isolated ledger commits the fill and, at zero remaining quantity, final exit in its own SQLite transaction.
5. Commit the V2 acknowledgement only after validating both stores and independent exit accounting. Publish success after this acknowledgement commit.

There is **no transaction spanning both stores**. An interruption after intent and before acknowledgement remains unresolved even when a fill can be read from the ledger. No automatic callback replay, deletion, uncertainty clearing or synthesized acknowledgement is provided. A failure after the acknowledgement commit may return its exact durable receipt on identical retry, with no financial callback. Before-intent interruption permits a fresh request because no durable operation began.

The adapter serializes cooperating fixture calls and explicitly closes its own SQLite connections. It does not exclude independent clients, privileged actors or other native writers. A coordinated rollback of both stores cannot be detected without an independent revision witness. These limitations keep C1/D1 blocked. Real power-loss durability, filesystem/sidecar identity and protected publication are not accepted by subprocess tests or SQLite FULL alone.

## Native V1 compatibility and truthful views

PaperJournal, ManualPerpStateStore, their singleton behavior, V1 record formats and actual callers are unchanged. Existing full-close rows still reconstruct through the original handoff reader; no historical event is rewritten. V2 events live in a separate disposable sidecar, never in a V1 stream that an old reader could silently misinterpret.

`HYPERLIQUID_PARTIAL_VIEW_V2` exposes OPEN, PARTIALLY_CLOSED or CLOSED_FIXTURE_LEDGER_ONLY. Every position retains its native UUID, original cost basis and baseline source status. Native journal OPEN/manual ENTERED remain explicit even after the isolated ledger reaches zero; `native_positions_flat` stays false. These are **baseline states**, not fresh observations of a running native service. No native full-close at the final partial price is fabricated. Production integration needs a separately approved native representation/migration and writer contract before V2 can replace V1 state.

The fixture report wrapper first requires a fully acknowledged, independently reconciled V2 state with no remaining quantities. It then uses existing immutable daily cash reporting and returns a V2 receipt binding the baseline, event revision and digest to that report. Pending, corrupt or incomplete handoffs cannot use this wrapper to claim a complete session. It grants no operational shutdown authority and cannot exclude external mutations between reads/publication. The receipt is a consistency envelope; it is not an authenticated witness or a cross-store atomic report publication.

## Acceptance evidence and continuation

Initial failure: normalized handoff positions do not retain native `risk_dollars`; corrected exit scope validation to derive original risk from quantity times risk price. Retained logs/diagnostics/hl-partial-v2-first.txt. Second failure: exact Decimal numerical value compared with a differently scaled string; corrected test to compare Decimal values without changing financial arithmetic. Retained hl-partial-v2-second.txt. First successful selection:28passed; extended integration:31passed. Those overlap, are not additional distinct cases, and are not the final validation of later source edits. Targeted Ruff findings (unused import, shadowed test arguments and import formatting) repaired mechanically without suppressions.

Actual source classes run only through the previously reviewed singleton-omitting fixture loader and explicit disposable paths. Tests cover BTC long/ETH short/SOL long, fractional partial/final quantities, duplicate callbacks, stale/future prices, over-close, missing/foreign identity, corrupt baseline/event/fill/position/finalization, simultaneous calls and three-position reporting. Abrupt own-child exits exercise before-intent, after-intent, ledger partial/before-commit/after-commit, before-ack, before-ack-commit and after-ack boundaries. Interrupted write exceptions preserve original exception context and pending intent. No global or unrelated process termination occurs.

Fixture totals are deterministic assertions, not performance evidence: one 0.5-unit position partially exits 0.125 at +2 and 0.375 at +4 (directions reversed for short); net 1.71 USD after unchanged costs. Three positions yield 5.13 USD and declared fixture closing cash 1005.13 USD. No real records, providers or account balance claims.

L1 is the isolated versioned contract; L2 is failure/restart and actual-interface fixture acceptance; L3 is final combined validation, history-preserving checkpoint and reviewed Git publication. Exact final results and checkpoint receipt are appended after the final run. Earlier overlapping results must never be summed.

## Remaining approval dependencies

B1 independent complete source/opening exposure/cash archive; C1 actual process/writer/resource ownership and drain; D1 protected storage, trusted authorization, clock and rollback; E1 controlled runtime integration, provider rights/budgets, backup/restoration and explicit operational acceptance remain BLOCKED. All 21 decisions remain unchanged. Python/Windows startup refusal is unchanged. Phase2 HOLD, Phase3 BLOCKED, production NO-GO; actual PAPER startup authorization NO.

Next approval dependency: independently review this V2 representation and authorize controlled integration design for the selected native journal/manual writer boundaries, including durable shared IDs, acknowledged fill revisions and all-writer shutdown admission. This source-development approval does not grant that integration or migration. Obtain B1/C1/D1 evidence and provider/operational acceptance in parallel. No additional startup exemption is proposed.


## Verified final validation
One exact-final-source combined run:379passed,0failed,0skipped in92.56s,including34newV2cases (hl-partial-v2-final.txt). Earlier379pass run preceded connection/exit-validator refinements and is retained separately; not added to final count. Earlier28/31focused runs overlap. No JS/frontend changes; prior763JSnot rerun. Ruff2files,compile2files,checkpoint PowerShell parser and CRLF-aware diff checks pass. The normalized risk-key defect,Decimal assertion-scale failure and targeted lint outputs were repaired; original logs retained. No remaining failed/skipped cases in final selection.

Original8native/store/risk/governance source contents match base;paper_risk.py has existing Git-checkout CRLF conversion only. Raw canonical21decision andstartup-lock hashes remain unchanged. No original store code was modified. L2 checkpoint: {"stage": "hl-partial-v2-L2", "backup": "D:\\Work\\Project Atlas\\PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261023-211125-2b4cfc3d.bak", "backup_equal": true, "exact_readback": true, "outside_managed_equal_to_base": true, "roadmap_sha256": "b48ee64d3456ad5406f64c6a116da369d551d7ae33a84c0b6e77bcc2c6f9d6ab"}.

Final roadmap checkpoint: {"stage": "hl-partial-v2-L3", "backup": "D:\\Work\\Project Atlas\\PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261023-211126-329b422e.bak", "backup_equal": true, "exact_readback": true, "outside_managed_equal_to_base": true, "roadmap_sha256": "8421fb89d036519c9ab3febffc24634a852ae4356f506e0fb52df00bc018ca0c"}. Exact backup/input readback and all bytes outside managed section match the base commit. Complete seven-phase roadmap and canonical21decisions retained.

Files changed:backend/app/services/hyperliquid_partial_fixture.py;tests/test_hyperliquid_partial_fixture.py;this contract/continuation;PROJECT_ATLAS_MASTER_ROADMAP.txt;docs/ATLAS_AUTONOMOUS_STATE.json;docs/ATLAS_AUTONOMOUS_EXECUTION_QUEUE.md;docs/PAPER_FIRST_SESSION_DEPENDENCIES_2026-10-23.md;docs/DAILY_PAPER_21_GATE_READINESS_2026-10-23.md. Only these8reviewed files eligible for Git publication. Local failure logs,generated fixture financial examples,backups and unrelated files remain excluded.
