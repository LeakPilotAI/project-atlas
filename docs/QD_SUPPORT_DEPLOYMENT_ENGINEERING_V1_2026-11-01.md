# Support deployment engineering V1 — validation checkpoint

Base commit fdfb9a7fd9c63f067f37e5fdd39784dac5d09b1e, branch chatgpt/atlas-rebuild-v1.
Resumes the interrupted October 31 implementation without resetting or replacing it.

**Source components implemented; operational installation NOT EXECUTED. Complete two-cycle installed PowerShell acceptance is NOT PASSED.** The second Open still refuses readiness in the previously deployed disposable bundle. A new bundle adds precise failed-predicate reporting and stronger typed checks, but its genuine native redeployment test was rejected by automatic approval review. This is a recovery checkpoint, not a claim of complete operational readiness.

## Implemented components

- scripts/support_deployment.py: versioned exact deployment admission, native create-new protected support/selection resources, durable intent/receipt/ACK, independent copied-interpreter readback, source hashes, namespace/ACL/native identity/link checks, bounded capacity and deadline, partial-state preservation/refusal. Installation never selects a release.
- scripts/build_support_deployment.py: explicit nine-source package, excluding unrelated/untracked/private files. The old eight-source package remains unchanged historical evidence. The frozen application payload is unchanged.
- Existing installed_nonfinancial_launcher.py: new versioned support package admission, accepted deployment/receipt/selection-root binding, retained immutable support-file lease through owned process drain, separate confined DISPOSABLE launch path. Operational construction still requires real accepted dependencies and genuine LocalWindowsClock. No workspace fallback for runtime application imports.
- Existing release_selection_store.py: preserves the explicit fixed disposable namespace when loaded from a deployed fixture. Operational root and authority checks remain unchanged.
- Existing Atlas-Installed-Nonfinancial.psm1: V2 desktop binding includes deployment and receipt pins; separate explicit disposable mode; actual retained controller startup, readiness, Close and restart guard. New diagnostics name the failed readiness predicates without suppressing refusal. Provider/trading/autostart values must be actual booleans.
- Exact installation/selection/UNSELECTED-baseline rollback command interface reuses ReleaseSelector and NativeSelectionStore. No second selector, accounting engine, financial journal, dashboard or issuer was created.

## Exact source package

| Artifact | Identity |
|---|---|
| Deployment manifest | docs/QD_SUPPORT_DEPLOYMENT_MANIFEST_V1_2026-11-01.json |
| Canonical deployment SHA-256 | **260438e7ca62713ce5911cf0f43c7be0ef01115dc22d4f9c3fb014cc2175bc8f** |
| Support manifest V2 SHA-256 | **68962f680272331549dd29c65cb4031da873752ef5d289d2800380e22b97a555** |
| ZIP SHA-256 | **ffb92b9f6b62c9ff721c372efd0ea5c2aa04bf33af99a296d47373de4c64ef36** |
| Inventory | Nine source files, **156,313 source bytes**, plus support-manifest.json; ten ZIP entries, **48,793 ZIP bytes** |
| Bound application | **2c039af29dfefd1df77e0caa3db3fdf5ed188118** |
| Application receipt SHA-256 | c12ae55c8e31be813c1b3c1b7da87785c89af0945f73efa89621d5d846210915 |
| Application artifact digest | 94ec8b392dd9d0db13e01a8180dd7574baeb468b5e7bd9f3c209af05df048867 |

The private archive is logs/diagnostics/qd-support-deployment-reviewed-source-20261101/support-source.zip. Manifest canonical encoding is the existing sorted, compact UTF-8 JSON encoding; committed manifest bytes equal that encoding. All source hashes use canonical LF. Compile and exact ZIP inventory/hash validation passed. Ruff --no-cache passed. This package has not been installed or selected.

## Native and lifecycle evidence recovered

