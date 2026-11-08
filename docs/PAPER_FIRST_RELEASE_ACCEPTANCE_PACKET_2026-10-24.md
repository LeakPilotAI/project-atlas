# PAPER-first release program and isolated Quality Dips acceptance packet â€” 2026-10-24

## Permanent operator decision / authority boundary

Atlas is single-user Windows-local research and PAPER trading. No VPS/cloud/remote production server or mandatory paid hosting. LIVE-MONEY IMPLEMENTATION IS OUT OF SCOPE: no real broker order placement/modification/cancellation, execution adapter, real-capital enrollment, PAPER-to-live promotion, live toggle or dormant live pathway. A future live-money phase needs a new explicit operator decision and separate implementation authorization. Historical proposals remain historical; unrelated legacy code remains unactivated/unrewritten. Existing CI checks and reviewed GitHub source publication are development tools, not hosted production.

This instruction confirms account intent, not independent B1/C1/D1/E1 acceptance, financial enrollment, provider permission or startup. All21canonical decisions remain unchanged. PAPERstartupNO;productionNO-GO;Phase2HOLD/Phase3BLOCKED.

Machine-readable policy: ATLAS_PAPER_RELEASE_POLICY.json; deployment policy adds the same permanent scope. Neither is an issuer credential or release token. New P1-P8 milestones supplement the21decisions, never replace/promote them.

## Verified account reconciliation

| Operator intent | Actual source evidence / limitation |
|---|---|
| New isolated1000USD hypothetical account;no legacy adoption | QD_OP_ACCOUNT_V1 / QD_OP_ENROLLMENT_V1 require account/epoch/policy and separate roots. No actual account/resources created. Complete independent legacy exclusions still needed. |
|100USD maximum new entry,one concurrently open position | validate_enrollment fixes policy; operational replay checks entry notional and open remaining quantities before accepting historical receipts. Native operational financial writer/routing still absent. |
| Eligible ranked stocks/ETFs,not MSFT-only | QD_OP_ACCOUNT_POLICY_V1 universe; execution evidence instrument/asset/fractional/rank/quote checks. Current provider/ranking issuer authenticity not accepted. AAPL/SPY/QQQ coverage retained. |
| Manual long-only entries/exits,no scale-in | Operational replay kernel requires manual commands,long-only,one open position; positions cannot silently merge. No working financial POST activated. |
| Fractional where supported;partial/full exits | Explicit fractional support and exact Decimal quantities; partial remaining and independent per-prefix audit. Existing compatibility/disposable tests,not operational acceptance. |
| Overnight holding allowed | Immutable source positions remain open across day reports; shutdown of read-only host never liquidates. Missing valuation stays unavailable. |
| Explicit synthetic fees/slippage | Existing2bpsfee+2bpsslippage per side; roundtrip cost=2*entry_price*exited_quantity*(fees_bps+slippage_bps)/10000,allocated on exits.100USD is entry notional,not a claimed executable all-in market-cost limit. Actual market costs/fills not authenticated. |

No financial behavior correction was needed for the selected parameters. This milestone changes source policy/validation/CI and documentation only. Existing runtime/financial writers/dispatch remain unchanged.

## Exact B1/C1/D1 acceptance packet

Each acceptance artifact must identify reviewer/custodian by name/role, authority and independence basis, date, reviewed release digest, account/epoch/resource scope, evidence references, conditions/expiry and explicit decision. Fields remain UNASSIGNED/UNOBSERVED until real evidence is provided. Codex engineering tests and advisory ChatGPT review cannot authenticate financial archives, Windows resources or operational authority. Do not manufacture a signature or mark generated JSON as approval.

