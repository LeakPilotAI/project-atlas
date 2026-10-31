# Quality Dips — advisory reconciliation and C1/D1 review package

Base `6e01bd4b7c1653a767bf8d6ad9234dc6fea04460`; branch `chatgpt/atlas-rebuild-v1`.
**BLOCKED_WAIT. B1/C1/D1/E1 BLOCKED. All 21 decisions unchanged. PAPER startup NO; production NO-GO.**

## Recorded review and source reconciliation

`QUALITY_DIPS_ADVISORY_REVIEW_V1_2026-10-24.json` records the six exact operator-supplied ChatGPT findings, disposition and explicit authority limitation. It binds both original reviewed artifacts by SHA256. It is an attributed advisory record, not a signed/authenticated review or independent acceptance. Original proposal and handoff remain byte-identical. No operator confirmation of proposed financial parameters, operational approval or source authenticity is inferred.

| Proposed contract | Existing implementation / discrepancy | Required disposition |
|---|---|---|
| USD1,000 capital | Explicit immutable fixture inception supports supplied positive simulated capital; does not prove accepted cash | Independently accept scope/inception; no legacy balance recovery claim |
| MSFT-only, USD100 entry, one remaining position | `paper_epoch_fixture.EpochFixture._apply` enforces Quality Dips long-only/no fabricated stop and available cash; it does **not** enforce this new instrument/notional/count policy. `quality_entry` accepts general eligible symbols/notionals. | Known proposal-versus-general-engine gap, not an existing promise violated. A future versioned, atomically enforced selected-account policy must be accepted and separately integrated; a request builder alone cannot exclude alternate writers. Do not quietly apply new limits to retained V1 histories. |
| Fractional quantities | Existing Decimal positive quantities, partial exits and remaining-quantity/revision checks support fractions; native Quality Dips V1 whole-lot journal does not supply canonical partial/cash semantics | Accept units/precision and versioned native projections; retain exact acknowledged commands for retries. Never mark native FLAT while canonical quantities remain. No new precision guarantee or stock exchange lot rule inferred. |
| 2bps fee + 2bps slippage per side | Existing candidate formula is `2 * entry_price * closed_quantity * (fees_bps + slippage_bps) / 10000`; USD100 fully closed costs USD0.08, allocated across partials | Internally consistent synthetic entry-notional assumption; not authenticated market costs, spread or fill evidence. Separate fee/slippage presentation needs evidenced allocation, not inferred totals. |
| Patient-capital overnight holdings | `quality_terminal_exit` refuses price-only shutdown exits; existing source retains open lots until accepted terminal/manual action | Preserve holdings. Operational shutdown completion must not mean liquidation. No forced intraday close or invented valuation. |
| Reports versus lifecycle | `PAPER_DAILY_FIXTURE_V1` and existing account summary classify remaining positions as INCOMPLETE; UNKNOWN projections refuse report completion | Preserve V1 bytes/semantics. Future separate lifecycle outcome may attest owned writers stopped while positions remain OPEN, with valuation UNAVAILABLE/accounting limits explicit. It must never relabel the V1 financial report COMPLETE or ignore UNKNOWN. Exact versioned overnight acceptance still required. |

No newly demonstrated correctness defect warrants a source repair under this execution. No application, financial dispatch, startup, frontend or lifecycle source/test changed. The above discrepancies are explicit next-integration requirements, not evidence that proposed limits are already enforced.

## C1 independently reviewable boundary

The proposed new account alone is the financial scope. Four logical resource roles are canonical events/receipts, additive native projections, immutable reports and admission/control evidence. Actual root/file IDs, owning process instances and accepted source revisions are **not yet supplied**. Logical IDs in the original proposal remain unprovisioned review labels. Protect each namespace and any sidecars/temporary publications; a lock on one file does not exclude another file or process.

