# Quality Dips enrollment bootstrap V1 - 2026-10-24

## Authority and implementation

SOURCE ONLY. B1/C1/D1/E1 remain BLOCKED. PAPER startup NO; production NO-GO. Windows-local, no VPS or live-money implementation. No account, credential, operational directory, issuer, key, service, financial record or bridge installation was provisioned. Original alien frontend and protected startup remain unchanged. Synthetic control witnesses are test models, not independent authority.

Implemented files:
- scripts/observation_runtime/quality_dips_enrollment_bootstrap.py: dependency-injected enrollment intent, authenticated publication witness/readback and short-lived enrolled launch plan.
- scripts/windows/Atlas-SelectedPaper-EnrolledLauncher.ps1: source-loaded, explicitly injected launcher using the existing retained-child bridge; default invocation refuses.
- tests/test_quality_dips_enrollment_bootstrap.py: 46 focused cases, including real disposable child lifetime and graceful closure.

The bootstrap reuses QD_OP_ENROLLMENT_V1 validation and the existing operational read composition. It requires account/epoch/policy/resource/release scope, independent issuer, durable publication witness authority and trusted clock. Preparing a pure intent also requires read-service acceptance. Publication verification requires authenticated ACKNOWLEDGED state, native verified genesis readback, exact current pin, source and projection revision zero, no positions, cash1000 and zero gross/cost/net. Active/legacy account adoption is refused. No disposable schema is reclassified.

## Publication interface and failure semantics

QD_OP_ENROLLMENT_INTENT_V1 binds enrollment, policy, resources, release, executable and READ_ONLY capability. Its deterministic operation identity is once per account/epoch, independent of release upgrades or substituted resources. The issuer must authenticate the exact entire scope; changed payload under that identity is a conflict, not a new enrollment.

issuer.lease(scope,now).check and publication.lease(scope,now).snapshot/check are injected trust interfaces. QD_OP_PUBLICATION_WITNESS_V1 binds intent_digest, operation_id, resources_digest, state, ack_id, current_digest and acknowledged_at. Missing/untrusted/stale/rolled-back custody refuses; PENDING, UNKNOWN, FAILED and previously ACKNOWLEDGED work cannot be prepared again. Only acknowledged genesis may produce QD_OP_ENROLLED_READ_READY_V1 or QD_OP_ENROLLED_LAUNCH_PLAN_V1. Issuer/custody continuity and clock monotonicity are checked after the action as well as before it. Plans expire within30s and are not bearer credentials.

The one-time publisher is intentionally an UNIMPLEMENTED, separately accepted effect interface. Before any implementation/provisioning, its reviewed contract must:
1. Independently reserve the account/epoch operation and immutable intent digest using durable compare-and-swap; concurrent conflicting requests refuse.
2. Retain durable PENDING before touching new resources. Never initialize missing resources from a read path.
3. Publish the accepted QD_OP inception, initial projection and V2 calendar report using exact creation-handle identities and existing financial replay/audit, without rewriting original evidence.
4. Verify immutable bytes, physical identities, revision0 and report coverage; publish independently held current/high-water evidence and durable acknowledgement bound to this intent.
5. Retain UNKNOWN for publication/commit-before-ack failure. Crash/restart never resets the witness to UNPUBLISHED or blindly repeats financial effects. An independent recovery decision is required.

No publisher method, operational issuer, provisioning routine, default dependency loader or financial command was added. The source bootstrap verifies an externally acknowledged publication; it cannot make one. The source-only milestone satisfies interface preparation, not enrollment or writable runtime integration.

## Enrolled launcher

QD_OP_ENROLLED_LAUNCH_PLAN_V1 binds account/epoch, operation, enrollment/policy/publication/release digests, explicit local executable and bounded clock window. New-AtlasEnrolledReadBridge requires AcceptedPlan, independent Authorize, TrustedClock and AcceptedChildFactory. PREPARE authorization occurs before factory invocation. The factory is an explicitly trusted dependency, not a user-controlled executable resolver; it must enforce reviewed release bytes and complete C1 ownership/resources. RETAIN authorization follows verification of retained actual Process PID, creation FILETIME, executable image and account/epoch/enrollment context. Each read bridge action rechecks authority. Observed identity alone does not grant ownership.

No default Start-Process, operational command line, GUI installation or backend registration exists. SourceLoadOnly imports definitions, not authority. Default script and existing desktop invocation refuse. Accepted factory must launch the actual interpreter directly, not infer child ownership from a venv redirector. Existing bridge verifies HTTP readiness before the Control Center opens the browser. Existing read host keeps all financial POSTs disabled and legacy mutating research GET unavailable.

Failure before factory means no child is created. On failure after exact retained-child verification, only that child receives graceful stdin EOF with the existing12s close budget. No forced termination. An unverified process is returned on the error for owner reconciliation without action. If graceful cleanup fails, the original failure retains the Process object and secondary shutdown error; ownership is not discarded. No operational lifecycle deadline changed.

## Tests and retained failures

