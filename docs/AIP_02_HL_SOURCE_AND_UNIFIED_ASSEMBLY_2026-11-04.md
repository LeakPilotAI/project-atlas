# AIP-02 — Hyperliquid source and unified research assembly

**AIP-02 COMPLETE — SOURCE-ONLY/DISPOSABLE. PAPER:NO. Production:NO-GO.**

Base: `a2ccd7d319abe96cafdeab64b74e61432d7f80d1`, branch `chatgpt/atlas-rebuild-v1`. This November 4 checkpoint-recovery report preserves the interrupted November 3 draft separately. Final regression execution completed November 4 local time; recovery reverified retained evidence without rerunning unchanged source. All observations below are synthetic/disposable unless explicitly described as retained historical evidence. No genuine clock clearance, provider entitlement, operational account state or installed acceptance is asserted.

## Scope and actual connections

AIP-02 in `ATLAS_INTEGRATED_PAPER_COMPLETION_AUDIT_2026-11-03.md` requires existing perp cache/trade/queue/settlement semantics, strict absence refusal and preparation of the two canonical lanes/custody/risk ports. This increment assembles those **source-level** connections without connecting an installed or operational financial runtime. It does not claim the later AIP-14 real two-lane financial pilot or any B1/C1/D1/E1 acceptance.

| Implementation | Connection completed |
| --- | --- |
| New `backend/app/services/hyperliquid_current_producer.py` | Explicit accepted current input + actual `HyperliquidAdapter` cache/order snapshot -> existing parser/publication -> acknowledged source archive -> replayable `read_cut()` and research projection. No acquisition/start/default authority. |
| Existing `paper_source_publication.PerpSourcePublication` | Extracted `prepare_capture()` retains its original book, candle, trade, queue and historical-oracle validation without writing. Existing `capture()` still prepares/publishes/readbacks and maintains its cache guard; adds optional original-input evidence/expected-head support. No replacement publisher. |
| New `scripts/observation_runtime/personal_perp_research_archive.py` | Typed USDC source recipe over the **existing** immutable image/CAS/intent/commit/ACK archive protocol. Distinct PERP enrollment/image schemas; no new storage engine, operational migration or financial codec. |
| Existing `personal_research_archive.NativePersonalResearchArchive` | Narrow recipe/schema/packet/freshness hooks permit that typed subclass. Existing QD enrollment and empty-image bytes remain unchanged; QD's exact archive type and strict schema cannot adopt a PERP image. Shared history/custody/UNKNOWN/capacity logic remains intact. |
| Existing `perp_source_planner` | Factored the original discovery + previous-order/setup lifecycle sequence into pure `source_research_plans`, used by both the original planner and read-only producer research view. No signal/ranking/entry/exit rule change. |
| Existing `HyperliquidMarketObserver` | Accepts the exact new source-wrapper type as well as the original publisher, requiring the same adapter identity and validated current cut. Does not connect/refresh a provider. |
| New `backend/app/services/unified_research_sources.py` | Read-only coherent pair view of the completed QD producer and HL producer, plus canonical lane/custody/risk **preparation**. No third archive, combined financial ledger, journal, session or runtime startup. |
| New tests | `tests/test_hyperliquid_current_producer.py` and `tests/test_unified_research_sources.py`; source/cache/protocol doubles and original pure accounting/strategy components only. |

The AIP-01 QD producer and its57-case test file remain byte-for-byte unchanged. Their existing archive protocol gained the narrow typed-recipe hooks above, and all396 AIP-01 test identities are present and passing in the final suite.

## Explicit source contracts and authority

`HyperliquidCurrentProducer` requires explicit source, input authority, publication authority, actual adapter object, read-only orders port, typed source archive, parameters, enrollment, clock and execution domain. Constructor parameters must match the archive enrollment digest/epoch/release/currency and the order port's parameters/domain. DISPOSABLE requires the existing fixture parameter schema and DISPOSABLE_TEST order domain; OPERATIONAL requires the existing operational parameter schema and LOCAL_ENROLLED domain. No operational verifier, dependency, account or root is installed by the constructor.

The PERP archive enrollment contains the original account/epoch/source/release/source-commit/root identity fields plus exact `lane:HYPERLIQUID`, `currency:USDC` and `parameters_digest`. It uses `PERSONAL_PERP_SOURCE_ARCHIVE_V1` / `PERSONAL_PERP_SOURCE_IMAGE_V1`. QD retains its original QD schemas. These are nonfinancial source declarations; they do not prove financial inception or current native identities on this machine.

