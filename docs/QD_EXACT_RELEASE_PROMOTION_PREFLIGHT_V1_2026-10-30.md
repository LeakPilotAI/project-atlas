# Exact-release promotion — preflight stop

Base: 00ea7cd0a1b97071635a2cf15c390d3151bb5c61. Branch: chatgpt/atlas-rebuild-v1.
Milestone: P-QD-EXACT-RELEASE-PROMOTION-NONFINANCIAL-ACCEPTANCE-V1.

**BLOCKED BEFORE PROMOTION. The exact installed release passed fresh native integrity verification, but a reviewed operational atomic selector/rollback mechanism is unavailable. No release selection, application launch or promotion occurred.**

The operator authorized promotion of the exact existing release and bounded nonfinancial acceptance, subject to the specified preflight. The same directive explicitly says: **"If the approved promotion mechanism is missing, unverified or requires new implementation, STOP."** It also says not to invent a replacement during this operation. That boundary was enforced. This is a technical implementation gap, not a missing external reviewer or enterprise approval.

## Exact installed artifact reverified

| Evidence | Current result |
|---|---|
| Authorized release | 2c039af29dfefd1df77e0caa3db3fdf5ed188118 |
| Actual installed directory | D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118 |
| Files / directories | 10,204 / 903 |
| Copied payload, unchanged inventory | 260,369,081 bytes |
| Durable receipt SHA-256 | c12ae55c8e31be813c1b3c1b7da87785c89af0945f73efa89621d5d846210915 |
| Installed artifact digest | 94ec8b392dd9d0db13e01a8180dd7574baeb468b5e7bd9f3c209af05df048867 |
| Completion journal | 44 records; final UNSELECTED_CODE_INSTALL_VERIFIED ACK matches actual receipt bytes |
| Actual installed readback | PASS, genuine new D-resident interpreter and installed NativePersonalReleaseIdentity |
| Remaining verification handles | 0; exact retained readback child exited and process handle closed |

The existing installed_readback implementation launched only the exact owned read-only verification child, in isolated/no-bytecode mode. It checked native file identities, hashes, protected owner/SYSTEM ACLs, link/reparse refusal, complete namespace, installed module cohort and process/executable identity. No application, HTTP host or financial service was started.

The old dependency/runtime release fca29cfe7760a28d2569b8b4b91ed1ea99804c3c also passed its original native identity/hash/ACL/namespace inventory: **10,182 files, 903 directories**. Its verification handles closed. Both releases remain intact; neither was recopied, repaired, replaced or deleted.

Native/desktop preflight took **12.750 seconds**. Raw identities and receipts remain private under logs/diagnostics/qd-exact-promotion-preflight-v1-20261030.

## Actual current launch identity

The existing Project Atlas and Stop Atlas desktop shortcut bytes, target/arguments and working directories match the previous acceptance. Their six associated launcher/module hashes also remain unchanged.

The actual Project Atlas shortcut invokes the workspace scripts/windows/Atlas-Observation-Shortcut.ps1 using Windows PowerShell, with D:\Work\Project Atlas as the working directory. Stop Atlas invokes the companion workspace stop script. These are actual current launch references, **not selection references to either immutable installed release**.

Consequently there is no factual previous selected native release SHA to record. The old fca runtime is a verified retained dependency release, not proof of an active-selection marker. The 2c release is installed and unselected. No new selection marker was created merely to manufacture a previous-selection identity.

Read-only D:\AtlasRuntime top-level inventory contains only the releases directory. Searches of the relevant available source, installed manifest and promotion procedures found no reviewed operational selected-release update/restore implementation. Source-plan "selection" is an explicit archive inventory, not application version selection.

## Blocking implementation gaps

1. **Operational selector and rollback are missing/unverified.** scripts/install_verified_release.py deliberately implements an unselected copy only. scripts/native_install_candidate.py explicitly does not select releases. scripts/build_release_candidate.py verifies source/staged archives; its portable consistency checks explicitly exclude release selection, process execution and native installed acceptance. Tests that preserve a synthetic selected.json marker do not implement an operational selector, atomic selection ACK or restoration procedure. The existing promotion procedure itself requires remaining unselected if that mechanism is unavailable/reviewed. No atomic operational promotion or rollback claim can be made.

2. **The existing desktop path is not a selection-aware installed launcher.** Both actual shortcut scripts are workspace files and are absent from the approved installed manifest. They cannot be silently added to the immutable release. Atlas-Observation-Dashboard.psm1 and Atlas-Control-Center.psm1 are present in the package, but the existing observation startup code locates backend\.venv\Scripts\python.exe, which is absent there. The actual verified installed interpreter is python\python.exe. Directly retargeting the shortcut to this release would not establish correct installed origin or solve that dependency-path mismatch.