Final combined run:193 passed,0 failed,0 skipped. This includes46 new bootstrap/launcher cases plus147 neighboring policy/operational/selected-policy/startup-lock cases. Earlier43/46 runs overlap; do not add them. Three real Windows protocol-only subprocess cases verify accepted bridge creation/repeated graceful close, independent RETAIN refusal with exact-child cleanup, and mismatched identity refusal with retained ownership. Four Windows refusal cases verify no factory use for absent dependencies, denied authority, stale plan and default invocation. No HTTP listener, browser, GUI or financial writer was launched by these new tests.

Three abrupt subprocess tests persist a disposable control-witness JSON then exit71; restarted bootstrap refuses PENDING/UNKNOWN and accepts authenticated ACK readback without reenrollment. These are injected test-authority models, not actual independent custody, financial publication crash tests or physical power-loss evidence.

Initial run:32 passed then1 setup error due sandbox temporary-directory allocation outside the workspace. Retained diagnostics record the failure; confined --basetemp resolved it without changed assertions. Subsequent final193 run is authoritative. Existing symlink privilege1314 limitation remains NOT EXECUTED from retained prior native evidence; no new symlink/ACL/native-financial security acceptance claimed.

Targeted Ruff2files, compilation2files, PowerShell launcher syntax and Git diff checks pass. PAPER-only static audit:558runtime source files,0issues. Prior native operational reader/real HTTP/browser evidence was not rerun or recounted here. Current tests grant no runtime authority.

## Concrete operator acceptance checklist - all unassigned/unprovisioned

Proposed locations only, NOT CREATED: D:/AtlasRuntime/releases/<accepted-sha>; D:/AtlasPaper/QualityDips/<accepted-epoch>/source,projection,report,control. Operator must approve exact paths, local volume/ancestor handles, physical identities and exclusion from legacy/dev/test roots. Names are not enrollment evidence.

| Item | Required named decision/evidence | Present status |
|---|---|---|
| B1 scope reviewer | Independently accept fresh1000USD hypothetical epoch, all legacy exclusions/unresolved obligations, eligible ranked stocks/ETFs,100entry,oneposition,manual,long,fractional/no-scale/overnight and synthetic2bpsfee+2bpsslippage assumptions | UNASSIGNED;operator intent retained,not accepted |
| C1 ownership reviewer | Exact release/command,parent/actual child/creation handles,resource roster;all selected financial writers excluded from read-only service;no same-user arbitrary-writer guarantee | UNASSIGNED;no actual process observation authorized/performed |
| Windows principals | Named operator/reader/publisher/custodian identities and SIDs;least privilege and independently reviewed owner/SYSTEM DACL/ancestor/namespace policy | UNASSIGNED;no Windows account/ACL/service changes |
| D1 enrollment issuer | Authenticated scope,expiry/revocation and single-use publication issuer mechanism,independent acceptance | UNASSIGNED;no credentials/keys created |
| D1 current/high-water custodian | Durable operation CAS,external-to-rollbackable-data continuity/acknowledgement custody;source-cut pin receipts | UNASSIGNED;local hashes are insufficient |
| D1 clock custodian | Authenticated UTC/freshness,monotonic sequence,discontinuity/outage refusal | UNASSIGNED;wall clock alone unaccepted |
| D1 recovery custodian | Witnessed backup/isolated restoration and abandoned/UNKNOWN publication decisions;physical remapping accepted separately | UNASSIGNED;no copied-pin authority |
| Read-service reviewer | Exact enrollment/process/session/resource/read-only acceptance with expiry and revocation;owned launch/close demonstration | UNASSIGNED;source interface only |
| E1 data/release | Licensed provider/feed rights,price/ranking/corporate-action/session acceptance plus separate connection and supervised PAPER release approval | BLOCKED;no provider contacted |

Exact next permission: authorize source-only implementation of the concrete one-time publisher and actual issuer/custody integration only AFTER naming their independently reviewable mechanisms and acceptance scope. Then separate permission must name new approved roots and principals for provisioning; record native identities and independent receipts; separately authorize observations,read-only bridge installation and supervised read-only launch. This request cannot provision or authenticate these resources. No repetitive demo is needed while those dependencies remain unavailable.

First supervised read-only launch sequence: accept B1 scope/exclusions and C1/D1 actual resources/ownership/issuer/clock/current/recovery evidence; separately authorize publisher/provisioning and verify durable genesis ACK; install reviewed injected bridge with exact release; explicitly authorize supervised read-only host launch; validate GET/identity/readiness/originalUI/no mutations/owned close. PAPER commands/providers require later distinct E1 and writer/routing permission. Trial counters remain0of7days and0of30-60sessions.

Seven phases unchanged:1coreincomplete;2EvidenceEngine/AFIHOLD0of10accepted;3BLOCKED;4CrossMarketpending;5historicalSaaSdeferred under Windows-local/noVPS;6institutionalpending;7commercialpending. All21governance decisions/startup locks/frontend/legacy evidence preserved. State zeroACTIVE/BLOCKED_WAIT at genuine authority/provisioning boundary.
