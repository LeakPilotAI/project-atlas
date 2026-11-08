# N1 disposable native-writer facade — implementation and continuation

Base3bc30a29a655f289ac81dab261c7d9cb6b2159c7;branch chatgpt/atlas-rebuild-v1;tracked tree initially clean. Read native integration design and117-reference source inventory before work. No backend-specific repository instructions found;frontend untouched. Authorization is N1 source development/disposable integration only,not production dispatch,migration,data connections or startup.

## Completed facade functionality

`backend/app/services/hyperliquid_native_fixture.py` exposes exclusive `create_native_fixture` initialization and a dependency-injected `NativeFixtureFacade`. It receives an already-created disposable V2 overlay/ledger,pinned baseline,explicit native PaperJournal instance/journal path and ManualPerpStateStore instance. It imports no native singleton,discovers no runtime paths and registers no API,CLI,environment selector or startup action. Direct arbitrary imports are not an OS security boundary;protected startup remains the existing refusal contract.

The prototype adopts only pre-existing **disposable fixture positions** created through the reviewed native-class test loader. It creates no entry/trading path. BTC/ETH/SOL,1USD simulated risk,max3positions,manual-only entry and3Rstop remain inherited unchanged. Fee/slippage remain the existing2bps/2bps per-side entry-notional allocation. No actual financial records are read or migrated.

### Durable shared association

Before publishing a projection,the facade stores a separate digest-pinned association linking every V2 position ID to the original journal trade ID and unique manual setup_key. It binds the V2 baseline and original native journal/manual hashes. Native journal UUID-derived IDs and V2 identity bytes are unchanged. Duplicate/missing setup or trade associations refuse. Partially initialized state retains INITIALIZING and cannot be reopened as READY or automatically reinitialized. The association pin is fixture consistency,not trusted authority or rollback resistance.

Native journal bytes remain immutable. Native manual snapshots retain version1 and original plan status/fields,with an additive `fixture_v2` object containing shared ID,projection schema,canonical source digest and partial-accounting projection. No mixed partial position becomes a fabricated V1 full close. Even after the fixture ledger closes,legacy journal OPEN/manual ENTERED remain explicit;new version-aware projection says CLOSED_FIXTURE_LEDGER_ONLY. Old callers remain unchanged and cannot use this as operational flat-state evidence.

### Separate revisions

- Global source revision counts acknowledged V2 fill events across the selected inventory;it is distinct from the original pinned V1 journal row count/hash.
- Per-position revision counts committed fills for that shared position. An ETH request at position revision0 remains valid after a BTC fill advances the global source revision.
- Applied source revision records the globally projected view in the current native snapshot. Each plan separately records applied position revision and its position revision.

Three positions with partial and final exits produce source revision6,position revision2each,and applied source revision6. All three are independently checked against canonical event replay and native operation receipts on restart. Booleans are not valid revision integers. Hashes alone do not validate missing associations or source completeness.

### Acknowledgement and failure boundaries

`record_exit` freezes the explicit V2 facade request,requires expected per-position revision and commits an outer pending native-operation intent under a bounded SQLite transaction. It then uses the existing V2 fill adapter's intent/ledger/acknowledgement protocol,projects the verified view through actual disposable `ManualPerpStateStore.save`,verifies its load,then commits the facade head/revisions and final receipt together. Success returns only after that final commit. Original exceptions propagate.

An acknowledged identical operation returns its immutable receipt without another fill or projection. A conflicting duplicate,stale position revision or substituted identity refuses. One unacknowledged native operation blocks further facade operations,snapshots and complete reporting,including when canonical financial persistence already succeeded. The implementation has no automatic repair,replay,projection rebuild or uncertainty-clearing method.

Stale price rejection after outer intent conservatively leaves that intent unresolved,even if no ledger fill occurred. It does not silently reset to ready or authorize another financial callback. Distinguishing a durable REJECTED state is deferred;current behavior sacrifices availability rather than inventing recovery permission.

Native snapshot failure retains its own pending/temp evidence plus the facade intent. An interruption after projection publication but before facade acknowledgement does not imply successful completion. After a durable final receipt,identical retry reads it without replay. Process crashes before intent can retry because no operation was admitted. Existing independent V2 financial replay/audit,cash evidence and immutable daily reports remain in use. The facade report additionally binds the association and applied source revision and refuses pending operations.

### Source and integrity checks

Every ready read verifies association/head integrity,original native journal bytes,native in-memory economic identity,complete manual setup/trade association roster,current manual hash,all canonical events/fills,receipt lineage and source/position/applied revisions. Native instance IDs alone are insufficient:quantity,entry,risk and fee/slippage changes refuse. Missing or corrupted receipts,changed native files,projection rows or pinned association refuse. No record deletion or compensating synthetic fill is used.

This is cooperative disposable exclusion,not proof against privileged clients,external native writers,symlink/file substitution or coordinated rollback. Two SQLite commits plus a manual snapshot are **not** a common atomic transaction. SQLite FULL/fsync and abrupt process tests are not power-loss/hardware acceptance. Physical storage security,antirollback and trusted recovery remain D1 requirements;all-writer/process proof remains C1.

## Executable acceptance

New tests use actual PaperJournal class definitions with only the production singleton omitted by the existing reviewed test loader,and actual ManualPerpStateStore objects at disposable paths. No actual financial files are opened. Test children terminate only themselves at explicit fault hooks;no unrelated process or global termination occurs.

