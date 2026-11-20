# Quality Dips one-time financial publisher V1 - 2026-10-24

## Implemented, not installed or authorized operationally

Source-only OneTimePublisher and NativeGenesisFiles implemented in scripts/observation_runtime/quality_dips_one_time_publisher.py. Tests in tests/test_quality_dips_one_time_publisher.py use confined disposable NTFS roots and explicit SYNTHETIC authority models. No operational publication, account opening, real-directory access, provider connection, service, bridge installation or startup occurred. The 13 provisioned directories and their private identities were not used by this implementation/test run.

Intended future target remains the exact previously provisioned epoch in private evidence, and existing release directory1cbf5d4d94f6f60f17b7b4b25dd6d434ddf67e43. Neither was regenerated, modified or enrolled. Source code intentionally does not hardcode machine-specific epoch/paths/IDs as authority. Future accepted enrollment must bind those exact real resources;the empty release directory is not an installed copy of this source commit.

B1/C1/D1/E1 remain BLOCKED. All21decisions, D:-only/existing-account/noVPS/PAPER-first/no-live-implementation policies, startup locks and alien UI unchanged. PAPER startup NO;production NO-GO.

## Publication flow and authority requirements

1. Existing EnrollmentBootstrap.prepare verifies independently accepted issuer/scope, authenticated UNPUBLISHED witness and read-service acceptance before publication. Its existing deterministic operation_id is once per account/epoch;changed enrollment/resource/release is a conflict,not another account initialization.
2. Require explicit custody, ownership, observer and files interfaces. Publisher custody must be the exact same publication interface used by bootstrap,both at construction and invocation. There is no default issuer,custodian,resource loader or command endpoint.
3. Authenticate a QD_OP_GENESIS_WRITER_V1 context binding exact intent digest and independently observed PID/creation/image. Issuer and ownership leases revalidate before and between effects. Trusted clock must remain nondecreasing and within30seconds;process changes,revocation,clock rollback and custody loss refuse.
4. custody.reserve(intent,writer,now) must atomically persist an exclusive once-per-account/epoch PENDING before yielding. Returned QD_OP_GENESIS_PENDING_V1 binds operation,intent,writer,state and durable acknowledgement. Structural pending_durable=True is NOT authority:txn.check must independently authenticate the reservation/monotonic custody. This repository supplies no real implementation of that trust/custody service.
5. Open only existing accepted native source/projection/report directories. Compare exact root IDs,require empty namespaces and protected native owner/SYSTEM ACLs. No directory creation,repair,legacy adoption,overwrite or recovery API. A conflicting file or foreign root leaves the reserved operation uncertain and blocks replay.
6. Exclusively create inception.json,projection.json and report.json via existing WindowsOutput.write_bound creation handles and FlushFileBuffers. Files bind native identity,canonical bytes and schema. Verify namespace,ACL,link,identity and contents after each publication. This is three immutable file writes plus a commit protocol,NOT an atomic multi-file filesystem transaction.
7. Reuse existing QD_OP contracts,initial(),replay() and history();no second accounting engine. Genesis source revision0 has no financial commands/positions;cash1000,gross/cost/net/net-R0. Long-only cash account introduces no supported borrowing or legacy obligations. This does not assert unresolved legacy obligations are closed;B1 exclusion acceptance remains mandatory.
8. Build source/projection/report pins and generation1 current candidate. txn.commit must durably authenticate QD_OP_GENESIS_COMMIT_V1 binding operation,intent and exact current digest. Candidate status fields are not independently issued ACK authority before custodian acknowledgement.
9. txn.acknowledge must durably publish the current/high-water and return the same QD_OP_PUBLICATION_WITNESS_V1 consumed by existing bootstrap. Bootstrap.verify_publication runs existing read-only composition/native decoding/independent replay/report reconciliation. Only matching acknowledged publication/current digest produces a successful result. No success before this boundary.

## Documents and receipt compatibility

Existing QD_OP_ACCOUNT_V1 bytes are the immutable inception document;no financial record schema relabeling. QD_OP_SOURCE_PIN_V1 revision0 contains exact inception binding and no records. Projection uses QD_OP_PROJECTION_DOCUMENT_V1 with existing initial financial state. Report uses QD_OP_REPORT_DOCUMENT_V2, America/New_York, authenticated cutoff and existing history generation. Genesis cutoff-day report is INCOMPLETE because a current calendar day is not completed;valuation remains unavailable. No premature COMPLETE report or invented inception timestamp:initial last_clock0 remains a replay sentinel,not account creation time.

File bindings and current/report pins match the existing native reader. External commit/witness receipts bind the enrollment intent and actual native file identities through the current digest. Durable receipt storage is the accepted injected custody's responsibility,not locally generated hashes or test JSON. Authenticated commit and publication time/current custody remain independent requirements.

