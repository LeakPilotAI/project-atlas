# Native Operational Reader + Windows Bridge V1 â€” 2026-10-24

SOURCE IMPLEMENTED / DISPOSABLE WINDOWS VERIFIED. Base3601659653328a5c7c3a609ed64cd5a6114d8f8f,chatgpt/atlas-rebuild-v1. No operational installation/enrollment/authority. B1/C1/D1/E1BLOCKED;all21decisions unchanged;PAPERstartupNO;productionNO-GO.

## Exact implementation files

- scripts/volume_inspector/operational_financial_read.py: NativeOperationalReadPort.read_operational/verify_operational; existing-only native identities before bytes, canonical operational schema, complete namespace, authenticated custody/clock/current high-water, replay/audit/report checks. No write/create/repair/recovery surface.
- backend/app/investment/quality_dips_operational_replay.py: bounded operational replay using existing Decimal arithmetic kernel and independent auditor; partial/full accounting, execution evidence, receipts, per-prefix independent audit, IANA event/cutoff-day history. No dispatcher or storage.
- backend/app/services/paper_financial_replay.py: optional explicit command_schema/receipt_schema on internal kernel. Historical defaults/public manifest validation unchanged.
- backend/app/services/paper_financial_audit.py: optional internal audit-row schema. Historical public validation/default unchanged. Auditor does not call transition/replay.
- backend/app/investment/quality_dips_operational_contract.py: separate report pin/document V2 support, V1 preserved, explicitly view-only original UI report mapping.
- scripts/observation_runtime/quality_dips_windows_bridge.py: injected stdio OPEN/VERIFY/CLOSE server; no default CLI/trust/enrollment/provider/writer. Exact process/host/sequence, graceful EOF.
- scripts/windows/Atlas-SelectedPaper-Bridge.psm1: New-AtlasSelectedReadBridge takes a retained exact Process, frozen expected context and authorization callback. Native identity, serialized bounded stdio, strict responses/uncertainty latch, graceful exit; no process creation/kill/enumeration.
- tests/test_quality_dips_native_operational_reader.py:52confined cases,51passed1NOTEXECUTED; genuine Win32/HTTP/PowerShell/direct-child tests and actual ControlCenterOpen/Close functions, browser stubbed.

Five continuity files: this report, QUALITY_DIPS_NATIVE_READ_BRIDGE_CONTINUATION_2026-10-24.md, PROJECT_ATLAS_MASTER_ROADMAP.txt, ATLAS_AUTONOMOUS_STATE.json and ATLAS_AUTONOMOUS_EXECUTION_QUEUE.md. Original GUI/selected router/composition/static assets/startup/FS2/test-pin readers unchanged.

## Native protocol

Injected custody lease authenticates the complete QD_OP_READ_BUNDLE_V1, enrollment/current/process/host and clock before opening files. Native boundary independently compares current with authenticated current, then rechecks custody/process/host/time after verification. Shared/nested authenticated read leases are required; caller objects and local hashes are not independent authority. A genuine lease must cover all writers/exclusion and rollback continuity.

Existing-only WindowsOutput holds no-delete ancestor/root handles; root identities match enrollment. read_bound checks exact native file identity, protected ACL, single link and bounded size before ReadFile, digest before canonical JSON/schema decode. Exact bounded namespace refuses missing/foreign/newer records. verify_operational performs a fresh load/replay/audit, not cached TRUE. No path-based SQLite, source adoption, repair or creation.

Source layout: inception.json exact QD_OP_ACCOUNT_V1; up to128 numbered NNNN-record.json. QD_OP_FINANCIAL_RECORD_V1 fields: enrollment_digest,revision,operation_id,predecessor,command,receipt,commit,ack. Predecessor is the accepted preceding physical QD_OP_FILE_BINDING_V1. Commit QD_OP_COMMIT_V1 binds revision/event_digest; ack QD_OP_ACK_V1 binds commit_digest/projection_state_digest/statusACKNOWLEDGED. Current pin binds all physical records. Duplicate IDs, missing/UNKNOWN ack, contradictory predecessor/receipt/revision refuse. This is a reader specification, not a financial writer or independently witnessed publication chronology.