| Requirement | Required artifact / concrete action | Producer and independent acceptance |
|---|---|---|
| B1.account | Operator confirms new account/epoch and exact policy above;reviewer accepts hypothetical inception,Decimal/cost semantics and explicitly unaccepted fill assumptions | Operator proposes;named accounting/scope reviewer independently accepts. No reviewer assigned here. |
| B1.exclusions | Complete signed-off scope inventory excluding every existing investment/prediction/perp/legacy account and unresolved N2 obligations;none declared closed,reset or adopted | Independently authenticated archive/scope custodian. No fresh private-financial inspection authorized in this task. Existing N2 discrepancies remain unresolved. |
| B1.publication | Bind approved hypothetical inception and actual immutable inception digest/physical identity,publication clock and report coverage scope | Accepted enrollment mechanism plus independent receipt witness. ACCOUNT_V1 lacks inception timestamp;do not treat replay last_clock0 as creation evidence. |
| C1.roster | Exact read-service parent and real child,release/executable/command,retained native handle/PID/creation identity,source/projection/report/control roots and resource roles | Operator names permissible process/resource scope;separately authorized read-only native observer produces evidence;independent ownership reviewer accepts. PID/image alone is insufficient. |
| C1.exclusion | Identify every selected-account mutator and all legacy scanner/mark/close callbacks;exclude legacy mutating research GETs and unregistered writers;prove writer/resource roster complete | Native ownership/security reviewer accepts actual ACL/principal/exclusion model and observed leases. Existing synthetic roster cannot certify actual writers. |
| C1.lifecycle | Accepted read-only lease,exact-child readiness and close,repeated open/close/fresh restart,revocation/timeout uncertainty;financial routing later needs entry-close/drain/report ordering | Named lifecycle reviewer plus operator supervised acceptance. No production process tests authorized by this instruction. |
| D1.resources | Propose new physical roots;verify volume/directory/file identities and protected DACL,ancestor handles,hardlink/reparse/substitution behavior before enrollment | Separate permission for named-root observations and later provisioning. Independent Windows security reviewer accepts actual resource proofs and residual risks. |
| D1.issuer | Identify the real enrollment/read-session issuer and validation mechanism;account/epoch/release/process/session scope,revocation and bounded validity | Operator names issuer/custodian;independent authority/security review. No key/account/certificate/credential creation now. |
| D1.current | Name current-pin/high-water custodian separate from rollbackable data/development changes;compare-and-swap revision continuity and restart/revocation evidence | Independent custodian/witness review. Local hashes/fixture authority or copied pins are insufficient. |
| D1.clock | Specify authenticated UTC source,clock sequence/freshness30s,monotonic discontinuity/rollback refusal and outage policy | Named clock authority and independent review. Windows wall time alone has not been accepted as trusted evidence. |
| D1.recovery | Operational-format backup manifest/source-cut/receipt custody,isolated restore,new physical-identity mapping,UNKNOWN/refusal and abandoned-writer decisions | Independently accepted recovery authority and witnessed isolated restoration. Existing disposable archival work does not accept operational enrollment or writable recovery. |
| D1.threat_model | Explicit trusted workstation/principal assumptions;separate mutation and custody authority where feasible;no claim against all malicious same-user/admin code | Operator and independent security reviewer must accept residual risk. Native owner/SYSTEM ACLs do not by themselves exclude arbitrary same-user writers. True-symlink case remains NOTEXECUTED(privilege1314). |

All reviewer/issuer/custodian names,actual resource enrollment IDs and genuine receipt references remain missing. No placeholder identity is an approval. B1 historical completeness is not bypassed by naming a fresh epoch;separate independent scope decision required,global governance unchanged.

## Narrow bootstrap/enrollment plan â€” NOT execution permission

Proposed locations only,not created: fixed reviewed release at D:/AtlasRuntime/releases/<accepted-sha>;new account at D:/AtlasPaper/QualityDips/<accepted-epoch>/{source,projection,report,control}. Operator must approve actual names/identities;do not infer enrollment from these paths. Keep mutable development,tests,caches and legacy financial roots separate. No legacy copy/adoption/migration.

1. Independent review of this packet and native reader/bridge evidence;assign scope/ownership/security/custody/clock reviewers and approve an explicit threat model.
2. Separately authorize SOURCE-ONLY enrollment/bootstrap implementation: reuse QD_OP contracts,native existing-only reader,WindowsOutput identity primitives and retained-child bridge. Exact files: new scripts/observation_runtime/quality_dips_enrollment_bootstrap.py (no default enrollment/issuer),new scripts/windows/Atlas-SelectedPaper-EnrolledLauncher.ps1 (explicit accepted dependencies),bounded tests. Do not build another accounting/bridge engine.
3. The bootstrap must consume independently authenticated enrollment/inception/current/session evidence;refuse absent authorities. A separately accepted one-time inception/projection/report publisher is required;there is no operational provisioner/financial writer today. Never use the synthetic test builder as operational enrollment.
4. Separate named permission to provision accepted directories/ACLs/principals/keys if the reviewed design requires them;then record native creation-handle identities and independent source-cut/current-pin receipts. No such provisioning authorized now.
5. Separate C1/D1 actual native observation/lifetime/namespace/lease/recovery acceptance. Launch the actual interpreter directly and retain its real Process handle: venv redirector's parentPID is not host ownership. No generic PID/name/port termination.
6. Only after B1/C1/D1 acceptance and explicit supervised read-only launch permission install the accepted bridge into the existing ControlCenter injection hook. Default desktop refusal and Python production lock remain intact. Test selected financial GET/health/UI and safe close;no command POST or provider refresh.
7. Subsequent separately authorized PAPER writer and manual-command dispatch/ranking-evidence publication implementation,provider rights/data acceptance,E1supervised release. Read-only success does not authorize it. No live-capital adapter or toggle at any step.

Minimum next request: name the real B1reviewer,C1ownership reviewer,D1issuer/current-pin/clock custodians and approve their evidence scope;then authorize the bounded source-only enrollment/bootstrap milestone above. Actual provisioning,observations,installation,provider connections and launch each need their named later permission.

## Measurable PAPER release program

P1-P8 are proposed measurable acceptance requirements,not independent acceptances. Exact evidence lists are also machine-readable. Preserve every attempted session/incident in denominators;never delete a bad run to claim a clean trial. No profit target,trade quota or invented fills;no-trade sessions may count only with accepted service/data/accounting evidence.

