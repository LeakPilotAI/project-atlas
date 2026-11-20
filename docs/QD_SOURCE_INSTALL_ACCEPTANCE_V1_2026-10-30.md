# QD source-package and installation acceptance — October 30, 2026

## Disposition

Resumed the exact interrupted working tree at `b0b0aded017bceed4770fdd888f6baec24a465a1`, following base `95cb575e7a941a8aa23d34a289dfd1c7bd5b5d57`. **Source packaging and disposable staging verified; new native installation and installed Stop/dashboard/restart NOT EXECUTED.** No active installation, financial resource, credential, provider, Windows configuration or frontend was changed. Unrelated modified and untracked work is excluded and preserved.

The completed historical SEC earnings/exhibit valuation and IEX reference binding remain unchanged. An IEX research reference is not an executable fill, and a historical valuation is not a current accepted ranking publication.

## Demonstrated defects and correction

Six initially failing archive tests reproduced acceptance of a correctly rehashed archive with Windows-incompatible names: case aliases, a reserved device name, trailing dot, trailing space, an invalid character and a file/directory collision. `source_path` and `windows_namespace` now refuse these before archive content validation. No reserved Windows path was created during the reproductions. Original failures are retained privately in `logs/diagnostics/qd-candidate-namespace-repro-v1.txt`.

`scripts/build_release_candidate.py` now additionally supports **explicit selected-source packaging**:

- `ATLAS_SOURCE_SELECTION_V1` binds the exact source commit and a separately supplied canonical file-list SHA-256; sorted, unique rows contain path, size and SHA-256.
- Every selected input must be tracked and unchanged against that commit. Unrelated edits and untracked/private evidence are neither packaged nor committed. This does not waive selected-source cleanliness.
- Bounded manifest, file and total sizes; source identity checked before reads; frozen caller-owned rows; commit rechecked after collection; only a new destination is created. Existing conflicting destinations refuse.
- The resulting archive is verified before return. A source archive remains `source_authenticated:false`, `installation_verified:false`, `activation_approved:false`. Hash consistency alone does not grant trust or release approval.
- Read-only `verify_staged_candidate` checks exact staged files, directories and bytes against the pinned archive, refuses links, unexpected or incomplete trees, and performs no repair, selection, ACL change or runtime launch.

The original broad source-review builder remains compatible. Its ability to include untracked support files makes it unsuitable for implicitly selecting this operational release. Use the explicit reviewed inventory for that purpose. `requirements-observed.txt` describes the packaging environment; it is not a dependency lock or proof of native dependency integrity.

Portable source checks do not establish Windows handle-bound ACL/namespace custody, exclude same-user/admin mutation, or constitute native installed acceptance. A verified source manifest is explicitly tested to refuse substitution for the native installation receipt before native access.

## Genuine observations and disposable validation

| Check | Result | Evidence and limits |
|---|---|---|
| Existing installation, read-only native audit | PASS | 10,182 files, 903 directories, 9,566 Python/dependency files; native identities, owner/SYSTEM ACLs and hashes verified; 142.583 seconds within 180-second bound |
| Existing installation handle closure | PASS | Retained files/directories both zero after close; no native child launched |
| Workspace presented as accepted image | REFUSED as required | `PERSONAL_RELEASE_NOT_EXECUTING_ACCEPTED_IMAGE` |
| Explicit source archive | PASS, consistency only | 637 unchanged reviewed source files; source commit `b0b0aded017bceed4770fdd888f6baec24a465a1` |
| Complete disposable source stage | PASS | 639 files including two companions; 7,862,988 bytes; native identity/ACL acceptance explicitly false |
| Interrupted second copy | REFUSED as required | Interrupted after three copied files; incomplete tree retained without repair; previous complete stage and synthetic selected-version marker unchanged |
| Source preservation | PASS | Original 637 source hashes unchanged before/after |

Archive SHA-256: `620c2d8659c2d033c5afa2c070caebeeb5ae1d40f84c675f0cf92929c851b85b`.

The one source-staging fixture was confined to `D:\Work\Project Atlas\logs\diagnostics\qd-source-install-fixture-v1-864619254d554d64afe5e5651ae3c653`. Its programmed limits were 180 seconds, 4,096 filesystem entries and 64 MiB. Observed: **67.891 seconds, 674 entries, 11,994,450 bytes**. Complete and interrupted artifacts were retained; no deletion or operational rollback occurred. Native children, financial actions and provider actions: **zero**. The synthetic selection marker tests preservation, not the real desktop's release-selection mechanism.

The existing installed release remains `fca29cfe7760a28d2569b8b4b91ed1ea99804c3c`, artifact digest `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`. Its 142.583-second full inventory audit is **not a Stop measurement**, and no cause for that audit duration was established. Exact private native identities and audit results remain outside Git in `logs/diagnostics/qd-current-installation-readonly-v1.json`; staging results are in `qd-disposable-source-install-acceptance-v1.json` in the same directory.

## Exact test evidence

Final relevant combined run: **248 passed, 0 failed, 0 skipped**, 26.48 seconds, one existing Starlette/httpx deprecation warning. It covers selected inventory/Windows namespace, candidate verifier/source identity/CLI/packaging, native release/module identity, installation technical checks, commissioning runner, read composition, publication restart, current financial memory and Windows clock. Command:

