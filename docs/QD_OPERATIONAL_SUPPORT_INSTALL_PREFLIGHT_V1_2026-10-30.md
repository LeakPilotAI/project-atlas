# Operational support installation V1: preflight stop

Base commit: c8a43aa17b66ab44cfd91fdceea32ab2e3ebc379. Branch: chatgpt/atlas-rebuild-v1.

**STOPPED BEFORE INSTALLATION.** Exact package and installed application integrity passed read-only verification. Two mandatory preflight requirements did not pass: no reviewed operational support installer exists, and the authorized support manifest does not explicitly declare its installation destination. No support deployment, resource provisioning, selection or application acceptance was attempted.

## Authorization and enforced boundary

The operator authorized P-QD-OPERATIONAL-SUPPORT-INSTALL-AND-CONTROL-CENTER-ACCEPTANCE-V1: one exact support installation, selection-resource provisioning, exact installed application selection and bounded nonfinancial acceptance. Financial commissioning and provider connections remain prohibited.

The directive requires: “If the operational support installation mechanism is missing or unreviewed, STOP.” It also says: “Do not invent a new installer during this authorized operational execution.” These are the reasons this execution stops. This is a technical handoff gap, not a missing enterprise reviewer or another request to approve the already-authorized application release.

The source manifest's historical `installation_authorized: false` field was not treated as overriding the new operator grant. The actual blockers are the absent installation mechanism and explicit-destination requirement.

## Read-only integrity results

| Item | Actual result |
|---|---|
| Support manifest | docs/QD_SELECTOR_LAUNCHER_SUPPORT_MANIFEST_V1_2026-10-30.json; canonical LF SHA-256 **8a227781d422287afc5cc8e2e88c463864df63e5a477aea35a844acb0ff81fed** |
| Retained support ZIP | SHA-256 **09b00f9e554d6bc8e799f99276bcf41efaf9880f88d8a4c1b2984cec505e0fb3**; 37,911 bytes |
| Exact support inventory | Eight source files, 115,534 source bytes, plus support-manifest.json; nine ZIP members; source/archive hashes and sizes match |
| Application release | **2c039af29dfefd1df77e0caa3db3fdf5ed188118** at D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118 |
| Application receipt | Raw SHA-256 **c12ae55c8e31be813c1b3c1b7da87785c89af0945f73efa89621d5d846210915**; retained 44-record publication journal ends with matching verified-installation ACK |
| Native installed application readback | Genuine D:-resident interpreter read-only verifier passed: **10,204 files, 903 directories**, exact release/artifact binding; zero retained verification handles |
| Installed artifact digest | **94ec8b392dd9d0db13e01a8180dd7574baeb468b5e7bd9f3c209af05df048867** |
| Older retained release | fca29cfe7760a28d2569b8b4b91ed1ea99804c3c: **10,182 files, 903 directories** verified; zero handles after close |
| Runtime namespace | Immediate D:\AtlasRuntime children: releases only; support destination and selection root absent |
| Actual desktop references | Existing Project Atlas and Stop Atlas links remain byte-identical and still target workspace observation scripts; neither was executed or changed |
| Read-only preflight duration | **14.250 seconds** |

Machine-specific native identities, process identity, shortcut details and complete verification results remain private in logs/diagnostics/qd-support-install-preflight-v1-20261030/result.json. That diagnostic evidence is not enrollment, financial custody or a support installation receipt.

The old fca release is a retained dependency/application release, **not evidence of an earlier selected native release**. The factual current selection is UNSELECTED: no operational native selection resource exists. Rollback to this baseline would preserve an unselected state; it must not invent a previous selection.

## Exact missing implementation

| Component | Present behavior and boundary |
|---|---|
| scripts/install_verified_release.py | Installs the separately reviewed application archive format only into D:\AtlasRuntime\releases\<40-hex-release>. It does not install support archives into launchers/<64-hex-manifest>. |
| scripts/build_release_candidate.py | Pure archive verification rejects the exact support ZIP with **Required archive companions missing**. That refusal was exercised without installation effects. |
| scripts/installed_nonfinancial_launcher.py | Verifies an already-installed support package at the exact manifest-derived location and launches a bounded nonfinancial runtime. It does not install that package. |
| scripts/release_selection_store.py | Operational construction opens an existing accepted, protected native selection resource. It does not provision one. Its disposable construction is not operational provisioning authority. |
| scripts/native_install_candidate.py | Contains confined fixture installation and reusable copy primitives, not a reviewed support-deployment/provisioning adapter. An ad hoc operational caller would be a new installer. |