Operational commands/receipts are QD_OP_COMMAND_V1/QD_OP_RECEIPT_V1; no FS2/test-pin translation. Pure arithmetic uses neutral parameters, fixed28-digit HALF_EVEN and Inexact refusal. Entry eligibility QD_OP_EXECUTION_EVIDENCE_V1 includes instrument_id,symbol,asset_class,fractional_supported,ranked_at,ranking_revision,execution_eligible. Stock/ETF, manual/long-only/no-scale-in,100USD/one-position/cash/freshness rules checked during replay. AAPL/SPY/QQQ cases prove no MSFT-only allowlist. Financial custody does not authenticate provider/ranking origins or waive B1/E1. Existing synthetic2bps fee+2bps slippage per side retained. Independent audit checks each prefix.

## Historical/report/UI compatibility

V1 reports contain only status, insufficient for historical audit. Separate QD_OP_REPORT_PIN_V2/QD_OP_REPORT_DOCUMENT_V2 add timezone,cutoff,history to enrollment_digest/source_pin_digest/revision/status. Existing V1 remains supported by contracts; new native reader refuses it as insufficient historical evidence. No historical bytes/layout rewritten.

V2 requires America/New_York and cutoff between last source event and trusted now; exact deterministic rows for every event day plus cutoff day. Rows bind date/start/end/effective exclusive end, source prefix revisions, opening/closing cash, realized gross/costs/net, open positions and unavailable valuation. Every snapshot is independently audited; DST25-hour fall-back tested. ACCOUNT_V1 has no creation timestamp: zero replay last_clock is only an ordering sentinel, never invented inception evidence. No fabricated no-activity calendar archive is claimed. Cutoff day's incomplete period remains INCOMPLETE; overnight positions remain open.

The original frontend validator exposed a mismatch with raw operational report envelopes. After native audit only, capability maps the latest V2 row to existing FS3_DAILY_REPORT_V1 **UI presentation** with view_only=true, operational_source_schema/digest and history. No retained FS3 source artifact is created or relabeled, and native trust remains operational only. V1 without daily evidence gives no report. Unsupported fee/slippage breakdown and valuation stay unavailable. Actual HTTP response passed the actual unchanged quality_dips_selected_paper.js validator. No theme/navigation/static changes or genuine browser/GUI acceptance.

## Windows bridge and ownership

Normal desktop/ControlCenter invocation still has no AcceptedSelectedReadBridge and refuses. The new factory is not installed/imported by a default launcher. Separately accepted launcher must retain the actual child, explicitly inject all enrolled dependencies and pass the bridge into the existing GUI hook. No CLI/environment/file authority loader exists.

PowerShell compares retained child's PID, creation FILETIME and image; separate authorization remains mandatory. Native observation is not independent ownership. Python checks exact context and sequence; OPEN waits for genuine loopback HTTP host/process readiness. Existing ControlCenter calls VERIFY before browser. All financial POST and legacy mutating research GET routes stay denied.

QD_OP_BRIDGE_CONTEXT_V1: host_id,process,account_id,epoch,enrollment_digest. QD_OP_BRIDGE_COMMAND_V1: sequence,host_id,process,action,ready. QD_OP_BRIDGE_RESPONSE_V1: sequence,status,ready. Strict versions/keys reject duplicates, escaped keys and noninteger sequences. Monitor serializes requests. Unknown transport response latches replay refusal; only exact-owner graceful stdin EOF/confirmed exit can clear it. CLOSE/EOF may close the retained read-only listener after financial custody expires; never grants financial or clean PAPER-session authority. No forced/global/name/port-based termination. Readiness15s/owned close12s reuse existing bounds; no protected deadline changes. Restart requires fresh process/composition/host; no automatic restart.

## Validation

