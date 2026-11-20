# Remaining native continuation: preflight and consolidated execution proposal

Date: 2026-10-26. Verified base:34cf61dabfcbabff86d27ba523a612c5746f7125;branch chatgpt/atlas-rebuild-v1.
Status: SOURCE-ONLY PREPARATION;NATIVE EXECUTION NOT AUTHORIZED.
Proposed grant: **P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V2**.

## Read-only preflight findings

Inspected canonical roadmap/current and retained checkpoints,autonomous state,execution queue,latest native report,interface boundary,operator capacity package,and actual native budget/segment/catalog,FS3,writer roster and fixture helpers. Tracked tree was clean at the stated base. No old fixture root was reopened,no journal/account content read,no native constructor or publisher invoked. One proposed path was checked for existence only and is absent. Original277/22/27-case results and initial failures remain historical evidence;not rerun or relabeled.

Remaining integration is concrete:

1. Six-role catalog is not the complete operational15-role/8-exclusion map. Existing `unified_writer_roster.py` is the canonical role inventory;native continuation must bind all roles and explicit aliases,not imply same-user hostile-code exclusion.
2. Prior order cut was empty. Need existing `perp_resting_order.transition` with ARM/CANCEL and financial FILL_PENDING/ACK history;unresolved RESERVED/FILL_PENDING must block switching. Preserve old IDs and consumed fill evidence after restart/rollover.
3. Prior report cut was inception-only. Need existing FS3 builder/audit over actual populated synthetic financial rows,partial/final fills,funding and source revisions,with historical day/session cutoffs across segments. Native report storage remains a fixture codec,not operational ReportArchive enrollment.
4. Hard-link refusal passed;native junction and true-symlink probes were NOT EXECUTED. Missing privilege must remain NOT EXECUTED;no privilege elevation/configuration change to force a test.
5. Source abrupt-child tests passed,but catalog interruption tests used exceptions in one parent. Need genuine retained-child death at catalog phases,then fresh-process inspection and persistent UNKNOWN without automated recovery/adoption.
6. Source review found ACK marker did not bind catalog digest;catalog scope/root-map checks were incomplete. Source-only correction now verifies exact marker digest,schemas,all six selected native resource maps,current pins/state cuts,and bound scope. These new checks have pure tests only;native constructor/reopen acceptance remains pending.

All remaining tests can be performed with synthetic accounts/resources,existing accounting/FS3/order/global transitions and injected clearly synthetic authority. They cannot establish actual workstation ownership,provider rights,independent custody,physical power-loss durability or B1/C1/D1/E1 acceptance.

## One exact proposed filesystem scope

Create exactly ONE previously absent root:

`D:\Work\Project Atlas\logs\diagnostics\continuation-fixture-77a93d8995474d649d7bda5095d84ab5`

If it exists or any ancestor/native identity is ambiguous when approved execution starts,STOP;do not adopt it or silently select another path.

Only descendants may receive native test writes:

- `native\<unique-case-id>\<role>\segment-0`, `segment-1`, `projection-0`, `projection-1` as applicable.
- `native\<unique-case-id>\catalog` for immutable switch intent/record/commit/ACK.
- `custody\<unique-case-id>` for plainly synthetic current pins,reservations,status and bounded locks.
- `attacks\<unique-case-id>\target` and `links` for junction/symlink/hard-link probes. ALL link targets and sentinels inside this same root;never target operational paths,Genesis,old fixtures or ancestors.
- `evidence` for bounded results,child identity receipts,hash manifests and original failures;`session-budget*` and reservation ledger at the new root.

Owner/current SID+SYSTEM protected ACLs only on newly created native fixture children. No root/project/ancestor ACL changes. Native IDs/SID retained privately;publish redacted source/results only. Existing expired V1 root/evidence remains untouched and its clock/reservations are never reset.

## Bounds,process ownership and cleanup

