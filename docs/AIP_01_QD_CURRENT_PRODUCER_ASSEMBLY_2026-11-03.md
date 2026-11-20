# AIP-01 — Quality Dips current producer assembly

**AIP-01 COMPLETE — source-only assembly and disposable acceptance. Operational current research, installed financial integration and PAPER startup remain unaccepted/unauthorized. Production: NO-GO.**

Base: `4404b116cf23fa9f85231c18e84e4aea98dcaee5`, branch `chatgpt/atlas-rebuild-v1`. Scope is AIP-01 in `ATLAS_INTEGRATED_PAPER_COMPLETION_AUDIT_2026-11-03.md`: an explicit source-to-authority-to-archive-to-reader path using existing components and disposable fixtures. No installed runtime, provider connection, account inspection/inception, operational financial publication, native acceptance experiment, browser action, V6 retry, Windows configuration or Genesis access occurred.

## Existing components and missing connection

| Component already implemented | Reuse in this increment |
| --- | --- |
| SEC/Alpaca free client, cache, normalization, original read-only `InvestmentScanner` | Remain unchanged. A new end-to-end fixture passes injected synthetic responses through the actual free bundle/scanner and into this assembly. No external fetch or Yahoo fallback. |
| `quality_dips_research_only.project_explicit_research` | Original board/scoring/order plus explicit current V2/V3 projection with stored evidence disabled. No new margins, scores, eligibility thresholds or tie-breaker. Given the same ordered input and clock cut, output is deterministic. |
| `CandidateEvidenceAdapter` | Original ranking/execution receipts, V3 observation/ladder checks and L1 reached-price validation; no replacement signal engine. |
| `QualityDipsSourcePublication` | Existing authenticated current publication protocol. Adds optional original-input evidence retention and an expected-head guard; existing callers retain their default behavior. |
| `NativePersonalResearchArchive` / `NativePersonalCoordinationImages` | Existing immutable image/CAS/intent/commit/ACK/current-custody protocol. Adds read-only `read_evidence(expected)` for packet and original sources from the same acknowledged cut. Existing `read(expected)` still returns just the packet. No new archive schema, initializer or operational storage migration. |
| `QualityDipsPublicationReader` | Unchanged. Its source interface is supplied by the new producer's `read_publication(timeout)`. A read-context double proves selection follows the original board rank; no financial runtime is constructed/connected. |

The missing connection was a bounded, provenance-preserving current-input assembly. The new `backend/app/services/quality_dips_current_producer.py::QualityDipsCurrentProducer` supplies it. All dependencies are explicit; construction performs no acquisition, filesystem provisioning, account initialization or startup. Caller-owned archive enrollment and all existing technical authority ports remain mandatory.

## Explicit input and acceptance contracts

Constructor dependencies: `source`, `input_authority`, `publication_authority`, existing `archive`, original `candidates`, `clock`, exact `enrollment`, and `execution_domain`. The archive must be the existing native-image archive type and match the enrollment and clock. Account/epoch/source identity, release digest, source commit and native root identity are frozen/bound. This is a nonfinancial source enrollment, not permission to create or fund an account.

`source.read_current()` returns one strict JSON cut with exactly:

```
schema: QD_CURRENT_RESEARCH_INPUT_V1
execution_domain: DISPOSABLE or OPERATIONAL (must match the assembly)
source_id: exact enrolled source
input_revision: positive integer, independently monotonic
observed_at: integer UTC seconds, not future, at most 30 seconds old
rows: 1..50 original normalized research rows, unique uppercase symbols
observations: original V3 observations covering those rows
instruments: 1..16 explicit scoped instruments, unique symbols/native instrument IDs
quotes: exact scoped symbol map; original execution evidence
publication: current original QD_RANKING_REVISION_V1
monitors: at most 16 explicit current instrument monitors
provenance: nonempty original source-receipt mapping
```

Maximum input is 131,072 serialized bytes; existing smaller candidate/packet/archive capacity checks also remain. No provider receipt, financial metric, observation identity or ranking authority is synthesized by the assembly. The upstream source supplies the observations; their V3 prediction must equal the existing pure projection, their strategy/policy/evidence/execution labels must agree, and their timestamps must be consistent. The test fixture's construction of synthetic observations is confined to tests.

`input_authority.verify_current(context, now=...)` must return a structured `QD_CURRENT_RESEARCH_VERIFIED_V1` receipt with `verified: true`, exact `binding`, nonempty `receipt_id` and matching `execution_domain`. Context includes the complete input, enrollment and domain. A bare `True`, mutated context, foreign binding/domain, missing provenance or unaccepted input refuses. The digest binds bytes; it does **not** create provider rights, authenticate an upstream source on its own or invent a cryptographic UTC issuer. Installing a legitimate operational verifier remains outside this increment.

