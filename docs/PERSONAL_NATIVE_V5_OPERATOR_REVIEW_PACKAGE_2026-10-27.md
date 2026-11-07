# V5 native-containment authorization review - October 27, 2026

**REVIEW PACKAGE ONLY. NOT AUTHORIZED. NOT EXECUTION-READY.**

## Exact decision requested

Approve the narrow **source-only V5 containment binding** under the existing Windows Job Object design, and review the bounded synthetic-test scope below. This permits completing the suspended-launch adapter/OwnedChild ownership connection and fake-API regressions;it does not by itself permit executing native children. No operational account,financial writer,provider or Windows service is included.

Suggested operator decision: **“Approve source-only V5 containment integration and the proposed synthetic-test boundaries. Withhold native execution until I review and approve the completed-source execution manifest.”**

Actual native execution remains a subsequent explicit decision under `P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V5`. The present source is known incomplete;approving this baseline digest cannot make it ready. The completed implementation will change hashes and must be presented with its exact refreshed manifest before that execution decision. Ordinary permitted offline work needs no repeated approval. Sole operator is the release authority;no external reviewer or enterprise chain.

## Refreshed exact source snapshot

- Source base commit: `dd077975ded4950f82b721503e26f57a4c5de680`;branch `chatgpt/atlas-rebuild-v1`.
- Manifest: `docs/PERSONAL_NATIVE_V5_SOURCE_MANIFEST_REVIEW_2026-10-27.json`.
- Manifest raw SHA-256: `975bd8bddfb2b77d765b05d230fe70ac176b8b101ab02dc63c3c36276ed43579`.
- 47 exact declared source/test/policy paths;includes the three native Job/API/launch modules and their admission,cleanup,identity and manifest regressions. Exact per-file hashes are in JSON.
- This47-file Atlas source set is not an authenticated interpreter/stdlib/site-package inventory. Exact runtime image and dependency evidence remain preflight requirements;no binary authenticity is inferred from source hashes.
- Two views:LF-canonical SHA-256 for source portability and raw SHA-256 for this local working snapshot. This normalization applies only to source text,never financial evidence. Neither view is an issuer,approval or anti-rollback authority.
- The four previously pending V5 preparation edits are preserved and included in this review:scope constants,budget root accounting,approval-gated runner and child handshake/import sequencing. No unrelated source files are adopted. The snapshot is explicitly a working-tree cut,not a claim that the old base commit already contains those edits.
- Old V5_FINAL manifest retained untouched;its path/hash is recorded in the new JSON. Historical285/431/196evidence and four red integration findings remain preserved.
- Runner now reads this review manifest and requires `execution_ready is True` after source verification,before creating any native root. The current value is **False**. Even a test-only stub of approval cannot cross that refusal. No approval artifact was created.

## Why execution cannot be approved as ready yet

Actual OwnedChild remains a retained-Popen fixture owner;the WindowsJobAPI suspended-creation method still refuses. Four unchanged acceptance assertions are red:Jobcreation,kill-on-close,suspended assignment-before-resume,and containment-failure integration. The new manifest explicitly names each test. Matching hashes is not evidence that these features are integrated.

Required source acceptance before a final execution manifest:one canonical owner per handle;configured Job before creation;exact executable/arguments withoutNUL;retained process and primary-thread handles;image/creation identity validation;assignment confirmed before resume;existingREADY/GOhandshake;child/grandchild containment;no inherited escape handles;retryable cleanup and truthful failures. Existing native API adapter must remain disconnected until this integration scope is authorized. No blanket authority,fixture approval or V4grant substitution.

## Proposed bounded synthetic test

| Boundary | Exact proposal |
|---|---|
| New root | `D:\Work\Project Atlas\logs\diagnostics\continuation-fixture-20f5937ddc2c44658cfd719193eb7591` |
| Roots allowed |Exactly that one NEW root and descendants;must be absent before creation;no adoption/recreation/repair of an existing root|
| Duration |600seconds inclusive of setup,testing,shutdown and verification;admission closes420s;suite self-exit450s;parentwait480s;phasechild25s|
| Storage |4096filesystementries,134217728chargedbytes(128MiB),including budget/control/evidence overhead;prospective reservations and existing native limits;fail closed on exhaustion|
| Native mutations |Synthetic FS2/FS3 source/projection/report/current-custody fixtures only;restricted owner/SYSTEMACLs on newly created fixture children;no changes to ancestors or existing resources|
| Processes |One existing development-Python controller;one suite child;ten sequential crash-phase children;at most two test children concurrently,eleven child creations total;exact owned handles/images/creation times only|
| IPC |Owned stdin/stdout/stderr pipes and Jobhandles;no HTTP listener,port,Windows service,task or global process search/kill|
| Native cases |Existing17cases:2separate-account once-only publication/codec/readback;10crash phases acrossQD/perp;3conflicting native cuts;1missingauthority;1actualdevelopment-layout observation|
| Exclusions |Real13directories,operational accounts,retainedjournals,providers,credentials,Genesis,production,systemsettings,live orders/transfers/withdrawals,operationalfinancialstartup|
| Cleanup |Gracefully reap exact owned self-exiting children;only failure/timeout cleanup may use the approved exact-owned containment contract;release handles,pipes,locks;retain root and evidence;no recursive deletion or unrelated process action|