`source.read_current()` supplies strict JSON with exactly:

```
schema: HL_CURRENT_RESEARCH_INPUT_V1
source_id, execution_domain, input_revision, observed_at
cache: exact actual adapter.paper_source_snapshot()
orders: exact read-only orders.snapshot()
maker_windows: original queue + selected trade IDs + declared queue_ahead
settlements: separately supplied historical settlement oracles
setups: original current lifecycle snapshot
provenance: nonempty original source receipt mapping
```

Input revision is a positive independent counter. Input serialization is bounded to131,072 bytes; maker windows<=32, settlement entries<=256, setups<=32. Cache market coverage must equal the explicitly configured existing parameter symbols, restricted by the existing manifest to BTC/ETH/SOL. Book/candle namespaces must cover those symbols; funding/trade namespaces cannot introduce others. Orders must have the matching domain and every supplied order must belong to the enrolled epoch/configured universe. Market values must be finite; price/volume/open interest positive. Original normalization/strategy restrictions still apply afterward.

The input owner must return `HL_CURRENT_RESEARCH_VERIFIED_V1` from `verify_current(context, now=...)`, binding the **entire** input, exact enrollment and domain, with verified status, nonempty receipt ID and matching execution domain. Boolean True is insufficient. Context mutation, foreign identity/domain, missing provenance, stale/future input or component substitution fails closed. A local digest binds content; it is not an issuer, proof of data rights or authentication by itself. Existing publication/archive authority checks and native custody leases are still required separately.

Current source input/publication/book evidence retains the existing five-second source requirement, original candle bounds and source completion checks. QD retains its separate original freshness contract. No financial executable-price threshold, Windows clock <=1000 ms/age<=120 s gate, browser45-second ACK or Stop8-second requirement changed. No Windows clock acquisition or settings operation was performed.

## Existing Hyperliquid research and execution semantics

The producer reuses `_paper_execution_observation`, `_paper_funding_observation`, `parse_public_trades`, `PerpSourcePublication`, original discovery/ranking/manual-plan/setup reconciliation and board projection. Determinism means identical ordered source facts, order/lifecycle cut and as-of clock produce the same normalized packet/research result. It does not freeze a genuinely evolving market into a permanently current observation.

**Maker evidence:** `maker_from_window` calculates only the existing queue/participation/quantity-step model. It requires a structured `HL_MAKER_WINDOW_VERIFIED_V1` receipt from the independent injected source owner over the exact original order, queue, selected trades, parameter digest and domain. It reparses the actual original trade rows, validates IDs/side/time/price, verifies the original at-limit visible queue and source revision/digest, and requires the queue's original receipt. It never turns the parser's `complete_window:false` into true. A current cache, mark touch or successful transport acknowledgement alone cannot establish a complete accepted window.

The accepted model is unchanged: available quantity is `(traded_quantity - queue_ahead) * participation`, capped by requested quantity and floored to the original order step. Exact fractional capacity avoids ambient Decimal rounding increasing fills; final Decimal arithmetic uses the existing28-digit precision with inexact refusal. Filled + cancelled quantity equals requested. Missing window means no fill; insufficient queue capacity means no fill; an invalid supplied window refuses publication. Raw windows, generated proof, source reference and original window acceptance receipts remain auditable through the acknowledged source image. A concrete test derives **0.375 filled /0.125 cancelled** from requested0.5, trades5, queue ahead1.25, participation0.1 and step0.001. These are simulated quantities, not real executions or operational account results.

**Funding:** original historical rate records are normalized by the existing parser. A separately accepted original settlement oracle remains separate from current mark/oracle data. Missing historical evidence stays absent. The actual planner is tested to refuse a due funding operation without the required rate/oracle history, and to leave a resting touch unfilled without trade-window proof. It never substitutes current book values for settlement. A fixture explicitly preserves historical oracle87 while current book oracle differs. Source publication can truthfully show missing settlement evidence; that does not authorize the affected financial operation.

Existing BTC/ETH/SOL scope, fees, slippage, position/margin/leverage/session limits, partial/IOC behavior and exit semantics are preserved. No scanner, coach, legacy financial mirror, wallet signer, order endpoint or strategy scheduler is started. No new trading opportunity is forced.

