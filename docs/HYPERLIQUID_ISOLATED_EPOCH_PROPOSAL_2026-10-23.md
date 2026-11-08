# Independently isolated Hyperliquid PAPER epoch — conditional feasibility

Base: 2caa50ec2081c7f8a1f27799df2a9783f2090f48, branch chatgpt/atlas-rebuild-v1.
Decision: **CONDITIONAL technical feasibility; implementation proposal only. PAPER startup NO. Production NO-GO.** B1/C1/D1/E1 remain BLOCKED and all 21 decisions remain unchanged. Phase 2 HOLD; Phase 3 BLOCKED; AFI-1–10 PENDING.

## Scope and evidence

The complete master roadmap was read, with permanent strategy/recovery instructions reconciled against the latest managed checkpoint, queue, state, N1 facade, final controlled-runtime proposal and acceptance checklist. The private N2 discrepancy report was reviewed locally. Its source identities, counts, dates, hashes, financial figures and detailed discrepancies are deliberately omitted. No additional real financial source reads or application initializers were needed. Existing local findings remain unresolved; this proposal does not certify their completeness or replace them.

A new simulated accounting epoch can be distinguished from historical migration only if its inception explicitly declares **new hypothetical capital**, not recovered money, a deposit from an old account, or proof that old exposure is flat. The proposed 1000 USD is a simulation parameter requiring separate acceptance, not a source fact. No legacy position, balance, loss, cashflow or unresolved obligation moves into or disappears because of the epoch. Historical records retain their original status and provenance. Investment, prediction, shadow and other PAPER lanes remain separate.

The present proposal does not override the prior N2-C prohibition on a fresh account evading B1. An independent governance reviewer must decide whether a separately scoped new-epoch acceptance is permissible under existing decisions. Until that decision and its required evidence exist, B1 remains a startup dependency. Codex does not issue a scope exception, acceptance signature or authority token.

## Minimum inception and isolation contract — proposed, not provisioned

An accepted inception manifest must bind contract version, unique epoch ID, immutable release/configuration digest, explicit simulated opening amount/currency, creation/cutoff clock, report IANA timezone, cost policy and instrument/quantity units. Bind canonical resource identities and their independently verified disjoint paths, projection/report namespaces, allowed writers and manual session scope. No implicit default paths, legacy fallback, balance inference or restart-as-new-epoch reset. Approval of the manifest is distinct from storage provisioning, runtime wiring and startup.

Preserve existing 1 USD simulated risk, maximum three positions, manual-only BTC/ETH/SOL, stricter applicable 3R day/session stop and conservative 2bps fee/2bps slippage per side assumptions. An epoch boundary cannot reset accepted day/session risk restrictions. Missing independently accepted risk baseline refuses. Instrument precision, tick/lot units, mark choice, funding/margin exclusions and USD versus other currency semantics must be explicitly accepted; no unsupported equity or valuation claims.

Storage isolation must cover canonical events, operation intents/receipts, manual projections, cash evidence, inventories, daily reports, session/writer registries, audit/recovery records, caches and locks. Path separation alone does not prove ownership, absence of hard links/reparse points, writer exclusion or rollback resistance. Verify identity before access under the accepted N4 design. Deny legacy readers/writers from resolving to this namespace and deny new writers from resolving to old namespaces. Do not automatically create missing operational stores or copy fixture databases into them.

## Canonical authority and lifecycle

Reuse the final proposal's single logical `ATLAS_PAPER_CANONICAL_V1` event authority. Canonical IDs must include the accepted epoch and durable operation identity; a position ID is allocated once at committed entry. It is not synthesized from symbol/side or reused across epochs. Distinguish global source revision, position revision and applied projection revision. N1 fill-only revision counters remain V2; do not silently reinterpret them as the all-event source sequence.