Two genuine disposable application copies and support installations completed before interruption. Each application copy verified **10,204 files, 903 directories, 260,369,081 bytes**, using the existing native copier and retained source/dependency receipts. New resources were confined repository fixtures; no D:\AtlasRuntime write occurred.

The revised fixture at logs/diagnostics/qd-selector-v1-native-support-51efac897fc6 recorded native application copy 77.406 seconds and support installation/readback 0.406 seconds. A separate process using that copied D:-resident Python imported the deployed support module and verified native support identities, ACLs, receipt and hashes; zero readback handles remained.

The first full lifecycle exceeded eight seconds. It rehashed the entire disposable application during Stop, unlike the real immutable reader. The correction retains actual no-write/no-delete native read handles and performs namespace verification during Stop. The threshold was not changed. Later **first-cycle** results:

| Path | Timing and outcome |
|---|---|
| Direct installed Python controller | Internal Stop 2.125 s; observed 2.141 s; exit 0, no stderr |
| Windows PowerShell identity diagnostic | Controller internal Stop 1.719 s; owned process exited, no stderr |
| Actual installed PowerShell adapter, first cycle | 1.5661076 s; externally observed 1.578 s |
| Actual adapter, later first cycle | 2.1295174 s; externally observed 2.156 s |
| Actual adapter, later first cycle | 1.8664481 s; externally observed 1.890 s |

**Each two-cycle adapter run still failed on its second Open with OWNED_INSTALLED_DESKTOP_READINESS_REFUSED.** First-cycle success is not restart acceptance. Root cause is not yet established. The direct single-cycle diagnostic confirmed all measured ownership/readiness fields matched. Debugger frame probes did not expose the relevant function-local values reliably; their null/automatic-only records are retained and are not evidence of missing runtime identities.

The latest source reports failed readiness keys and retains all checks; this does not itself prove the restart defect repaired. Its package needs genuine disposable deployment and lifecycle validation before operational use.

The first-cycle full native test performed six original page GETs, financial UNAVAILABLE/cash-null/positions-null/startup-false checks and POST 403 before its later restart failure. Overall that test remains FAILED; this is not complete dashboard, interactive-window or real-browser acceptance. The actual PowerShell Open/Close adapter was exercised, not a newly integrated interactive legacy Control Center window or modified desktop shortcut.

## Exact test results

| Execution | Result | Meaning |
|---|---|---|
| Interrupted initial source run | 203 passed, 1 failed, 1 warning | Support path-mapping compatibility fixture corrected; preserved |
| First native/source combined run | 217 passed, 1 failed, 169.22 s | First Stop exceeded eight seconds; preserved |
| Revised native/source combined run | 224 passed, 1 failed, 169.00 s | Native/readback/refusal cases passed; two-cycle PS readiness failed |
| Resume restricted source run | 184 passed, 25 failed, 1 warning, 22.29 s | Windows error 5 for fixture hardlinks and 10013 for localhost; no assertion weakened |
| Latest normal-permission source run | **209 passed, 0 failed, 0 skipped, 13.30 s** | Four source suites only; no native installation copy |

The latest 209 contain **50 new support-deployment cases and 159 existing relevant cases**. They cover exact manifests, missing/corrupt/duplicate/extra ZIP entries, bad destinations, source pins, typed/default authority refusal, fixture/operational separation, installed-only admission and existing selection/rollback/lifecycle safety. Prior native coverage includes actual protected ACLs, native IDs, receipt/ACK/readback, partial-install/retry refusal, wrong parent, immutable support leases, missing ACK, hardlinks, corrupted receipt, unknown namespace, missing Python and existing eight native selector cases. Do not add overlapping runs to invent a distinct-test total.

An initial resume wrapper had a pytest hook argument-name error before collection. It executed no tests; the corrected wrapper produced the results above. All earlier 308-test source/native/HTTP evidence and historical partial acceptances remain preserved.