Original research/ranking freshness remains at most600 seconds, original ranking expiry remains exclusive and its lifetime at most600 seconds, input/quote/monitor freshness at most30 seconds, and the final current cut is rechecked at completion. Publication time cannot precede ranking issuance. Existing stricter executable IEX/financial-runtime checks are unchanged; passing this research assembly is not executable-data acceptance. Clock evidence itself is injected, not obtained or relaxed here.

## Publication and replay sequence

1. Verify exact enrollment/component bindings and acquire a nonblocking per-assembly publication lock.
2. Copy and validate the input; obtain its domain/enrollment-bound acceptance receipt. Run the existing explicit projection, retaining board order, source timestamps and scores.
3. Match original observations to that projection. Validate the original instrument/quote evidence. Only existing V3 eligible/reached-L1, unblocked, complete candidates enter bundles. WATCH/missing valuation remains a genuine no-entry publication; invalid/missing required maps, contradictory predictions or stale quotes refuse.
4. Read the acknowledged archive head. Verify prior archived provenance/domain/enrollment/receipt before comparing independent input revisions. No legacy/foreign provenance adoption. An identical current input returns the existing verified packet without a write; a same-revision conflict or rollback refuses, including after restart.
5. Recheck source stability/acceptance. Publish through the existing source producer with `expected_head` bound to the earlier duplicate check. Native CAS still owns durable publication. A competing winner causes refusal rather than a second copy of the same input. Reentrant publication cannot share a mutable projection.
6. Persist the complete original input, acceptance receipt and enrollment digest alongside the original projected research/scanner rows. Read back the acknowledged image and validate replay, packet bundles, monitors, current custody and freshness. Logical input revision, source publication revision and native image revision remain distinct.
7. `read_publication(timeout)` independently reaccepts the archived input, rebuilds the original projection, compares its bundles/sources to the actual current packet and verifies completion freshness. It opens no financial runtime and performs no publication. Consumers must use this source interface, not treat a saved packet or the internal publication helper as enduring current authority.

Known pre-effect input refusals leave the archive unchanged. Once publication has been attempted, an exception latches refusal on that assembly; it cannot blindly retry. Native interrupted-write/ACK uncertainty retains the existing UNKNOWN poison. A fresh assembly can recover only from independently accepted acknowledged current custody and complete source evidence. It does not repair, replay an uncertain operation or reset a revision. A newly accepted fresh successor can follow an expired input while preserving all predecessor bytes; old evidence is never timestamp-refreshed into a new observation.

The per-call `.2` source-read parameter retains the existing interface; these pure protocol tests are not a new Windows native latency/Stop certification.

## Disposable acceptance and regressions

**Final: 396 passed, 0 failed, 0 errors, 0 skipped; 15.90 seconds console time (JUnit15.861 seconds).** Includes **57 new AIP-01 cases** plus339 existing relevant cases across15 test modules. The earlier111/382/389/395-case selections overlap this final suite and are not additional distinct passes. Prior590 V6 harness cases and all historical native evidence remain retained; they were not unnecessarily rerun or promoted.

Final selection:

```
tests/test_quality_dips_current_producer.py
tests/test_personal_research_archive.py
tests/test_paper_source_publication.py
tests/test_quality_dips_research_only.py
tests/test_personal_paper_read_composition.py
tests/test_free_research_pipeline.py
tests/test_historical_earnings_valuation.py
tests/test_iex_research_reference.py
tests/test_personal_commissioning_runner.py
tests/test_personal_paper_inception_memory.py
tests/test_personal_native_coordination_memory.py
tests/test_personal_publication_restart_memory.py
tests/test_qd_publication_completion.py
tests/test_quality_dips_autonomous_paper.py
tests/test_quality_dips_v2_board.py
```

Execution uses the existing `backend/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider`, explicit backend/repository/test paths, bytecode disabled and disposable TEMP/TMP/`--basetemp`/JUnit outputs beneath `logs/diagnostics/aip-01-current-producer-20261103`. Actual native financial/archive tests requiring separate confined enrollment were not selected; none are silently counted as passes/skips.

New coverage includes complete current input, actual candidate/board agreement, original rank selection, exact provenance readback,30/31-second freshness boundary, completion-time expiry, missing maps/valuation, foreign source, future/stale data, ranking expiry/identity, duplicate rows/instruments, conflicting observations, source mutation, release/source-commit/root/component substitution, blanket-True refusal, disposable-to-operational domain refusal, duplicate publication across restart, stale/conflicting input revisions, separate input/publication/native revisions, deterministic replay on independent memory stores, competing publication, reentrancy, interrupted commit/UNKNOWN no-retry, prior-provenance refusal and fresh-successor recovery.