One accepted command binds epoch/run, payload digest, expected source/control/position revisions, manual authority, price provenance, quantity, costs and currency. Acknowledgement requires the documented canonical and required projection durability boundary. Identical acknowledged retries return the original receipt. Conflicting reuse refuses. Pending/UNKNOWN financial callbacks are not replayed automatically, even if an upstream error looks harmless. Cross-store fsyncs do not establish joint atomicity. Preserve intent and unacknowledged evidence for independently authorized reconciliation.

Partial and final exits operate on committed remaining quantity, allocate entry/exit costs once, and independently reconcile net currency and trade-R. Zero remaining quantity requires durable committed fills/finalization. Missing/stale prices preserve unresolved positions. Opening cash is an explicit accepted simulated genesis event; realized net cash is derived once per committed fill. Deposits/withdrawals require explicit evidence, not balance edits. Cash is not total equity; open-position valuations remain unavailable unless valid marked evidence exists.

Immutable daily reports bind epoch, original inventory identity/version, canonical cutoff, every fill/cash effect, applied projection revisions and local-calendar boundaries. Report revisions preserve lineage. Clean requires complete inventory, financial reconciliation, acknowledged writes and accepted writer drain. A report or process exit alone cannot authorize shutdown. Distinguish incomplete/failed/timed-out/unknown states, retain unresolved evidence and refuse next-start writes until accepted reconciliation.

Shutdown sequence remains entry admission close -> financial drain -> valid-price remaining exits -> final financial drain -> reconcile/report -> report drain -> verified owned backend exit -> separately approved dependencies. Preserve existing 20s application and 30s manager budgets; no forced kill, deadline extension, unrelated action or Docker Engine/Desktop stop. Parent exit cannot hide active child writers. Cooperative admission does not exclude external clients or privileged actors.

Restart must reopen the same accepted epoch and verify identities, revision pins, source/projection/cash/report consistency, outstanding intents and all-writer state. No empty replacement store, automatic uncertainty clearing, new session risk reset or implicit opening-cash recreation. Hashes detect unmatched corruption, not coordinated machine rollback. Trusted authority, clock freshness and rollback evidence remain independently required.

Version-aware dashboard/API views must display epoch, simulated status, source cutoff/revisions, freshness, incomplete state and remaining quantities. Historical V1 stays read-only and byte-compatible, visibly separate from current epoch. Never sum old and new balances or display legacy administrative terminal records as priced liquidation. No frontend selector or caller-supplied epoch grants write authority.

## File-by-file proposed implementation boundary

All runtime changes below require separate explicit implementation approval; none is implemented here.

| File / existing surface | Next bounded change | Acceptance required |
|---|---|---|
| `backend/app/services/hyperliquid_position_events.py` (planned) | Accepted epoch envelope, genesis/entry/exit/cash events and atomic command receipt boundary | N4 storage/authority decision; canonical schema review; crash/UNKNOWN tests |
| `backend/app/services/hyperliquid_native_runtime.py` (planned) | Route only accepted selected epoch; reject legacy/default paths and cross-epoch IDs | Explicit N5 wiring approval; exact resource identity and no fixture authority |
| `paper_journal.py`, `perp_manual_state_store.py`, `perp_manual_service.py`, `perp_manual_trade_lifecycle.py` | Version-aware canonical routing and applied projections; retain V1 readers and original records | Existing caller compatibility, durable acknowledgements, truthful remaining state |
| `backend/app/api/perp_manual.py`, risk/observability services | Bound manual commands, accepted complete risk/exposure and version-aware views | No automatic entry, no caller authorization, preserve stricter loss limits |
| `paper_writer_fixture.py` and approved future native writer adapters | Reuse tested roster/intent semantics, independently identify every real writer | N3 ownership, incarnation, metadata/report writer admission and native drain |
| `daily_paper_liquidation.py`, `paper_partial_accounting.py`, `paper_exit_audit.py` | Reuse math via accepted canonical adapters | Independent fill/cost/source completeness; no fabricated prices |
| `paper_cash_evidence.py`, `paper_bound_daily_report.py` | Accepted epoch-bound cash/report projections | Genesis provenance, complete source cutoff, timezone and immutable lineage |
| Existing manual/dashboard current readers | Explicit epoch/schema/revision/freshness presentation | No mixed balances, no false FLAT; retained V1 byte reconstruction |
| `backend/app/main.py`, Windows manager/worker and shutdown controls | Only separately approved accepted-path admission and lifecycle wiring | Python refusal remains until formal acceptance; no alternate launcher or unlock |
| Existing provider adapters | Selected authorized feed, explicit budgets and freshness | Rights, collection permission and actual continuity evidence; no connections now |