## Crash, failure and no-replay behavior

Any partial write,failed native readback,clock/process change,failed commit or missing acknowledgement yields PublicationUnknown. The publisher asks custody to persist UNKNOWN;failure to persist that marker preserves the original and custody-error exception chain and still cannot return success. Existing durable PENDING must continue blocking replay. Entering/exiting a reservation can itself fail after persistence;those ambiguous failures also return UNKNOWN. No automatic rollback,delete,reset,retry or recovery method exists.

A hard process exit cannot execute exception cleanup. Restart must interpret an unacknowledged durable PENDING/COMMITTED reservation as uncertain and refuse publication. If acknowledgement was durably published before process exit,bootstrap may verify it read-only,but publisher still refuses reenrollment. Different callers must share an independently durable CAS/reservation and high-water authority;local hashes alone cannot guarantee this. Nonparticipating same-user/admin writers remain a separate C1/D1 threat-model limitation.

## Tests actually executed

Final combined run:241passed,0failed,0skipped. Breakdown:33new publisher cases,46existing bootstrap,54operational contract,37selected policy/accounting,68PAPER policy,3production lock. Earlier26/30/238/240/241 runs overlap and are not added. Native APIs genuinely ran on Windows within the new qd-publisher-* diagnostics root;no browser/HTTP host or operational resources used.

New coverage includes native successful genesis plus actual bootstrap/native-reader readback;exact1000/zero positions/P&L;duplicate refusal;conflicting intent;five missing dependencies;unaccepted issuer/owner/stale/rollback;partialsource/projection/report;commit/ack failures;clock discontinuity/custody loss/process revocation;legacy/nonempty roots;foreign rootID/broadACL refusal;concurrent requests withoneexclusive reservation andthreefiles;unacknowledged PENDING;UNKNOWN persistence failure with original exception context;split bootstrap/publisher custody refusal;default CLI refusal.

Three abrupt real subprocess exits cover beforecommit,aftercommit/beforeack,andafterack. Restart uses existing disposable files and durable synthetic control ledger;no duplicate native files or financial callback replay. Test control JSON uses exclusive creation and flush/fsync solely as an explicit test-authority model. These tests do not demonstrate independent operational custody,physical power-loss durability or protection against all hardware/filesystem failures.

Initial test failure was a missing available field in the reused synthetic acceptance helper;retained locally and corrected without production changes or weakened assertions. Targeted Ruff2files,compilation2files,checkpointPowerShell parsing,diff checks pass. Static policy scanner559runtimefiles0issues. Existing privilege-dependent true-symlink limitation remains NOT EXECUTED from prior evidence;not retested or promoted. No operational writer/process ownership acceptance claimed from disposable tests.

## Remaining evidence and exact next permissions

Implemented publisher is source-capable only;no accepted operational issuer,reservation/high-water custodian,clock or writer authority was installed. Same-account/sharedD:limitations from the permanent deployment decision remain unresolved. In particular a rollbackable local test ledger or copied current pin cannot become independent custody just because the publisher accepts an injected interface.

Before actual financial inception:
- Independently accept B1 new epoch/policy and all legacy exclusions;never adopt unresolved legacy obligations.
- C1 review actual accepted release,writer/process/resource roster,exclusive admission,nonparticipating-writer limitations and shutdown/restart ownership.
- D1 review and authenticate actual issuer,reservation/current/high-water/clock/recovery interfaces and native resource identities;accept or resolve sharedD:/same-account/backup limitations without waiving a gate.
- Separately authorize installing those accepted dependencies and ONE real financial inception publication against the already provisioned epoch. Do not rerun directory creation or use test builders/authorities. Permission must name the exact existing private epoch/root identities,issuer/custody,reviewed process/release and failure/recovery scope.

After a genuinely acknowledged genesis, separately authorize bridge installation and supervised read-only launch with accepted service/process authority. Reuse original ControlCenter/selected view;all financial POSTs stay refused. E1provider rights/connection permission,ranking/executable price evidence and separately approved manual financial routing remain later steps. Seven-day0of7 and extended0of30-60sessions;no trial started. No redundant demo/framework or live-money implementation is required or introduced.

## History and publication

Master checkpoint updated through approved updater,byte-equal backup/exact read-back/outside-managed bytes and prior managed history preserved. State/queue retain previous directory reconciliation,historical failure,all21decisions/sevenphases and gate blockers. Existing operational directories untouched;native reader/bootstrap/UI/startup/policy bytes unchanged. Only two new source/test files and reviewed documentation/state published;diagnostics,synthetic records,actual machine identities and private financial evidence excluded.