## Publication, acknowledgement and recovery

- A nonblocking producer lock prevents overlapping mutable projections. Original source/cache/order identity is checked before effect and again at completion. Bound parameters/components are rechecked immediately before publication.
- Raw input, its domain/enrollment acceptance receipt, normalized cache/order evidence and separate maker-window acceptance receipts are retained alongside the packet in the existing immutable source image. Native logical revision/current/ACK checks remain authoritative.
- An identical accepted input revision/cut returns the already acknowledged packet without another write. Same-revision disagreement or rollback refuses, including cold restart. Current cache/order change requires a newly accepted input, not blind reuse of an old packet.
- Publication uses the inherited expected-head/CAS guard. Input revision, adapter cache revision, logical publication revision and native image revision remain separate. No counter reset or operational capacity expansion.
- `read_cut()` reaccepts the original input/domain, checks original archived receipts, reconstructs the original normalized packet, compares archive/cache/order/source cuts and verifies freshness at completion. Fresh receipt identities need not be identical, but their accepted binding/domain must match. Cold replay does not depend on a transient in-memory “last published cache” flag.
- Interrupted native publication retains UNKNOWN/poison and refuses replay/repair. Once a producer attempts publication and fails, that instance is latched closed; a new instance still needs valid acknowledged current custody and evidence. No uncertain operation is automatically retried.

The shared source image remains bounded to127 source successors plus its initial native image, under the original128 native revision limit and existing image/packet capacities. Long-running continuation remains AIP-03; this increment does not roll over or alter an operational store.

## Unified QD/HL view and financial boundary

`UnifiedResearchSources` requires the exact QD and HL producer types, common explicitly bound clock/domain, distinct account/epoch/source/root identities, distinct image ports, and matching release/source commit. Each lane independently authenticates its own publication; one lane cannot vouch for the other. Joint authority must return a structured `ATLAS_UNIFIED_RESEARCH_VERIFIED_V1` receipt for the exact enrolled pair and packets. Repeated fresh reads refuse changed, stale, missing, foreign or conflicting evidence.

The result is a read-only `ATLAS_CURRENT_RESEARCH_VIEW_V1`, **not a new publication ledger or financial snapshot**. QD remains USD, HL remains USDC; `total_cash` and `total_equity` remain None and `financial_startup_authorized` remains false. No counterpart account is invented, funded or consolidated.

`prepare_canonical_lanes` verifies the actual `CanonicalWriterLane` and `UnifiedPortfolioCustody` class identities, exact writer/source/reader/observer/epoch/account/release/parameter bindings, common clock and the explicitly supplied risk-port identity. The original component verifiers run before/after the joint binding receipt; callback mutations and substitutions refuse. It neither invokes `compose_personal_unified` nor starts/connects a financial runtime, publishes financial state or creates a session/reservation.

Disposable constructor-seam tests instantiate the actual HL `NativeFinancialWriter`, `RestingPerpWriter`, `PerpSourcePlanner`, `HyperliquidMarketObserver`, canonical lane and unified custodian over inert in-memory cuts/ports. The QD financial writer is explicitly an **inert typed contract double**, not a connected enrolled QD runtime; its actual canonical-lane constructor and AIP-01 real source producer are used. This is scoped source/preparation evidence, **not complete live financial composition or genuine native enrollment**. Existing separately scoped actual-lane native evidence is preserved without rerunning it. No installed/account connection was needed for AIP-02's source-only acceptance.

Risk conversion remains an externally accepted explicit port. A non-parity **synthetic0.97** declaration exercises port identity; it is not a current FX quote or operational permission and no conversion is computed by this view. Actual portfolio reservations, account/risk reconciliation, accepted conversion evidence and session authority remain the responsibility of the existing financial composition/admission path and later commissioning.

## Exact validation results

**Final consolidated suite:667 passed,0 failed,0 errors,0 skipped;29 modules;27.97 seconds console (JUnit27.929 seconds).** Includes **80 new cases:53 HL producer and27 unified-source cases**,587 existing cases, and **all396 AIP-01 identities**, including all57 AIP-01 new cases. Counts are not added across overlapping runs. The old590 V6 cases remain historical evidence, not an unnecessarily repeated suite or a fresh runtime acceptance claim.