The existing N1 facade is a disposable reference, not a runtime implementation. It adopts fixture positions; it does not implement a newly authorized operational entry authority. Its fixture namespaces, declared opening cash and harness pins are not independent trust anchors. No source-only defect requiring a runtime change was demonstrated in this stage.

## Disposable acceptance and limitations

New tests reuse actual journal/manual classes only through existing singleton-omitting disposable helpers. They compare retained fixture bytes, separate account IDs, cash and reports; reject cross-account request/baseline/association substitution; and refuse missing opening cash or missing price. They do not initialize real stores or prove protected directory isolation. The fixture helper intentionally retains the old native open position even after a separate fixture overlay closes; this is truthful historical separation, not a successful native migration.

An initial test incorrectly expected a malformed-price refusal to leave the facade readable. Actual behavior conservatively retained an unacknowledged intent before downstream validation. The corrected test verifies no fill and continued snapshot/report refusal; no evidence was erased and no implementation safeguard was weakened. Original failure output is retained locally, excluded from publication. No new source defect or broader recovery permission is inferred.

## Dependencies and earliest supervised session

1. Independent governance review explicitly adjudicates new hypothetical inception versus historical adoption, and its relationship to B1. Preserve historical discrepancies and accept no implicit waiver. Obtain the required complete independently authenticated new-epoch genesis/risk/source evidence and any historical evidence the decision still requires.
2. C1/N3: independently accept exact actual writer/process/resource ownership and all-writer exclusion/drain, including children, report and metadata writers. Native fixture observation alone remains insufficient.
3. D1/N4: accept trusted issuer/operator proof, protected storage identities/sidecars, clock, rollback and explicit recovery policy; separately authorize provisioning. Local files, fixture pins, environment variables and Yes clicks alone remain insufficient.
4. Explicitly authorize the file-level canonical/native implementation above and its disposable integrated acceptance. No protected caller wiring is authorized by this design task.
5. Independently accept provider rights, budgets and authorized feed continuity; backup/isolated restoration and native lifecycle boundaries. Resolve deferred GUI close and legacy Stop acceptance before one-click use.
6. E1/N6: review applicable unchanged 21 decisions, accepted release/session scope and supervised bounded session, then separately authorize startup on the existing accepted path. Until then startup remains NO.
7. Execute and independently inspect the authorized session, reports, unresolved-state handling and safe shutdown. Offline tests do not constitute operational or power-loss acceptance.

Historical migration is a different future action: complete archive/exposure/cash reconciliation, witnessed mapping, original-byte preservation and separate migration permission. A new epoch neither performs nor authorizes it. Eventual live-money eligibility additionally needs venue account/security approval, real order/fill/position/balance reconciliation, exchange idempotency, margin/funding/collateral controls, independent kill switches, loss/exposure limits and security/risk/legal review. None is enabled or implied by PAPER feasibility. No VPS is required.

## Next engineering and approval boundary

All currently authorized design and useful separation acceptance work is complete after validation and publication. The exact next proposed engineering action is an **explicitly approved disposable canonical epoch-inception/event-receipt implementation**, with immutable epoch/resource binding and no protected dispatch. First obtain the governance scope decision above; do not manufacture an ACTIVE runtime task or silently grant a B1 exception. Production integration, provisioning, migration, providers and startup remain separately unauthorized.