Synthetic capital1000USD and1000USDC remains segregated. No real account inception. Control-state SQLite is test coordination,not independent financial/custody authority. These17cases do not claim a native concurrency,symlink,power-loss,fullUIor operational-trading acceptance that they do not execute. True-symlink capability remains separately NOT_EXECUTED.

The existing development venv resolves through an existing C:-base Python. Proposed temporary use is solely a synthetic-test tool,not C:Atlas deployment or D:operational readiness. No interpreter is installed/copied here. Operator must include that existing-tool use in the eventual test scope or require an approved D:runtime first. Exact local resolved executable and all11childargv are in ignored `logs/diagnostics/PERSONAL_NATIVE_V5_REVIEW_COMMANDS_PRIVATE_2026-10-27.json`;review locally,do not publish. Actual native image/creation observation is still pending.

### Proposed commands - DO NOT RUN NOW

Inert review command,already permitted:

`& 'D:\Work\Project Atlas\backend\.venv\Scripts\python.exe' -B scripts/observation_runtime/personal_native_compatibility_run.py --plan`

Future controller,blocked until completed source/approval/preconditions:

`& 'D:\Work\Project Atlas\backend\.venv\Scripts\python.exe' -B scripts/observation_runtime/personal_native_compatibility_run.py --execute --approved-scope P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V5`

Only the retained exact base interpreter may run the fixed `tests/personal_native_compatibility_child.py --suite` and the ten enumerated `--case <root>/native/case-death-<lane>-<phase> --lane <lane> --phase <phase>` invocations. Lanes:QUALITY_DIPS/HYPERLIQUID;phases:before_reservation,pending,source,commit,ack. Private JSON enumerates every argv;no arbitrary executable,script or case path is authorized.

Approval file `docs/PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V5.json` remains absent. Do not create or modify it until the corresponding actual operator decision exists. It does not authorize financial services and cannot override missing readiness,source drift,identity failures or resource bounds.

## Acceptance and evidence required from a future authorized run

All17native financial cases must complete with actual pass/fail/skipped/error counts;unavailable capabilities are NOT_EXECUTED,neverPASS. Retain original failures,per-case publication/reservation/ACK outcomes,replay/arithmetic/report parity,USD/USDCseparation,native creation-handle IDs/ACL checks and before/after synthetic source hashes. Record actual process/image/creation/Jobmembership,exit/cleanup outcome,peak entries/chargedbytes and elapsedtime. Verify no surviving test-owned child/lock;no port is opened. Unverifiable ownership or incomplete shutdown remains explicitly unresolved. Do not delete/recreate the root to rerun a partial session. Financialstartup remainsNO after successful tests.

## Validation performed for this review

71passed,0failed,0skipped,0errors;2.96seconds;pytestexit0. Selection:test_personal_v5_manifest_review_pure,test_personal_native_v5_authorization_pure,test_personal_native_entry_pure,test_personal_native_scope_pure,test_native_fixture_budget_pure.8newmanifest cases;33earlier overlappingpasses not added. Existing venv;bytecode/pluginautoload/cacheprovider disabled;ordinary source scratch under logs/diagnostics/v5-manifest-policy-offline-20261027. No NativeCase or child suite was collected/executed. The test approval stub exists only in monkeypatched memory;no real approval file/root was created. Source/static F/E9 checks and newtest Ruff pass. No financial or provider regression suite unnecessarily repeated.

## Independent next work and boundaries

Can proceed without activation:source/hash drift review,offline API/cleanup/argument/receipt/risk tests and demonstrated nonactivating bug fixes;review packaging/D:runtime requirements and exact installation checklist. Current policy and existing default refusals remain intact. Native launch/OwnedChild connection is the explicit outstanding source boundary,not an external-reviewer vacancy.

After that source scope is approved:finish binding using existing owner/helper,run fake-API acceptance,refresh this manifest to completed code and present the exact newdigest. Only then request/consume the single bounded native execution decision. After successful native acceptance,operational installation/enrollment,once-only account inception,provider access and financial PAPERpilot still require separate explicit authorization through the existing activation bundle. No Windows reboot/service/desktop trial or financial startup is included in this package.

PAPERstartup:NO. Production:NO-GO. OriginalUI,separateaccounts,Genesis isolation,sevenphases and21historicaldecisions unchanged.