```text
<D-resident-python> -B -m pytest -q -p no:cacheprovider -p pytest_asyncio.plugin --basetemp <new-D-diagnostic-root>
  tests/test_candidate_selected_inventory.py tests/test_candidate_windows_namespace.py
  tests/test_candidate_verifier.py tests/test_candidate_source_identity.py
  tests/test_candidate_cli.py tests/test_offline_candidate_packaging.py
  tests/test_personal_release_identity.py tests/test_personal_release_module_binding.py
  tests/test_personal_installation_technical.py tests/test_personal_commissioning_runner.py
  tests/test_personal_paper_read_composition.py tests/test_personal_publication_restart_memory.py
  tests/test_personal_runtime_current_memory.py tests/test_personal_windows_clock.py
```

The subsequently added, disjoint source-manifest/native-receipt substitution test passed **1/1**, 2.58 seconds. **Total: 249 distinct passing cases, 0 final failures, 0 skips; 28 new cases.** The intermediate 77-pass run overlaps and is not added. Prior 325/406-test evidence is preserved, not counted as freshly rerun. Six original reproduced failures are preserved, not erased by the final green run.

Ruff passed the changed builder and both new test files. Static PAPER policy audit: **639 source files, zero issues**; no operational acceptance/startup permission inferred. Python TestClient coverage is not a real browser or installed Control Center test. No new browser host was started.

## Non-destructive native installation acceptance sequence

1. Freeze the committed, reviewed runtime selection and its file-list/archive pins. Separately freeze the exact D-resident Python and dependency inventory, provenance/signature and hashes. Never include the whole dirty worktree or use the observed-package companion as a trusted lock.
2. Acquire fresh actual `LocalWindowsClock` evidence in the accepted runtime. Verify the actual Windows operator, existing release-parent identity, no reparse/substitution, a new absent release child and the exact approved installation scope before creation. Proposed destination is `D:\AtlasRuntime\releases\<approved-source-commit>`; resolve that full SHA and all source pins in the execution scope. Preserve the current release unchanged.
3. Reuse the established native creation-handle/owner-SYSTEM installer primitives and D-resident interpreter layout. Create only the approved new child and descendants; capture original creation-handle identities, protected ACLs and exact hashes. Bound installation to the previously reviewed 600 seconds, 40,000 entries and 1 GiB unless a separately approved scope is stricter. Do not rerun private one-shot installers tied to old release plans or receipts.
4. Any partial copy, mismatch or clock/resource failure stops with evidence retained. Do not delete/recreate, adopt, repair or select a partial release. Before selection, verify complete native inventory, D-only interpreter/dependencies, module origins and default refusal without commissioning evidence. Rollback means retaining the old immutable release and withholding selection of the new one; it never resets financial custody or replays uncertain effects.
5. Run explicitly scoped installed acceptance with synthetic account resources first: authority, financial Stop/reconciliation/report/ACK, writer drain, exact owned exit and independent post-exit readback **within the unchanged eight seconds**. Test missing authority, partial/UNKNOWN publication, restart reconciliation, read-only dashboard/connection states and original Control Center normal Stop. Actual browser and installed process evidence must be recorded as such. Workspace TestClient or the old disposable Stop timings cannot substitute.
6. Only after actual installed acceptance, current native research/publication custody, regular-session executable IEX and every remaining financial gate pass may the already approved once-only $1,000 QD inception and **ONE total 60-second** supervised PAPER pilot proceed. Check prior inception/UNKNOWN before any attempt. No forced trades, Hyperliquid inception, V5 containment, live-money execution or automatic startup.

This task authorizes preparation and disposable tests, not replacement of the active installation. Any new protected release creation/selection or installed native child test outside the existing conditional commissioning scope requires the operator's exact execution scope first. The actual financial grant is not expanded or reissued here. The sole operator remains personal release authority; no external reviewer chain is introduced.

## Remaining gates and next executable work

The genuine clock binding accepted **915 ms** at `2026-10-30T01:46:13Z` (October 29, 20:46:13 Central), expiring four minutes later. It is now historical evidence. See `QD_CLOCK_INSTALL_DIAGNOSTICS_V1_2026-10-29.md` for 902/908/915 ms attribution and the unreconstructable old 2,551 ms refusal. No Windows Time source/configuration/service/clock change or resync was made. The 1,000 ms threshold is unchanged.

Remaining technical conditions: fresh runtime clock; exact current accepted native research publication/custody; fresh entitled executable IEX during an eligible session; reviewed new native installation and dependency/resource binding; installed eight-second Stop, real dashboard/Control Center and restart acceptance; actual financial activation/inception/readback. Historical valuations and old quotes cannot satisfy current-data admission. No new provider request or current ranking acceptance was claimed this increment.

**Next milestone:** bind an exact new-release installation/installed-synthetic-acceptance execution scope to the reviewed manifest and actual D-resident dependency pins; retain refusal until its required authority and resources are available. Source-package validation is complete and should not be repeated unnecessarily. Do not manufacture a new financial test or bypass protected-storage authorization to continue.

All seven phases, 21 historical decisions, personal policy, original alien UI, separate USD/USDC scopes, protected accounts, historical journals and Genesis isolation remain unchanged. No activation or account inception occurred. Existing conditional pilot authorization remains unused. **SOURCE PACKAGE VERIFIED; NEW INSTALLATION NOT COMPLETE; PAPER READY: NO; PILOT COMPLETE: NO. Production: NO-GO.**