Coverage includes actual BTC/ETH/SOL parser/discovery/projection, source/archive acknowledgement and cold replay, missing/stale/future/conflicting data, bad source/domain/receipt, wrong market/control namespace, original queue/trade/quantity/price disagreement, negative trade inputs, source mutation, parameter/release/root substitution, duplicate/rollback input, unfilled queue capacity/touch, due-funding refusal, separate historical oracle, ambient-precision independence, original observer binding, interrupted ACK/UNKNOWN, QD/perp image separation, QD/HL coexistence, separate USD/USDC, canonical source/risk/clock/ownership-port substitution and callback mutation.

Regression selection is preserved in `logs/diagnostics/aip-02-hl-source-20261103/acceptance.xml` and `acceptance.txt`; `source-validation-proof.json` lists all29 per-module counts and nine tested source/test hashes. It includes the prior AIP-01 research/valuation/scanner/read-model/accounting/commissioning-memory modules plus personal/unified runtime contracts, unified accounting, perp financial/execution/funding/IOC/margin, market observers and original discovery/setup/board suites. No native test requiring real confined roots, installed runtime, actual provider or operational account was selected. Native image I/O in the new tests is the existing in-memory double; current source/queue authorities are explicitly synthetic. The adapter's provider methods are guarded against use in new fixtures. External provider requests/connections: **0**.

Final JUnit SHA-256: `d8fc407418576ef88e6cd07c5cbf725b5075109b3aa50631c006444ab1a5056f`.

No-cache Ruff check passes all nine source/test files; formatter check passes all five new files. Existing compact files were not broadly reformatted. One preexisting warning remains: Starlette/httpx TestClient deprecation. No dependency installation was attempted. The unrelated preexisting research test edit is preserved as-is (SHA-256 `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb`) and excluded from the commit. Its working-tree tests participated in the regression suite.

### Failures and retained evidence

The first28-case new selection passed. A restricted-permission combined selection was interrupted after partial progress; normal-permission read-only inspection found no matching surviving test process. The corresponding normal-permission selection passed130 cases. No pass is inferred from the interrupted command. This is ordinary test permission scope, not Windows administrator elevation or an operational run.

Two broader runs retained663 passes/1 failure and664 passes/1 failure. Both failures were the new due-funding fixture: first it omitted a position revision; the corrected fixture then initially treated the existing `apply_event` state/receipt tuple as a single state. The final fixture uses the actual pure accounting transition's complete next state, verifies funding is due, and preserves the original expected missing-history refusal. Its targeted check passed1 case, then the full final667 passed. No financial validation or expected refusal was weakened. Initial import-order/unused-import findings were fixed; earlier logs/XML/artifacts are retained and not converted into passes.

New fixture images and test artifacts remain disposable/in-memory or under the explicit diagnostic root. Inventory immediately before the proof file:923 entries /14,344,761 logical bytes. This is ordinary regression storage, not operational capacity or resource acceptance. No cleanup of unrelated data, caches, processes or historical evidence occurred. Test commands completed; final exact-command process inspection is recorded separately from V6's native Job/socket/handle acceptance. No installed host or V6 listener/browser experiment occurred.

## Remaining authority and commissioning dependencies

No actual Hyperliquid provider rights, feed continuity/window completeness, historical settlement oracle, operational account/custody/release/native root identity, current clock, financial risk conversion, writer exclusion, Stop timing, dashboard or restart acceptance has been newly established. Real maker-window evidence that cannot be proved remains ineligible; historical or fixture success cannot fill that gap. Missing due funding data refuses the affected operation. The operator must explicitly authorize any later current provider access, native enrollment/installation, account inception and bounded PAPER session after all unchanged technical gates pass.

The installed release/support, original receipt/ACK/journal, operational selector and financial stores were not accessed or changed. Historical UNSELECTED revision6 is not freshly reread here. Future immutable release/source-pin review must include these new/changed modules; no old authorization or frozen payload is reused/patched. B1/C1/D1/E1, all21 historical decisions, sole-operator personal policy, original V6 failures/consumed grants, the blocked three-reader/trusted-Chrome prerequisites and Genesis isolation are preserved.

**Next audited milestone: AIP-03-CONTINUATION-OPERATIONAL-BOUNDARY**, beginning with source review/disposable tests and preserving its operational-migration authorization boundary. AIP-04/AIP-05 remain independently eligible within their own scopes. This execution stops after AIP-02 documentation, validated commit, non-force push and remote-SHA verification. No subsequent milestone, operational connection or acceptance retry is automatically executed.