| Source writer / reader boundary | Proposed treatment before an accepted account can run |
|---|---|
| `investment/prospective_evidence.py` observation append -> `quality_dips_paper.py` lot mirror | Admit exact evidence and financial operations separately with stable shared identity and durable acknowledgements; detect split/UNKNOWN outcomes. No blind callback replay. |
| `api/investment_board.py` GET fan-out; Quality Dips marking/terminal functions | Read-only account requests must have no financial or provider side effects. Explicit mutation paths require admission; deny otherwise. Do not merely relabel the existing GET read-only. |
| `quality_dips_v3_forward_store`, state, alerts/delivery; investment/target/quote/ladder caches | Separate evidence/metadata identities and drain; no metadata record substitutes for financial commit. Shared workers/resources require exclusion proof or admission. |
| Legacy Quality Dips, investment book, Hyperliquid manual/mirror/micro, equity mirror, shared PaperJournal, prediction and shadow | No new-epoch resource access. Accept exact disjoint roots and routes or explicitly roster each competing writer; source constants/account names alone do not establish exclusion. Preserve legacy records and unresolved positions. |
| Diagnostics, standalone scripts and alternate imports | Inventory direct store users; deny selected-epoch access unless explicitly admitted. Same-user arbitrary code/external Docker writers are outside demonstrated cooperative authority. |
| Daily reports, projections, archive/dashboard readers | Accepted read-only handles and complete source/applied revisions; UNKNOWN must remain unavailable. Report writers join final drain. No default empty financial fallback. |
| Windows parent/worker/API process and children | Existing refusal-only entry paths remain. Require exact run/release/PID/creation/image/command/account/parent plus trusted launch provenance and retained-handle lifetime evidence before ownership assertions. No generic-name/port termination. |

Required protocol: accept exact run/resource/writer/incarnation roster -> durably admit each operation before effects -> persist canonical event/receipt -> acknowledge required projections -> close entry admission -> drain admitted financial work -> refuse unresolved pending/UNKNOWN -> reconcile complete cash/quantities -> publish explicitly limited overnight/day report -> drain report/metadata writers -> observe exact owned process exit. Restart authenticates current resources/revisions and refuses incomplete intents. Unknown operations cannot auto-expire, retry or clear. Existing 20-second backend and 30-second owned API deadlines remain; no additional budget is granted.

C1 reviewer artifacts: fixed release/run/resource roster and authority origin; exact writer/caller disposition; per-operation intent/commit/projection evidence; pending/drain/exit observations with freshness; source/report completeness; concurrent alternate-writer exclusion or explicit residual limits. Existing native retained-child tests establish observation capability only. They do not certify an actual Atlas run, exclude hidden children or grant operational shutdown authority. Independent Windows lifecycle reviewer must accept the actual scope and results.

## D1 independently reviewable boundary

Use R7E47G's trusted-workstation Phase 1 policy: trusted intended operator, reviewed code/OS and normal native enforcement; no claim against same-account compromise, administrator/kernel actors or coherent whole-machine rollback. Do not add enterprise PKI/TPM/VPS requirements. Existing E136/21-gate obligations remain unchanged.

| Required contract | Reused evidence / unresolved acceptance |
|---|---|
| Epoch/root identity before access | R7E47F `snapshot_store.py` native handle-bound/no-follow/file-ID/DACL/single-link/digest checks are a tested control-state candidate. Actual approved roots/file identities and financial storage strategy remain missing. |
| Financial storage | Q4 path-based fixture SQLite is not protected operational authority. E's SQLite substitution/sidecar failure remains relevant. Accept database/journal/WAL/SHM or a separately approved narrower financial persistence design before native use; do not silently promote F's control snapshot into a replacement financial engine. |
| Trusted issuer/operator | H/I native account/session and explicit review workflow provide scoped primitives. Runtime issuer enrollment and exact epoch/resource/action binding are unaccepted. Supplied files, environment flags, clock functions and fixture signatures do not grant authority. |
| Durable receipt and revision | Reuse canonical operation receipts and G local intent/ack handoff semantics only through accepted storage. Bind global source/per-position/applied revisions and current pin. Split commit/ack gaps retain uncertainty; no newest-file fallback. |
| Clock | Approved source/freshness/window; reject missing/future/backward/stale evidence. Caller fixture timestamps are compatibility inputs, not trusted time. |
| Rollback | Detect known stale pins, missing/sparse handoff, source/receipt contradictions and known restore. Local same-authority files cannot prove undisclosed full-machine rollback absence; record this trust limit without inventing independence. |
| Recovery/restart | Preserve UNKNOWN and startup prohibition. Any clearing requires separate exact-action/revision-bound approval and independently obtained helper/writer evidence. No clearing from EXITED, missing process, timeout, Yes or apparent unchanged Engine alone. A first session may retain unavailable full recovery if accepted consistent inception exists and uncertainty always refuses. |