The free-bundle end-to-end test executes the actual normalizer, read-only ingest and scanner, then the producer/archive path with **six injected synthetic fetch attempts and zero external requests**. Original source receipts survive in the archived input. Missing normalization produces an empty entry-bundle set; no analyst target or signal is manufactured. Financial-book/legacy portfolio access is forbidden by test guards. The eligible-candidate test additionally forbids filesystem opens and verifies only the nonfinancial source-image schema, with no account/cash/position image.

All native image storage operations in the new assembly tests use the existing **in-memory native I/O double**. This proves native protocol/revision/ACK integration against disposable state, **not actual Windows file identity, ACL, handle, process or installed custody acceptance**. Read-only runtime selection uses an explicit context double, not a connected installed financial runtime.

No-cache Ruff check passes all four changed/new source/test files; formatting checks cover the two new files. Existing source files received only the narrow additive changes above. New-file formatting was also checked for unchanged AST at its initial formatting step. A final suite on the resulting code passed.

One existing warning remains: Starlette's `httpx` TestClient deprecation. No dependency installation was attempted. The unrelated preexisting `tests/test_free_research_pipeline.py` edit was included as-is in the working-tree regression selection but was neither modified nor staged. Its SHA-256 remains `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb`.

### Retained intermediate evidence

- Initial new selection:33 passes/1 failure from an overbroad test substring search for `cash`; the actual source board legitimately contains `reserve_cash`. Replaced with structural source-image checks plus a filesystem-open guard. Financial state was never created by that fixture and no accounting assertion was weakened.
- A restricted-permission combined run stalled after partial progress. It was interrupted; a subsequent normal-permission read-only process query found no AIP-01 test survivor. The same focused selection passed111/0/0 with normal Windows test permissions. This was not administrator elevation, service access or an installed run. No passing result is inferred from the interrupted run.
- One broader command named a nonexistent test file; pytest ran zero tests and returned a collection-command error. Corrected selection retained in subsequent logs. Initial two import-order lint findings and new-file formatting findings were corrected; no assertion/safety threshold was removed. All failures/logs are preserved.

Final evidence: `logs/diagnostics/aip-01-current-producer-20261103/acceptance.xml`, `acceptance.txt`, and `source-validation-proof.json`. JUnit SHA-256: `fb385ce9a5c29bf65603134fde45ab6a6a0115b40e6118846a4e9d3a5809ed44`. The proof records four tested source/test hashes, final counts, the unchanged unrelated-test hash and deliberate-operation exclusions. Fixture artifacts remain retained, not deleted to conceal failures. Inventory immediately before that proof:708 entries/10,498,502 logical bytes; this is ordinary disposable regression storage, not a native operational capacity claim. No new native host/Job or installed process was launched; test commands completed, and final process inspection is separate from V6 cleanup acceptance.

## Remaining boundaries and next milestone

AIP-01's canonical source/disposable DONE criteria pass. It does not install a genuine provider/current-publication authority, verify current market data or authenticate fixtures as operational research. Existing genuine SEC/Alpaca historical research remains intact and historical; no new current ranking, clock clearance, account balance or executable quote is asserted.

Operational work still requires the approved personal B1/C1/D1/E1 technical facts, actual native source enrollment and source-authority handoff, current permitted IEX evidence/instrument/calendar/action/halt facts, fresh clock <=1000 ms/age<=120 seconds, exact immutable installed release/resource/ownership binding, accepted installed financial Stop/reconciliation/ACK/drain/restart and explicit bounded startup authority. Frozen installed application/support, receipt/ACK/journal and historical UNSELECTED revision6 were not accessed or changed. The new files and changed publisher/archive require future explicit source-package/pin review; they do not patch the frozen installation or silently refresh an old acceptance package.

No new external blocker was discovered for source-only completion. The V6 active-listener/trusted-Chrome evidence blockers, historical failures and consumed authorizations remain unchanged. All21 historical gate decisions and the sole-operator personal policy are preserved without promotion. No live-order, wallet, transfer, subscription, autorun, shortcut or Windows setting capability was added.

**Next audited milestone: AIP-02-HL-SOURCE-AND-UNIFIED-ASSEMBLY**, source-only/disposable first. AIP-04 dashboard contracts and AIP-05 fake-sender recovery also remain independent; AIP-03 may proceed within its separately reviewed storage boundary. This execution **stops after AIP-01 validation/documentation/commit/push/remote verification**, as directed. PAPER:NO. Production:NO-GO.