Final combined **311Pythonpassed0failed1skipped/NOTEXECUTED**,51.50s:52new(51pass1skip),54operational-contract,29pure-read,74selected-integration,37selected-policy,37FS1,3startup-lock,26existingdisposable read-service cases. True-symlink privilege1314unavailable, never PASS. Junction and hard-link probes executed in confined resources. JavaScript **25passed0failed0skipped**. After combined, successful bridge fixture strengthened to call actual ControlCenterClose;10overlappingbridgecases passed15.23s,not added to310. Ruff7/compile7/PSparse4/diff pass.

Covers exact identity before ReadFile, wrong/missing/coherently corrupt records/ack/predecessor/receipts/totals, stale/revoked/substituted custody, namespace/hardlinks, current continuity, concurrent reads, process/clock changes, partial/full exits, overnight/cash/report reconciliation, DST and ambient precision; genuine HTTP GET/POST/legacy refusal, released port/fresh restart; PowerShell native PID/creation/image/authority/host refusal, duplicate opens, strict malformed replies, uncertain replay refusal and exact graceful close. Browser opening is stubbed; no real browser/native GUI or operational acceptance.

Original run23pass1fail: venv launcher PID/image differed from actual child. Read-only comparison proved the parent/child mismatch; fixture starts actual interpreter directly with test dependencies. No ownership check weakened. Reproduction retained locally. Intermediate29pass,300pass1skip and10strict-bridge overlap final cases, not additive. Mistaken Ruff-on-PowerShell invocation corrected to native parsing. No hidden failure or altered financial security assertion.

## Remaining independent evidence and shortest next step

B1: independent isolated hypothetical1000USD account/epoch, eligible ranked stock/ETF/100USD/one-position/manual/overnight/synthetic-cost scope and legacy exclusions/unresolved obligations acceptance.

C1: accepted actual parent/real-child/resource identities, complete writer roster, nonparticipating-writer exclusion, read-lease/lifetime/drain evidence. Matching process metadata does not grant ownership.

D1: actual independent enrollment/issuer/session/current-highwater custody and trusted clock; rollback continuity beyond coherent local hashes; protected native resources/ACL/namespace, abandoned-writer/recovery and operational-format backup/restore. True-symlink unexecuted evidence remains unaccepted. No claim of universal same-user/admin or physical power-loss protection.

E1: provider rights, executable-price/session/corporate-action evidence, recovery and supervised release permission for eventual market/PAPER operation. No providers contacted.

Next: independent source/native-evidence review and named actual Windows identity, account scope, resource roots and custody/clock/issuer owners; then explicit bounded enrollment/bootstrap/provisioning and bridge-install acceptance authorization. No operational-format source provisioner/financial writer exists here: do not use fixture builder as enrollment. Actual inception/report/pins require a separately accepted enrollment publication mechanism. Only after actualB1/C1/D1 resources/read-service acceptance and explicit supervised read-only launch permission should a direct-child composition be installed. Financial dispatch/providers/PAPER need later separate permission/E1. No issuer credentials, approvals or operational authorities manufactured.

## Preservation

Approved roadmap backup equality/exact readback/outside-managed bytes/prior checkpoint preservation verified. State/queue zeroACTIVE/BLOCKED_WAIT and old outcomes retained.34protectedhashes include every tracked original static asset, startup/manager/GUI/deployment policy and21decision matrix. Exclude local diagnostics, native IDs/pins, financial records and private logs from publication.

Seven phases preserved:1coreincomplete;2EvidenceEngine/AFIHOLD(AFI-1..10PENDING,0accepted);3BLOCKED;4CrossMarketpending;5historicalSaaSdeferredWindowslocal/noVPS/nocloud;6institutionalpending;7commercialpending. No Genesis access, operational launch or financial authority.

Final review: an isolated direct replay reproducer demonstrated numeric identity coercion (integer versus equivalent float). Canonical predecessor comparison now preserves types. The failing reproducer is retained. One earlier fixture assumption about a native index component was corrected before isolating this defect; attempts retained. Final311pass/1NOTEXECUTED includes the new regression.
