# Project Atlas — one-home storage policy

**User-selected home:** `D:\Work\Project Atlas` on D:. This is the only approved location for **new** Atlas-created project files, downloaded/build artifacts, diagnostics, temporary browser profiles, local caches, dashboards, configuration, and future data stores. No VPS and no automatic startup.

## Immediate rule (effective November 12, 2026)

- All new Atlas-owned temporary files and supported Python/pip/Ruff caches must use subdirectories of `D:\Work\Project Atlas\logs`, not the Windows user Temp directory on C:.
- The desktop **Project Atlas** observation-only shortcut invokes `scripts/windows/Atlas-Use-Project-Storage.ps1` before launching Python. The helper validates the one exact home and rejects reparse points and foreign paths. This is a **per-process** environment change; it does not modify Windows global TEMP or other applications.
- Other/manual Atlas terminal or test entrypoints must dot-source the same helper or explicitly set `TEMP`, `TMP`, `TMPDIR`, `PIP_CACHE_DIR`, `RUFF_CACHE_DIR`, and `XDG_CACHE_HOME` under the chosen home. Do not create another `D:\Atlas*` root or new `C:\*` Atlas profile.
- Existing system Python, installed Windows programs, user application data, shared pip caches, OS-managed Temp, and other non-Atlas applications are **not** Atlas-owned and must not be deleted or moved.

## Protected historical layout — not safe to move in File Explorer

The previously created directories `D:\AtlasRuntime`, `D:\AtlasCustody`, and `D:\AtlasPaper` remain **legacy, original native-identity-bound exceptions**, not approval to create additional outside folders. As of this audit the original 12 native custody/PAPER financial namespaces are empty, while `D:\AtlasRuntime` holds immutable releases and an append-only selector chain. Hundreds of tracked references bind exact paths, file IDs, original release receipts, and native directory handles. Any rename, junction, symlink, or physical move would refuse installed-source integrity and might destroy the chain needed for Stop and future financial reconciliation.

`D:\Work\Atlas-Shutdown-Backups` is a historical standalone backup. Retain it until an independently verified replacement/restore exists; moving the only good backup inside the working repository would reduce recovery isolation. `D:\Captures` is not an Atlas project folder: do not touch it.

## Safe single-home migration required for physical consolidation

1. Quiesce Atlas; independently verify its original native Stop, current selected release, immutable native selector records, snapshots, and financial/custody empty-state proof.
2. Plan **new native original directory identities** under `D:\Work\Project Atlas` with no aliases/junctions. Update all exact-path contracts and owner/clock/publisher financial enrollment readers together. A source-only search/replace or an NTFS junction is **not** a migration.
3. Prepare and review an immutable new release containing all runtime policy documents, validate a new selection chain and account roots without rewriting or adopting the old selected release or financial journals.
4. Carry out the move only after separate native user approval, one-at-a-time create-only writes, full original readback, durable recovery receipts, and independent rollback/Stop acceptance. Do **not** delete original native directories before independent readback certifies the replacement.
5. Relocate/retire historical backups and old installed versions only after restoration and audit guarantees are met; do not silently remove immutable release evidence. Verify no new C: Atlas temp or unintended D: root directories remain.

This migration is **not complete**, and none of these project instructions authorizes PAPER startup, financial account inception, provider rights, or live trading. Until migration, preserve the three original native roots and do not create any new siblings. The preferred home and the existing historical exceptions must be shown clearly in every new release/storage review.

## Audited findings

November 12, 2026, read-only native inventory: `D:\AtlasRuntime` ~4.53 GiB across 205,605 scanned entries; `D:\AtlasCustody` and `D:\AtlasPaper` contained directory namespaces but zero files; historical shutdown backup ~2.14 GiB. These are complete bounded local enumerations, not guessed disk sizes. The main repo was larger than the 350,000-entry bounded scan and its reported size is a **partial**, not the total.

C: targeted cleanup: 41 abandoned `atlas-disposable-chrome-????????` temporary test profiles dated November 8 were verified not active, contained no reparse points, and removed, recovering 69,549,895 bytes (~66.33 MiB). Shared pip cache and unrelated data were not touched.

## Mandatory end-of-execution Windows Temp cleanup (added November 12, 2026)

At the **end of every future Atlas development/Commander execution** (once its tool processes have exited), run the project script `scripts/windows/Atlas-Post-Execution-Temp-Cleanup.ps1 -ExecuteVerified`. The script narrowly removes inactive, abandoned Atlas-specific disposable Chrome test profiles from the current Windows user's `C:\Users\...\AppData\Local\Temp`, with strict path, age, activity, link and size bounds. It runs read-only without `-ExecuteVerified`, reports the number/bytes cleaned and skips active profiles. Also verify the development commands used `scripts/windows/Atlas-Use-Project-Storage.ps1` to keep new Atlas temporary data on D: in the first place.

Never delete `C:\Windows`, other users' data, shared pip/VS Code caches, recent/in-use Temp directories, or any financial receipt, selected immutable release, account journal, custody directory, original Stop evidence, or project diagnostics under D:. If a cleanup check refuses, **record the refusal**; do not bypass it or perform broad cleanup.

Cleanup is a **final step after each execution** and is not an alternative to the independent safe migration of the original three D: native directories.