The report and launcher derive the proposed support destination as:

`D:\AtlasRuntime\launchers\8a227781d422287afc5cc8e2e88c463864df63e5a477aea35a844acb0ff81fed`

The authorized support manifest explicitly names `D:\AtlasRuntime\selection` but has **no explicit support installation destination field**. A destination implied by executable code or a narrative report does not satisfy this directive's explicit-manifest preflight. No pinned manifest was edited to manufacture compliance.

## Focused validation

Existing test files: tests/test_unselected_release_adapter.py and tests/test_installed_nonfinancial_launcher.py.

Selection expression:

`default_or_untyped or fixture_clock_is_not or module_entry_is_source_only or target_rejects_path_like or launch_default_refuses or missing_runtime_never or fixture_ports_never or installed_support_package_admission`

**18 passed, 0 failed, 0 skipped; 87 deselected; pytest 2.06 seconds, measured test call 2.157 seconds.** Deselected tests were outside this focused refusal check; they were not failed or counted as new acceptance. The previous 308-test source/disposable increment and all prior failures remain preserved rather than unnecessarily repeated.

Tests used one create-new repository diagnostic fixture, logs/diagnostics/qd-support-preflight-refusal-tests-v1-20261030. Python filesystem-write instrumentation reported **163 permitted write events, zero denied/outside-write attempts**. Before result publication: **101 entries, 8,264 logical bytes, 421,960 conservative allocation-upper-bound bytes**, no materialized hardlink groups. Bytecode and pytest caches were disabled; temporary files were confined. This Python audit is test instrumentation, not a Windows security boundary or proof about arbitrary native programs.

These checks verify offline refusal/package-admission behavior, not actual operational support installation or positive installed startup. No source code changed in this increment.

## Operational outcome and cleanup

| Required outcome | Result |
|---|---|
| Support installation / support receipt | NOT ATTEMPTED / no receipt created |
| Operational directories or files created | **0 / 0** |
| Selection resource / selection records | NOT PROVISIONED / **0** |
| Selected application | UNSELECTED; existing installed 2c payload retained |
| Genuine installed Control Center startup | NOT EXECUTED |
| Dashboard acceptance | NOT EXECUTED |
| First Stop / restart / final Stop | NOT EXECUTED; no timing samples claimed |
| Rollback | NOT NEEDED: no selection change |
| Clock | Not acquired after the earlier installation-preflight blocker; no stale acceptance reused |
| Owned resources | Read-only installed verification child exited; both native verifiers closed all handles. No application listener or owned application port was opened. |
| Financial services, accounts, providers, PAPER | No activation, enrollment, publication, access or connection |
| System / unrelated state | No Windows Time, desktop shortcut, automatic-startup, protected-account, retained-journal or Genesis operation |

Private evidence and unrelated working-tree modifications were preserved. No operational resource was adopted, repaired, deleted or overwritten. All 21 decisions, seven phases, B1/C1/D1/E1, PERSONAL_PAPER_ONLY_V1 and strict-profile history remain unchanged. PAPER startup: **NO**. Production: **NO-GO**.

## Minimum next scope

The next necessary decision is narrowly scoped **SOURCE-ONLY support-install adapter and deployment-manifest engineering with offline/disposable tests**. This operational execution expressly prohibits inventing that adapter, so none was implemented here.

The missing adapter should reuse existing reviewed copy/native primitives and explicitly bind:

1. The unchanged 8a2277... support manifest and 09b00f... archive to an exact destination, source hashes, root identity requirements and bounded resource limits.
2. Create-new protected support and selection children, exact native identity/ACL verification, complete namespace and no app-payload overwrite.
3. Durable intent, verified installation receipt and ACK, independent readback, incomplete/interrupted-install refusal and preservation of all existing resources.
4. Tests for missing inputs, wrong hashes, collisions/substitution, interrupted copy, incomplete receipt, selection-root provisioning failure and resource exhaustion.

A separate deployment execution manifest can bind the existing payload and explicit destination without silently changing or repacking the authorized support manifest. If implementation requires payload changes, those changes and new pins must be reviewed explicitly before operational use.

After that source implementation is reviewed and tested, the sole operator can approve its exact installer/deployment pins and the bounded nonfinancial installation/selection/Control Center acceptance scope. The exact application need not be recopied. Current clock, actual selection/resource acceptance and eight-second Stop/restart still must pass during that execution. Current research, executable IEX evidence and financial custody/inception/session acceptance remain separate commissioning requirements; this report grants none of them.