3. **The current shortcut's provider mode conflicts with this grant.** Atlas-Observation-Shortcut.ps1 passes -BoundedDataOnly. Atlas-Observation-Dashboard.psm1 translates that to --data-only-seconds 30 --operator-data-only-approved, and desktop_observation.py can start its provider collector in that mode. The current grant expressly prohibits provider connections. The default observation entry supports no-provider behavior, but that does not provide a reviewed selection-aware installed Control Center/desktop adapter. The existing shortcut was not executed to test this conflict.

No replacement pointer, bootstrap, launcher, marker, installation file or runtime dependency was invented, installed or modified. The original alien UI, protected startup locks and financial boundaries remain unchanged.

## Acceptance status

| Requested stage | Actual status |
|---|---|
| Exact candidate native identity/receipt/ACK | PASS, freshly reverified |
| Old release and current desktop preservation | PASS |
| Reviewed atomic operational selection | BLOCKED: mechanism unavailable/unverified |
| Previous-selection restoration | NOT VERIFIED; no selection changed, so no rollback was needed or attempted |
| Promotion receipt / newly selected release | NOT CREATED / NONE |
| Installed nonfinancial Control Center startup | NOT EXECUTED after mandatory pre-promotion stop |
| Dashboard/browser rendering | NOT EXECUTED in this milestone |
| Installed eight-second application Stop | NOT EXECUTED; no timing sample claimed |
| Installed application restart | NOT EXECUTED |
| Resource cleanup | Read-only verifier child exited, retained handles closed; no application or host was opened |
| Financial/provider/PAPER activity | NONE |

No new clock capability was acquired after discovering the selector preflight blocker. The previous 228-ms capability remains revoked historical evidence; it was not reused as current authority. Applicable fresh clock checks still must pass before any eventual selection/startup operation. No Windows Time service, configuration, source, synchronization, registry, startup or system clock change occurred.

## Focused offline validation

Four existing suites ran against new write-audited disposable fixtures:

- tests/test_unselected_release_adapter.py
- tests/test_personal_release_module_binding.py
- tests/test_candidate_selected_inventory.py
- tests/test_nonfinancial_resource_host.py

**101 passed, 0 failed, 0 skipped in 6.02 seconds.** Including child startup and evidence collection: **7.437 seconds**. pytest cache was disabled, bytecode disabled and temporary/cache locations confined. Python write audit recorded no outside-write refusal. No operational account, retained journal, service or provider was accessed by the tests.

Before the final regression result artifact, the fixture contained **544 entries**, **23,610 logical bytes**, and a **2,251,834-byte conservative allocation upper bound**. The result artifact is retained. The regression child exited; no listener or application was started.

These tests verify existing copy refusal, mixed-module origin refusal, archive-inventory/staging preservation and nonfinancial fixture boundaries. They are **not** operational atomic-promotion, rollback, installed Control Center, dashboard, Stop or restart acceptance. The previous 223-test evidence and genuine V2 code-copy acceptance remain valid and preserved; no second full copy was performed. No public implementation changed, so broad suites and lint were not repeated.

Private regression evidence: logs/diagnostics/qd-promotion-offline-v1-222ec04e1d30.

## Required next scope

Authorize **source-only implementation and offline/disposable validation of the minimal selection/rollback and provider-disabled installed desktop/Control Center launcher binding**, preserving this exact immutable release and leaving desktop selection unchanged during engineering.

That work must bind actual receipt/native identity, verify exact installed interpreter/module origins, retain the real prior launch reference for restoration, refuse ambiguous/partial selection and keep provider/financial startup disabled. Review the concrete implementation and its preservation/rollback tests before attempting this promotion. The present directive forbids building that mechanism inside the promotion operation; no such implementation was performed.

Existing promotion permission was not exercised or converted into permission for new selector implementation. The single V2 copy grant remains consumed; recopying the release is unnecessary and unauthorized. No external reviewer chain is introduced under PERSONAL_PAPER_ONLY_V1.

Current accepted research/executable IEX, native financial resource/writer/custody/session acceptance, financial activation/inception and financial Stop/dashboard/restart remain distinct later commissioning gates. None is accepted by native code readback or these offline tests.

All historical evidence, original failures, unrelated modified research test/untracked files, seven phases, B1/C1/D1/E1 and all 21 historical decisions are preserved. No protected financial state or Genesis resource was accessed, no process outside the exact owned verifier/test children was stopped, and no automatic startup was enabled. No files were deleted and no space was reclaimed.

**Final selection: unchanged workspace desktop observation references; 2c release remains unselected. Promotion: BLOCKED. PAPER startup: NO. Production: NO-GO.**
