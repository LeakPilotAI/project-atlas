# OwnedChild continuation and acceptance boundary - 2026-10-27

## Verdict

BLOCKED. Personal release authority remains the sole operator;no external-reviewer chain is required. PAPER/native activation is not authorized by the new autonomy directive. No approvals/gates were fabricated or promoted.

Branch chatgpt/atlas-rebuild-v1,HEADa8896316841d2724b681a69445d1c0b60f1d7d71 on entry. All five tracked changes and unrelated untracked work were preserved. Reviewed existing venv/startup diagnostic edits in the fixture remain intact alongside the new fixes;no production launcher was changed.

## Four requested failures reproduced first

Command:backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_personal_native_job_containment_offline.py;PYTHONDONTWRITEBYTECODE=1,PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.

Actual pytest result:4failed,2passed,1.24s;pytest exit1. The enclosing first PowerShell inspection also printed source files,so its final shell exit0 was not a test pass.

| Test | Unchanged assertion / actual status |
|---|---|
|test_job_object_creation_is_required|CreateJobObject absent from OwnedChild;FAIL|
|test_job_object_kills_owned_tree_on_close|JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE absent;FAIL|
|test_child_is_created_suspended_before_assignment|CREATE_SUSPENDED absent;FAIL|
|test_containment_failure_is_explicit|NATIVE_JOB_CONTAINMENT_REQUIRED absent;FAIL|

The WindowsJobAPI.create_suspended_child method still deliberately raises NATIVE_CHILD_LAUNCH_BLOCKED_PENDING_V5_INTEGRATION. The injected ContainedChild helper owns Job/process handles only after admission;OwnedChild is the actual fixture Popen owner. No second Popen/Job owner or Windows adapter connection was introduced. Future integration must transfer exact handle ownership,verify image/creation/handshake,retain primary-thread handle,assign before resume and preserve cleanup failures. Current native V5approval is absent. These four actual integration tests cannot be truthfully marked green under the explicit prohibition on activating that integration without approval. None were skipped or weakened.

## Newly demonstrated defects and source repairs

Using fake Popen/handle objects only:

1. Identity refusal,budget expiry or wait failure formerly closed a potentially live child's last process handle and pipes.Three reproducing cases failed. finish now preserves both and attaches the existing OwnedChild owner to the propagated exception for explicit recovery.
2. A wait return without confirmed poll exit could proceed toward successful evidence publication.One reproducer failed. Explicit OWNED_CHILD_STILL_RUNNING now refuses before evidence write.
3. Exited-child stream/handle close failures lost retry context or could republish evidence.Two reproducers failed. A private cleanup method retains exact incomplete resources,attempts all exited-resource closes,tracks successes and exposes retry ownership. A successful publication is cached only after bounded evidence write returns;retry never rewrites acknowledged evidence or closes released resources twice.
4. Constructor rejection now also retains the canonical owner on the original/cleanup exception and uses the same exited-only resource-release helper. Existing fake constructor rejection tests remain green.

This is fixture lifecycle/source hardening,not a financial writer or native launch activation. No financial format/accounting/risk/UI change. No physical child or filesystem-native financial test was executed. Actual native wait/termination/pipe behavior still needs the separately authorized contained test.

## Validation after changes

| Selection | Actual result |
|---|---|
|Initial new retention tests before fixes|4failed,1passed;1.44s;exit1|
|Additional close-failure tests before fixes|2failed,5passed;1.36s;exit1|
|Focused new/constructor/owner tests after first repairs|15passed;2.09s;exit0;later eighth new case included in broad run|
|All test_personal_native_*offline.py except actual-process windows_launcher,plus test_personal_native_v5_authorization_pure.py|115passed,4failed,0skipped,0errors;9.78s;exit1|
|test_personal_paper_runtime.py,test_personal_paper_inception_memory.py,test_personal_current_pins_memory.py,test_quality_dips_personal_dependencies.py;existing native/file-backed exclusion expression|81passed,3deselected,0failed,0skipped;3.22s;exit0|
|New test file Ruff;fixture F/E9 checks;both files compile without execution|PASS|