Latest source fixture: logs/diagnostics/qd-support-source-regressions-20261101-a88d4a8f. Test-call elapsed 13.422 seconds; Python write instrumentation: **2,616 permitted events, zero denied/outside attempts**. Bytecode and pytest caches disabled, TEMP/cache locations confined; PowerShell module-analysis cache is explicitly confined in the current native test. This is Python-level instrumentation, not a claim of whole-system Windows filesystem auditing. Earlier native process cache effects were not exhaustively audited; no retrospective full-scope PASS is asserted.

The revised native fixture's recorded size was **13,363 entries, 264,702,327 logical bytes, 319,437,175 conservative allocation-upper-bound bytes**, within its proposed 600-second/40,000-entry/512-MiB fixture bound. The support installer separately enforces 600 seconds/8,192 new entries/64 MiB with conservative allocation allowance. Synthetic full-runtime copies are larger than the support-only deployment and have distinct fixture limits.

## Second dependency audit

| Dependency | Final status | Next proof/action |
|---|---|---|
| Explicit source inventory/destination/dependencies | Implemented; pure validation passes | Review exact new pins |
| Native support installer and create-new selection resource | Implemented; prior genuine disposable install/readback passes | Rerun current exact bundle after guard change |
| Durable intent/receipt/ACK/partial refusal | Implemented; prior native cases pass | Include in next combined run |
| Atomic selection and baseline rollback | Existing implementation and native cases retained | Complete combined lifecycle through final rollback |
| Installed-only module/interpreter/receipt binding | Source and prior first-cycle native evidence | Current complete package positive acceptance |
| Provider/financial isolation | Audit guard, typed false flags, unavailable-state HTTP assertions | Reconfirm across restart; no financial acceptance implied |
| Original dashboard | Original source preserved; six-page HTTP assertions reached | Complete lifecycle; no new real-browser/interactive-form acceptance claimed |
| Eight-second Stop | Corrected path passes multiple first cycles | Both cycles must pass unchanged bound |
| Restart in same PowerShell process | **UNRESOLVED readiness refusal** | Named failure-key diagnostics under current deployed fixture |
| Owned cleanup | Known diagnostic controllers exited; narrow Windows queries found **zero remaining copied Python images** in both prior native fixtures | Verify each new run's exact children/ports/handles |
| Actual operational support/selection | **NOT INSTALLED / NOT PROVISIONED** | Separate authorization after current native acceptance passes |
| Genuine operational clock | Not acquired/reused in this source milestone | Fresh <=1000 ms / <=120 s at future operational invocation |
| Financial enrollment/current research/IEX/PAPER | Not accepted or activated | Separate commissioning scope unchanged |

No extra runtime module is currently known missing. This audit is not independent operational acceptance and does not close the restart engineering issue. The sole operator remains the release authority; no external committee or reviewer chain is introduced.

## Automatic-review boundary and next action

Two attempts to run a fresh current-bundle native fixture were rejected before process creation. Automatic review interpreted the old native-copy authorization as one-time and required fresh approval, despite the current milestone's disposable-testing language. The clarification and exact limits are recorded in docs/QD_SUPPORT_DEPLOYMENT_DISPOSABLE_VALIDATION_SCOPE_2026-11-01.md. No rejected copy was rerouted or executed; the proposed final fixture remains absent.

Existing-fixture process-only diagnostics and source-only regressions were separately permitted and completed. This checkpoint stops at that execution boundary. The immediate next decision is **one fresh bounded disposable native-copy/lifecycle validation**, not operational support deployment. See the consolidated proposal for exact roots, limits, exclusions and the later conditional operational procedure.

All unrelated changes/private evidence, original UI, protected accounts, retained journals, all 21 decisions, seven phases and B1/C1/D1/E1 are preserved. No operational support install/selection/rollback, shortcut edit, Windows Time change, provider connection, financial service, account inception, PAPER or Genesis operation occurred. **PAPER startup NO. Production NO-GO.**