- One run;30-minute monotonic hard deadline beginning before first root mutation. Close test admission by minute25,reserve final5minutes for owned-process exit,handle release and final inventory. Fail closed;no extension/restart with a fresh anchor.
- Maximum8192 total filesystem entries INCLUDING files,directories,links,logs,control state and failed/abandoned publications;maximum256MiB conservatively charged allocation/metadata. Durable prospective reservations before EVERY create/overwrite/link operation;failed writes consume budget. Validate ledger schemas/nonnegative counts,current root/ancestor identities and no reparse before access;missing/corrupt reservations after initialization refuses rather than recreating/adopting them.
- Two native segments per tested role,128local slots each;bounded global traversal. Do not expand existing operational capacities. Reuse prior full128 test evidence;repeat only when changed integration requires it.
- At most two test-owned children concurrently;60seconds maximum per child,shorter if session deadline requires. Retain original process handles and verify PID,creation identity and image;no lookup/termination by name/port,no unrelated process enumeration. Child code paths and all input/output roots pinned to this scope. Prefer self-exit/graceful exit;requested emergency permission is limited to terminating an exact retained test-child handle after its bound expires. Never act on ambiguous/foreign/replaced identity. No Atlas service,provider,scanner,HTTP host,financial runtime or network listener.
- Keep immutable predecessor/successor/crash evidence. Close handles,wait/reap owned children,verify no owned process remains. No recursive deletion or reset. For link probes only,permit removing the exact newly created link entry after identity/target verification (never follow/delete its target);retain before/after sentinel hashes and probe results. If link identity is uncertain,stop and preserve it. Final inventory must enumerate links without traversing them and count their budget;ordinary financial access still refuses reparse points.
- Disable bytecode/pytest cache writes for execution;capture test outputs inside the new root. Source/docs edits remain ordinary authorized engineering work,not permission to write elsewhere during native tests.

## Complete proposed writer/resource mapping

Every row has a unique writer ID,synthetic account/release/session binding,retained test-process identity,exact native resource and accepted predecessor/successor mapping. Same process may hold multiple distinct writer roles. Aliases require explicit declaration and exact resource equality;do not manufacture15independent stores or financial engines.

| Canonical role | Fixture resource / continuation handling |
|---|---|
| QD_DECISION | immutable decision publication;source decision revision and no new decision during switch |
| QD_SOURCE | QD native financial segment chain;USD only |
| QD_PROJECTION | exact QD source projection roots;global applied financial revision |
| QD_REPORT | populated QD historical/session report chain and complete source cut |
| QD_COORDINATION | pending/ACK financial coordination;UNKNOWN blocks |
| QD_RANKING_PUBLICATION | synthetic retained ranking publication/current source version;never made fresh by rollover |
| PERP_SOURCE | perp native financial segment chain;USDC only |
| PERP_PROJECTION | exact perp source projection roots and applied global revision |
| PERP_REPORT | populated perp report chain,fees/funding/cutoff/source lineage |
| PERP_ORDERS | durable resting order/event chain;original IDs,ACK/fill consumption retained |
| PERP_FUNDING | explicitly declared writer alias to PERP_SOURCE;settlement evidence bound |
| PERP_MARK | explicitly declared writer alias to PERP_SOURCE;mark revision/evidence bound,no fill inference |
| PERP_MARKET_PUBLICATION | synthetic order-book/trade/publication version;no provider activity |
| GLOBAL_CUSTODY | catalog/control chain;SESSION/CLOSE/FINAL,reservation and high-water |
| SESSION_RESERVATION | synthetic lease/currentness boundary;expired/revoked grants refuse |

Eight canonical exclusions:LEGACY_INVESTMENT,LEGACY_PREDICTION,LEGACY_MANUAL_PERP,LEGACY_JOURNAL,RESEARCH_MUTATION,INCEPTION_PUBLISHER,RECOVERY_WRITER,LEGACY_SCANNER_FINANCIAL_MIRROR. Exercise competing **synthetic** writers for each and refusal after admission closure. Do not inspect/start actual excluded systems. A fixture exclusion receipt is not operational exclusion acceptance.