The last two test selections are disjoint:196passes and4failures in this increment,8new cases. Do not add overlapping focused results. No warnings were emitted by those final selections. Prior285/431evidence remains retained;it is not relabeled as current native evidence.

Broad lifecycle command selected Get-ChildItem tests/test_personal_native_*offline.py excluding test_personal_native_windows_launcher_offline.py,then pytest -q -p no:cacheprovider --basetemp logs/diagnostics/owned-finish-offline-20261027 plus tests/test_personal_native_v5_authorization_pure.py. Plugin autoload and bytecode were disabled. All process/kernel32 ports in that selection were fake/source-only. Actual-process windows_launcher was not run because native execution requires separate authorization. The81case selection used -k 'not native_existing and not native_evidence and not native_mutation and not operational_reader and not enrollment_adapter_wraps and not session_reservation_durable_single_use_restart'. The excluded cases require a different financial/native scope,not altered assertions.

## Integrity and current installation status

The existing V5source manifest now correctly refuses NATIVE_SCOPE_SOURCE_CHANGED after the fixture repair. It was not rewritten to conceal that change. No V5operator approval artifact exists;the proposed fixture root remains absent. Source manifest must be refreshed/reviewed for the complete future contained implementation before execution. Consumed earlier native grants are not reusable.

Only source/tests,ordinary pytest scratch,and continuity documents were written. No13protected directories,journals,financialaccounts,providers,credentialinstall,services,systemsettings,desktopshortcut,Genesis or retained-history host was accessed/activated. No process tree was enumerated/killed. Existing unrelated service state is not newly established. Original alienUI untouched. No actual browser,desktop startup/Stop,reboot,marketdata,Discord,financial inception or pilot ran.

Financial/runtime tests support separate1000simulatedUSD/1000simulatedUSDC,once-only publication,UNKNOWN/refusal,clock/risk and recovery source behavior. Current marketdata remains UNVERIFIED:AlpacaIEX/QDpublication and Hyperliquid current observations require authorized scope/rights/freshness. D:venv still depends on C:base Python;operational D:runtime installation remains unperformed. Actual ownership/resources/custody,once-only native inception,read-only dashboard and real Stop/restart still need acceptance. No long-term stability/profitability claim.

## Exact next action

One consolidated operator decision is needed for the existing V5 contained-launch implementation/OwnedChild binding and bounded synthetic native test after source-inventory refresh. Existing proposed boundary:one exact V5root in docs/PERSONAL_NATIVE_COMPATIBILITY_EXECUTION_PROPOSAL_V5_FINAL.json,600seconds inclusive,4096entries,128MiB,exact-owned self-exiting test children,synthetic records only,no providers/realaccount/Genesis/system changes. Current proposal is stale and NOT authorized;do not execute it or create approval to advance the queue. Confirm the contained native implementation scope and refresh its exact source list before presenting it for execution approval.

Then separately authorize D:runtime/resources/local dependencies,once-only simulated inception,currentdata and boundedpilot through the existing consolidated activation bundle. No new accounting engine or dashboard is needed. No safe operational Start command can be claimed today. Do not run generic financial startup. After actual acceptance,ControlCenter normalStop routes SHUTDOWN_FLATTEN through existing verified writers;freshBID/ASK,ACK,reconciliation,FINAL/drain and exactownedclose required. Missing evidence preserves POSITION_OPEN/UNKNOWN/SHUTDOWN_INCOMPLETE. EmergencyStop and crash never imply a completed liquidation;manualrestart reconciles before a newly authorized session.

PAPERstartup:NO. Production:NO-GO. Live-money orders/withdrawals/transfers remain excluded. No enterprise approval chain is reintroduced.