Coverage:three mixed long/short positions,fractional partial/final quantities,independent revisions,shared association persistence,duplicate/conflicting requests,concurrent calls,pending report refusal,stale revisions/prices,initialization interruption,corrupt head/receipt/manual/native source,changed native in-memory sizing,rehashed missing association and native snapshot commit without durability acknowledgement. Eight abrupt subprocess boundaries cover before/after outer intent,inner canonical intent,ledger commit,canonical acknowledgement,manual projection,outer acknowledgement commit and after final acknowledgement. Restart never blindly replays unknown callbacks.

The first run reached16passes then1failure because the corruption test expected ValueError/KeyError while the native snapshot correctly raised its documented ManualPerpStateError. The assertion was corrected to explicitly include that store error;failure log preserved at logs/diagnostics/hl-n1-first.txt. It was not an application acceptance failure or a suppressed exception. An intermediate run passed24tests before the last association/stale-price cases. Targeted import formatting and set-comprehension lint findings were corrected without suppression. Final exact combined results are appended below;overlaps are not added.

A source AST regression confirms no other backend module imports the facade. Native caller and startup files remain unchanged;this is absence of integration,not proof against arbitrary external Python invocation. The existing Python startup lock and all21decision hashes are independently checked by the checkpoint verifier. Existing V1 regression selections remain included;native journal bytes are asserted unchanged by N1 fixtures.

## N2–N6 boundaries and continuation

| Step | Remaining dependency | Current decision |
|---|---|---|
| N2 | Independently complete original source archive,opening cash/exposure,witnessed adoption mapping and discrepancy reconciliation;explicit actual-record access/migration scope | B1 BLOCKED;no real records or migration authorized. |
| N3 | Exact actual process/writer/resource ownership,entry-versus-exit gate split,all-writer drain/quiescence and lifecycle acceptance | C1 BLOCKED;fixture facade does not wrap production writers. |
| N4 | Protected storage/projection namespaces,independent trusted authority,clock,revisions/rollback and authorized recovery | D1 BLOCKED;no ACL/registry/key/TPM changes. |
| N5 | Approved native dispatcher/service/API/reader integration and version-aware V1/V2 routing;accepted historical adoption and crash protocol | Protected runtime integration separately required;unchanged native callers cannot consume this prototype operationally. |
| N6 | Provider usage/display/storage rights,budgets,backup/isolated restoration,native lifecycle and explicit supervised first-session authorization | E1 BLOCKED;no provider/service/PAPER startup authorized. |

N1A association/revision foundation,N1B disposable native projection/crash acceptance,N1C combined validation/checkpoint/publication are the only selected subtasks. After verified completion,no further N2–N6 work is implied by N1 permission. Exact next engineering action:review this facade's interface,revision and pending-publication policy for a separately scoped controlled-integration proposal;actual dispatcher changes and record migration require their own approval and independent evidence. Do not repeat M1–M3 or claim a fixture acknowledgement is production authority.

Production NO-GO;PAPER startup authorization NO;B1/C1/D1/E1 remainBLOCKED;all21governance decisions unchanged;Phase2HOLD,Phase3BLOCKED;AFIacceptance unchanged. All historical roadmap sections and original evidence retained. No protected services,providers,Docker,Genesis,trading orDiscord activated. No actual financial records,protected configuration,startup permissions or lifecycle deadlines changed.


## Final validation and preserved failures
One final combined run:412passed,0failed,0skipped in136.88s (logs/diagnostics/hl-n1-final-combined.txt),including27N1cases plus385existingneighbors. Earlier411combinedpassed preceded the report-lock correction;not added. Focused27passed,overlapping the final selection;not added. Targeted Ruff2files,compile2files,checkpoint PowerShell parsing and CRLF-aware diff checks pass. A final nested-with lint correction is mechanical test-only;its same admission-lock assertion is retained. No frontend change;prior763JSretained/notrerun.

A concrete cooperative report/admission gap was separately reproduced:after snapshot validation the report did not retain facade admission through publication. Original failing lock-proof test retained in hl-n1-report-race.txt. The facade now holds its bounded SQLite admission transaction through reporting;the test verifies a second writer cannot acquire that lock. This only serializes cooperating facade admission;independent ledger/native writers still require C1. No lifecycle deadline changed.

Original PaperJournal,ManualPerpStateStore,manual service,existingV2adapter and main lifespan source match base;no protected runtime imports/callers were changed. Every27N1test passes;no final failed/skipped cases. Native snapshot exception-type failure and reproduced report-race failure remain preserved locally.

Verified final checkpoint:{"stage": "hl-native-facade-N1C", "backup": "D:\\Work\\Project Atlas\\PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261023-215420-c2ff60da.bak", "backup_equal": true, "exact_readback": true, "outside_managed_equal_to_base": true, "roadmap_sha256": "b4b17d0be00c8b85793918b4825c9393e82c62bc3b812384bcd64a01fa964413"}. Backup equality,exact input read-back and historical bytes outside managed section match base3bc30a29. Complete seven-phase roadmap and all21decision hashes preserved;Python startup lock unchanged.

Files changed:new native fixture facade;new test_hyperliquid_native_fixture.py;this continuation;masterroadmap;autonomousstate/queue;first-session dependency plan;21gate readiness supplement. Only8reviewed files eligible for publication. Logs,generated financial fixtures,backups and unrelated local files excluded/preserved.