D1 reviewer artifacts: approved Phase 1 threat/scope statement; exact storage/read-before-trust/publication/sidecar specification; accepted root enrollment and trusted issuer/clock provenance; native denial/substitution/interruption evidence; current-pin/ack continuity and known-restore policy; explicit recovery owner and refusal semantics. Security/storage reviewer and operator must accept these independently. No actual enrollment, ACL/key/registry creation or protected store provisioning occurred here.

## Precise permission requests — not exercised

**P-C1-FIXTURE-OBSERVE:** authorize a named native acceptance run of the retained test-owned child identity/command tests (`test_native_identity_observation.py`, `test_native_child_observation.py`, `test_native_fixture_command.py`) after reviewing the exact test selection and fixture command. Permit only children created and retained by that harness, native read-only identity observations and graceful closure of their own stdin with existing bounded waits. No live process census, Atlas/Docker launch, unrelated PID action, force-kill, financial store access or ownership grant. Evidence remains fixture-only; it cannot itself accept actual C1.

**P-C1-ACTUAL-READONLY:** separately approve a fixed Atlas run/release and named expected PID/creation/image/command/owner/child/resource roster, and the exact read-only observer. Allow observation only of those named processes/resources; no enumeration of unrelated processes, starts/stops, provider calls or original financial payload reads. Current exact IDs are unavailable; this permission cannot be executed or presumed granted until supplied and independently reviewed. Results affect ownership claims, not startup permission.

**P-D1-DISPOSABLE-NATIVE:** after independently accepting the proposed storage test plan, authorize native identity/ACL/substitution/crash tests solely in a new disposable directory under `D:\Work\Project Atlas\logs\diagnostics\qd-d1-native-acceptance-<unique-run>` using reviewed existing primitives and harness. Any temporary restrictive ACLs/restricted tokens must be confined to that directory/children and explicitly included in permission. No operational root, issuer/key/registry/TPM enrollment, production financial data or provisioning. This is not currently authorized or performed. Protected operational enrollment remains a separate later request with exact roots and trust decisions.

**P-NATIVE-INTEGRATION:** after B1 scope plus C1/D1 prerequisites are accepted, separately approve Q10's exact Quality Dips source file changes and versioned overnight semantics. Permission must name the accepted canonical financial storage/issuer interface, policy enforcement and excluded writers. Development approval is distinct from deployment, migration, provider access or startup. Hyperliquid remains a separate follow-on lane.

External prerequisites remain: operator confirmation of the proposed financial parameters; independent historical exclusion/obligation disposition; current accepted storage/issuer/clock evidence; actual ownership/exclusion and E1 rights/backup/restore/lifecycle/session acceptance. No reviewer supplied those in this advisory message.

## Validation and exact continuation

New pytest tests: **not run**; no source/test behavior changed. Existing Q9 224 passes remain retained evidence, not rerun or added. Validation checks exact review disposition/six findings and false acceptance flags, original artifact hashes, source contract locations/formula/long-only/overnight behavior, canonical 21 decisions and startup lock preservation, public-path existence, diff checks and approved roadmap backup/read-back/history equality. No private records or protected process/storage tests were accessed or performed.

Persist BLOCKED_WAIT with no ACTIVE implementation task. **Next smallest decision:** confirm the proposed Quality Dips financial scope for design and select a bounded C1/D1 native acceptance plan/permission above for independent review. Advisory suitability is recorded, but B1 remains blocked. Do not repeat Q4–Q9, manufacture another adapter, clear UNKNOWN, provision authority or enable financial dispatch. Continue once the named decision/evidence is supplied. Full strategy coverage and all seven roadmap phases remain preserved; no other lane gains activation or consolidation authority.


Verified approved checkpoint: backup byte equality,exact managed read-back and historical outside-section preservation against pre-update/base all PASS. Original reviewed artifacts,canonical21decisions and startup-lock raw hashes unchanged. Backup `PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261024-005658-0c6dc20d.bak`;roadmap SHA256 `24b2881c67b224d500c0b77a84a992074d13bf7dc0d904c4e8797e682fa3b46c`. No new tests or operational acceptance.