## Checkpoint recovery — November 4, 2026

Recovery independently found the branch at the original base commit, with an empty staging index and no completed AIP-02 commit. The locally cached remote-tracking branch matched that base; live remote verification is required after the checkpoint push. Existing implementation, private artifacts, the November 3 draft and the unrelated research-test edit were retained. No AIP-03 work was begun.

Recovered evidence was verified, rather than presented as a new test run:

- All nine tested source/test SHA-256 hashes match current working-tree bytes and parse successfully.
- The final JUnit artifact hash matches its retained proof and the earlier roadmap/state declaration. It contains 667 distinct test identities with zero failures/errors/skips, and its exact 29-module distribution matches the proof. The retained console records one existing dependency warning and 27.97 seconds.
- All 396 original AIP-01 test identities occur in that final suite. The QD producer and its 57-case test file match both their retained hashes and the base commit byte-for-byte.
- The due-funding fixture calls the existing pure `apply_event`, unpacks its state/receipt tuple, checks the resulting position has funding due at the test time, and asserts the unchanged `SETTLEMENT_RATE_AND_HISTORICAL_ORACLE` refusal with unchanged state. The original planner and pure accounting model are not modified.
- The personal PAPER policy and 21-decision gate matrix match the base commit exactly. The preexisting unrelated research-test edit still has hash `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb` and is excluded from staging.
- The prior active recovery values and roadmap checkpoint are preserved in their existing archival structures. This recovery adds its own explicit archival entry and current report reference.

The retained 667-case result remains attributable to this source tree; no expensive regression rerun was needed. The earlier interrupted process-inspection and resource inventory findings are recovered historical evidence, not newly executed native cleanup or Windows acceptance. No current provider, clock, installed, selector, account or browser inspection was performed in this recovery.

Tested implementation pins (raw file SHA-256):

| File | SHA-256 |
| --- | --- |
| `backend/app/services/hyperliquid_current_producer.py` | `fa31ae70faf142ceeda2e6732fd96f72e3e31f62789a7aef756f88ebfa19154b` |
| `backend/app/services/unified_research_sources.py` | `da4f56930a5ed9a60092c797f8cb7d5ab8e98fda595eeeaad08d20ecd05d1458` |
| `scripts/observation_runtime/personal_perp_research_archive.py` | `2bb07a435b338eb46bc335fba2affea6670f5c6435b1119d5b27ea2e36963ddc` |
| `backend/app/services/perp_source_planner.py` | `02bf0ddd98ae77071390abfe02622f2145c2bbbed355a0a3a05d175650543898` |
| `backend/app/services/paper_market_observers.py` | `c29977ff90ab97ec53956ea2af8da7f479ac2cfcbd6894334bdfaef753091266` |
| `scripts/observation_runtime/personal_research_archive.py` | `42edaf6b5e3d9cd9331913f1ec660d6b2ccbe41c38e708cb9342fba2836d1c79` |
| `backend/app/services/paper_source_publication.py` | `5834621c35f76edc799590b751da8c14016274d33f9c607e08e8a4fdd1450ed4` |
| `tests/test_hyperliquid_current_producer.py` | `0863b39f591a06a50c8572c849a3ad1d0a4b789a71f2dd2888b304c8191b8dc5` |
| `tests/test_unified_research_sources.py` | `9b55f2851fbcd63411bc7964efc51d3d47ff5d6e2e824bcbcf1896611e1d1b34` |

Checkpoint completion requires staging only the nine tested implementation/test files, the two AIP-02 reports, roadmap and recovery state; then a non-force commit/push and an independent live remote SHA comparison. The unrelated test, private logs, backup files and other work remain excluded. The final chat report supplies the resulting commit and remote verification, avoiding an impossible self-referential commit hash in this document.

**Decision: AIP-02 COMPLETE — SOURCE-ONLY/DISPOSABLE.** Genuine provider/queue-window/settlement authority, operational account/custody/risk enrollment, current clock evidence, installed financial Stop/restart/dashboard and B1/C1/D1/E1 commissioning gates remain outstanding. The V6 three-reader active-listener and trusted-browser prerequisites remain BLOCKED; neither is retried or reinterpreted here. Next canonical milestone is AIP-03, but this execution stops after AIP-02 checkpoint verification. PAPER:NO. Production:NO-GO.