## Execution and acceptance matrix

1. **Roster:** reuse actual validate_roster/lease/drain contracts with retained test-child observations;all15roles/8exclusions,missing/duplicate/foreign/stale process/resource/unknown operation/alias ambiguity refusal. Exact original-handle identities before access. Full operational roster remains separately unaccepted.
2. **Populated orders:** ARM->CANCEL and ARM->FILL_PENDING->financial ACK sequences from existing models;partial/full financial fills tied to exact evidence and durable source receipts. Roll only drained histories;pending and UNKNOWN refuse. Global operation/order IDs remain unique across segments/restart.
3. **Populated reports:** actual synthetic QD and perp entry/partial/final/funding records,at least two report revisions/day boundaries and a session cut;rebuild FS3 independently against uninterrupted full history. Compare cash,quantity,basis,fees,slippage,gross/net,funding and source/applied/report revisions;keep USD/USDC separate and unavailable valuations explicit.
4. **Containment:** confined target substitution,junction/true-symlink creation where Windows permits;native identity-before-read/write and budget before allocation;link/file/ancestor changes refuse,targets remain unchanged. No system privilege or developer-mode change. Unsupported capability=NOT EXECUTED,not PASS.
5. **Catalog crash/restart:** exact child exit before intent,after intent,each prepared role,record,commit,each partial selection,ACK,catalog CAS and admission ACK. Fresh process verifies acknowledged same cut OR explicit UNKNOWN. Missing/partial state never falls back to predecessor writer or blindly republishes. Actual recovery decisions remain injected and unaccepted.
6. **Inconsistent custody:** missing/foreign/old marker digest,partial root map,scope mismatch,mixed predecessor/successor,stale high-water,changed projection/report,revoked issuer/lease/clock. All reads/admission refuse or show UNKNOWN without effects. New source-only ACK/scope checks require native revalidation.
7. **Parity:** full logical replay/audit and FS3 projections before/after switch;predecessor byte hashes/native identities unchanged;no new inception/deposit,missing/duplicate effect or residual exposure;compare continuous versus segmented reference and cross-segment duplicate refusal. Source-read/report-read paths remain nonmutating.

Source files:extend `scripts/volume_inspector/native_continuation_fixture.py`, `scripts/observation_runtime/native_fixture_budget.py`, `tests/native_continuation_session_fixture.py`, exact test-child helper and native test module. Reuse existing financial_reporting,FS1audit/replay,perp_resting_order,unified_portfolio_custody and unified_writer_roster contracts. Protected operational dispatch,schemas,UI,launcher and financial roots remain unchanged. Do not add a second engine.

## Authorization requested — NOT YET GRANTED

Approve/reject **P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V2** as ONE consolidated grant covering the exact root,seven test groups,ACL/link actions,bounds and exact-owned child cleanup above. Approval permits only disposable engineering and tests. It does NOT permit operational migration,enrollment,current-custody installation,financial inception,provider/credential/service access,retained-journal reads,actual account/writer startup,Genesis access or release-gate changes.

Before operational continuation:independently accepted B1scope,C1actual owner/resource/exclusion/drain,D1issuer/current-high-water/clock/recovery and E1provider/release evidence remain mandatory. Reviewer roles not designated remain UNASSIGNED. Financial PAPER:NO;production:NO-GO;all21decisions/seven phases and original UI preserved.

## Checks actually performed during preparation

23 pure unit cases passed,0failed,0skipped;no native fixture root/files/ACLs/child/host created. Ruff and compilation passed;603-file PAPER static audit reports zero issues. Historical roadmap prefix/suffix and prior managed body verified preserved;original accounting,offline continuation,export contract and writer-roster source unchanged. Original native27,offline277 and bridge22 remain retained evidence,not rerun. Native scope/ACK hardening requires the proposed native revalidation before acceptance.