| Gate | Promotion evidence | Current progress |
|---|---|---|
| P1 authorized data | Named licensed provider/feeds covering permitted equity/ETF sessions;identity/quote freshness/execution eligibility/corporate-action and rate/outage refusal evidence;explicit connection permission | BLOCKED;no provider contacted or subscription assumed |
| P2 manual routing | B1/C1/D1+explicit financial integration permission;manual-confirmed entry/partial/full durable acknowledgements;all policy limits;no UNKNOWN auto-replay | BLOCKED;native operational writer/routing not implemented |
| P3 reconciliation | Every committed operation,original position,remaining quantity,cash,cost and report source revision accounted for;zero unexplained differences;zero UNKNOWN/unacknowledged work for clean outcome | BLOCKED operationally;offline native proof retained |
| P4 overnight | Accepted open quantity/cost basis and prior-day cash/report continuity through actual permitted shutdown/restart;no forced liquidation/reset | BLOCKED operationally;disposable/DST tests retained |
| P5 Start/Stop | Exact real parent/child/resource ownership,complete writer closure/drain and safe graceful Start/Stop under existing deadlines;Docker/Desktop left alone unless separately authorized Atlas-owned dependency policy | BLOCKED;read bridge source tested,uninstalled |
| P6 failure/recovery | Witnessed operational-format backup/isolated restore and crashes/UNKNOWN/stale-clock/substitution/network refusal;no duplicate effects or falsely clean result | BLOCKED;true-symlink/native custody and actual-format acceptance missing |
| P7 seven-day trial | Seven designated authorized US-exchange session days,counting rule accepted before launch;daily independent accounting review,all attempts/incomplete days/incidents retained;pause on unexplained state | NOTSTARTED;0operational sessions,0of7days |
| P8 extended trial | After initial review,30-60designated authorized PAPER sessions with complete attempt/failure denominator,manual controls,provider budgets,overnight/recovery and incident review | NOTSTARTED;0of30-60sessions |

Seven-session-day counting is a proposed explicit rule,not seven arbitrary calendar days/weekend observations or granted launch authority. Reviewer/operator must confirm before trial. Neither trial automatically activates other strategies or live trading. No readiness percentage supported by current evidence.

## Automated enforcement and limits

scripts/check_paper_release_policy.py statically checks machine/deployment policies and runtime sources without importing app code. Existing CI workflow runs checker and tests. Recognizable order SDK imports (including dynamic imports),order placement/cancel/modify functions/calls,remote order URLs,real-capital/live route/toggle identifiers refuse. PAPER-specific APIs and market-data-only imports/status reads remain allowed. Dormant live code is not permitted merely because a flag defaults false.

Initial scan's three findings were classified: existing LIVE_EXECUTION=False safety declaration,read-only UI status and a negative frontend fixture. No real broker order call matching these rules was found. Defensive prediction file is LF-canonical source-hash pinned and independently fails on change/deletion;that exemption never permits order calls or a true flag. UI remains byte-identical;test fixtures are separate from executable-source scan. No legacy capability was activated or silently rewritten.

This is a regression tripwire,not a code sandbox or proof against obfuscation,aliases/plugins/arbitrary network calls. It cannot replace reviewed release inventory,protected startup or independent acceptance. Development CI is not an operational permission issuer. Future changes to frozen policy/legacy assumptions require explicit review rather than updating baseline hashes blindly.

Validation: final147Pythonpassed0failed0skipped (53new policy/CI/source-guard cases,54operational-contract,37selected policy,3production-lock). Initial142run overlaps;do notsum. Static556runtime-source audit0issues;Ruff2/compile2,PowerShell updater parsing,YAML workflow/policy consistency,diff and preservation checks. No new native/browser/HTTP/provider/service tests needed or claimed;prior311passes1NOTEXECUTED/25JS retained,not rerun. Prior symlink limitation unpromoted.

## Seven phases and preservation

Phase1coreincomplete;Phase2EvidenceEngine/AFIHOLD(0of10accepted);Phase3BLOCKED;Phase4CrossMarketpending;Phase5historicalSaaSdeferred under Windows-local/noVPS;Phase6institutionalpending;Phase7commercialpending. Historical future live-money material remains historical and cannot authorize implementation in this PAPER-first program. No live-only broker certification/KYC/capital/order-routing work is a prerequisite or authorized task for this release;local B1/C1/D1/E1 requirements remain applicable.

Full roadmap updated only through approved checkpoint updater,backup/readback/outsidebytes/prior-managed verified. All21decisions,startup locks,alien frontend and unrelated work preserved. State/queuezeroACTIVE/BLOCKED_WAIT;all previous outcomes retained. No private financial source accessed,published,migrated or reset. No Genesis interaction,services/provisioning/providers/trading activation. Reviewed source/tests/docs only published.

Publication portability check: canonical LF source hash treats Windows CRLF and Linux LF checkouts identically for the retained legacy safety file. Test verifies both,without rewriting originals. Financial/native evidence hashing is unchanged. CI must pass before a reviewed PAPER candidate;repository branch protection was not configured by this milestone.
