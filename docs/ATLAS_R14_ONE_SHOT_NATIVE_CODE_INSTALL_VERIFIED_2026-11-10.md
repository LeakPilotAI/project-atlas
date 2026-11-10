# Atlas R14 one-shot code-only native installation — verified and unselected (2026-11-10)

## Terminal result

**SUCCESS: native create-only R14 code installation and installed-runtime readback completed** in a single one-shot attempt, with no release selection, provider/account connections, PAPER/live order permissions, service startup, cleanup, or Project Genesis changes. The exact one-shot approval was **consumed and revoked in installer source** immediately after receipt inspection; `APPROVAL_SHA256=None` and the permanent create-only destination disallow rerun.

The operator's explicit 2026-11-10 authorization was scoped to one low-impact R14 **code-only installation** to progress toward full financial PAPER production, not to immediate financial or live trading. New private ignored code-only consent bound exact package/source/dependency hashes to the local operator Windows SID; private single-run lease `logs/diagnostics/atlas-r14-code-only-install-one-shot-run-20261110.lock` was exclusively created before any independent-clock qualification. The private consent file is preserved (not committed/pushed or shared) for historical evidence, and the approval pin in `scripts/atlas_r14_low_impact_installer.py` has been reset to `None`.

## Exact results from executable terminal evidence

| Evidence | Verified outcome |
|---|---|
| Single-run wrapper | `logs/diagnostics/atlas_r14_authorized_code_install_once_20261110.py` (private ignored) |
| Approved source release commit | `7ff9d3dba2eabe110f843c13efac49464805de2a` |
| Source archive SHA-256 | `22e4d00cb61c56d0b298c059e597937696df8deeca25c7ec6b38ec5ff01e192a` |
| Source-file inventory | 953 tracked source files + 9,566 pinned native Python dependencies = **10,519 native files** |
| Native directories | **912**, including the new root |
| Planned native bytes | **263,456,250** |
| Genuine two-public-peer independent NTP initial uncertainty | **139 milliseconds**; independent 180-second qualification passed before native I/O |
| Resource headroom at preflight | **102.8 GiB available RAM**, **754.7 GiB available disk**; NBA2K27 absent |
| Installation and child native readback | **VERIFIED**; standalone 64-bit Python **3.12** executable and stdlib inside installed R14 |
| Wrapper return | **exit 0**, total **318.80 seconds** including NTP qualification |
| Native installed release destination | `D:\AtlasRuntime\releases\7ff9d3dba2eabe110f843c13efac49464805de2a` |
| Final native receipt (private ignored) | `logs/diagnostics/qd-unselected-release-7ff9d3dba2eabe110f843c13efac49464805de2a.json` |
| Final receipt SHA-256 | `4cbf4f78c4da879f0e7d35f7ab1c3e119b4e0e7fc04640f0984ad4c8ce912ba7` |
| Native file-inventory artifact digest | `da64e2436d23fc2e3aa7ea14888e3fa0429bea801b83886c181ec3a72fd16fa8` |
| Installed release postcopy journal | Two entries: code-only create intent + durable `NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING` with matching artifact digest; no terminal refusal |
| Previous selected R12 receipt SHA-256 | **`f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`**, unchanged |
| Prior R13 failed partial and refusal | Preserved intact, not reused or deleted |
| PAPER/live/financial/provider/startup authority | **False across receipt**, never enabled |

## Post-install acceptance and safety

Following terminal success, an independently launched small read-only verifier checked exact receipt SHA-256, schema, source release, archive/inventory hashes, file count 10,519, directory count 912, receipt-file digest equality, Python 3.12/64-bit installed layout, immutable R12 selector and prior failed R13 refusal journal, and presence of the final receipt paired with the journal's durable verified-before-publication entry. **All checks passed.** This post-install audit read the existing 2-3 MB receipt, **not all 263 MB of installed native file contents again**; full original ACL/file identity/hash and installed interpreter readback occurred inside the actual one-shot installer.

The successful R14 destination is now permanently **occupied and verified, unselected**, so old preinstall tests were made state-aware and must **refuse a new installation attempt**. The combined Windows IDLE-priority focused R14/R13/resource-host suite passed **68 tests, 0 failed/skipped in 1.64 seconds** after native success, with no second native copy, provider access or trading. The previous V13 timeout was not reused; this R14 attempt succeeded under the less expensive NTP/pacing and game-safe host checks, but the precise contribution of each optimization was not independently benchmarked.

The source approval temporarily pinned a private exact SHA-256 during execution at Git commit `841cf861`, with all finance/provider/startup/selection scope flags false. It was disabled immediately after successful native readback. The one-shot private consent and run lease remain ignored evidence; do not add them to Git or forward their contents. No repeated R14 installation is allowed.

## Next roadmap gate — not automatically satisfied

**R14 is installed, NOT SELECTED or financially commissioned.** A separate read-only assessment of R14's immutable native receipt, source/provider rights, launcher/Stop integration, and existing selected release state must precede any operator-approved release selection. A new R14 code installation is **not necessary** for that review. Independently accepted Quality Dips and Hyperliquid forward-PAPER source and runtime gates remain outstanding; Kalshi integration is a separate workstream. **Financial PAPER production remains NO-GO, 0/9 independently accepted operating gates.**

No automatically started service, broker/Hyperliquid/Kalshi credentials, real Robinhood account, financial trade or public GitHub push was touched.


## Verified next barrier: old release selector does not recognize R14's new journal

A **read-only code/reference compatibility check** confirmed that `scripts/release_selection.py::validate_spec` accepts an exact reference to the new R14 native release with receipt SHA `4cbf4f78c4da879f0e7d35f7ab1c3e119b4e0e7fc04640f0984ad4c8ce912ba7` and artifact digest `da64e2436d23fc2e3aa7ea14888e3fa0429bea801b83886c181ec3a72fd16fa8`, but the currently installed `NativeInstalledReleaseVerifier.open()` **does not yet accept this native installation's acknowledgment protocol**. Its source currently requires the journal's final event to equal `{"stage":"UNSELECTED_CODE_INSTALL_VERIFIED","receipt_sha256":"..."}`, whereas R14's pinned verified-before-publication journal ends with `NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING` and artifact digest; the separately existing fully verified final receipt is the authoritative terminal proof.

The existing `ReleaseSelector.change()` also restricts the `INDEPENDENT_TWO_PEER_NTP_CODE_SELECTION_V1` profile to an **older frozen V7 source release**, not this R14 source. Both are genuine **code-only selection blockers**—not failures of the successful R14 native copy. **No selector call that would read all installed files, select R14, publish a new revision, or mutate R12 was executed.**

Next: develop a version-specific, fail-closed native installed receipt + append-only acknowledgment verifier for R14 **without weakening prior selected-release rules**, then separately review and authorize exact R14 selection using independent clock and the current immutable selected head. Avoid using a legacy Windows-clock pathway to bypass the V7-only NTP selection restriction. Only after separate selection and the still-unaccepted financial operating gates can the user move toward automatic full forward-PAPER operation.
