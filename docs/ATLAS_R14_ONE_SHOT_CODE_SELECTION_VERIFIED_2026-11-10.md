# Project Atlas: R14 selected code release — verified one-shot native selection (2026-11-10)

## Verified terminal outcome

**SUCCESS. R14 is the selected, verified native CODE-ONLY release.** The user explicitly approved the exact one-time **R12 → R14 nonfinancial code-selection** operation. A privately pinned Windows SID operator consent was validated against the reviewed proposal and immutable R12 selected head; a create-only one-shot run lease was consumed before any external clock samples; the native publisher completed **exit code 0 in 197.44 seconds**, including the required real independent two-peer NTP continuous qualification and full installed-native R14 runtime re-verification.

This is **not** financial PAPER commissioning and did not start Atlas services, connect market providers, access private trading accounts, place any PAPER/live orders, configure automatic startup or touch Project Genesis. Existing financial PAPER acceptance remains **NO-GO, 0/9 gates independently accepted**.

## Native chain and release evidence

| Verified evidence | Result |
|---|---|
| Selected native version | **R14**: `7ff9d3dba2eabe110f843c13efac49464805de2a` |
| Previous selected version | **R12**: `2d4879878bf58bea5a3ed0a986b809791f638fec` |
| Published selection revision | **13**, immutable native NTFS `D:\AtlasRuntime\selection\r0013.json` and hardlinked `r0013.pending` |
| Published revision-13 native pair SHA-256 | `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31` — the two hardlinked paths have equal bytes, original-handle identity and ACL verified by native selection-store readback |
| Published 13-record chain head | `3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383` |
| Unique selection operation | `884883becd7c9aac0e3c89f50df30415` |
| Previous 12-record chain head | `f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd` — still the immutable predecessor |
| Original R12 selected envelope | `r0012.json` SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`, **unchanged** |
| Verified installed R14 native receipt | `logs/diagnostics/qd-unselected-release-7ff9d3dba2eabe110f843c13efac49464805de2a.json` SHA-256 `4cbf4f78c4da879f0e7d35f7ab1c3e119b4e0e7fc04640f0984ad4c8ce912ba7`, **unchanged** |
| Native R14 installed file identity | Pinned artifact digest `da64e2436d23fc2e3aa7ea14888e3fa0429bea801b83886c181ec3a72fd16fa8` — previously verified 10,519 files, 912 directories, and isolated Python 3.12 64-bit runtime |
| Operator source-approval checkpoint | Git `a9bb2607`, temporary one-time source pin of private consent SHA-256 `1dd666e9079cb737e12a8d983b2a2f918496a462bae329431511174720a39242`, all financial/provider/startup permissions false |
| Authorized reviewed publisher source SHA-256 | `91ada44c914a41857ac3b6fef2809bec885310de4b5e14af2b0748aedb27eec9` before approval revocation |
| Native selection-run lease | Private ignored `logs/diagnostics/atlas-r14-native-selection-single-attempt-20261110.lock`, preserved, no retry |
| Operator consent after completion | `scripts/atlas_r14_selection_publisher.py::APPROVAL_PIN = None`. Original private consent remains ignored historical evidence; any replay is refused before clock/NTP or native selector access |
| Observed original selection process | **Exit 0**, 197.44 seconds, independent 180-second clock + full readback and exact 13-record post-publication replay successful |

## Post-publication independent read-only acceptance

A separate, lightweight read-only Windows Python process opened the **real native selection store** under its original root identity and native lock, replayed all 13 linked selection records, required the first 12 to equal the old chain, and verified the exact R14 revision-13 `SELECT` row, previous head, native receipt SHA and artifact digest. It checked R12's old envelope unchanged, the new hardlinked pair SHA-256 equality, one-shot run-lease existence and revoked selection authority. **Read-only acceptance exit 0.**

Added `tests/test_atlas_r14_selected_postacceptance.py` with genuine read-only selected-head checks, native hardlink equivalence, lease/approval revocation, and refusal of a second code-selection execution. Updated earlier source-only proposal/publisher tests to recognize that revision 13 is **now already published**: synthetic publication tests intercept only `os.path.lexists` queries for R13 target names while replacing the native store in memory, and never mutate the real selected files. Former preselection proposal helpers now correctly refuse if prior consent evidence or the published target exists.

Focused Windows IDLE-priority postselected suite, across R14 selected-acceptance, proposal, publisher, R14/legacy selection, and R13/R14 native installer protections: **208 passed, 0 failed/skipped in 13.91 seconds**, exit 0. A first postselected regression had five *test-only* preselection-state assumptions; corrected the disposable synthetic paths without changing native production selection or weakening operating permission checks, then all 208 passed.

## Operator-facing next tasks

**R14 is now selected but not started or financially commissioned.** Next use R14's selected installed runtime as the code identity for a bounded **read-only PAPER readiness/launcher/Stop assessment**. Before the first months-long automatic PAPER session, qualify source/provider eligibility, independent time, separate Quality Dips and Hyperliquid PAPER writer readback, Start/Stop lifecycle, Discord/read-only dashboards, and actual supervised nonfinancial/PAPER commissioning according to the reduced single-user roadmap. Kalshi market intake remains separate and must not be assumed active from code selection.

There is **no need to reinstall R14**, retry the original R13 partial, republish revision 13, recreate one-time consent, reinstall packages, edit Windows clock/boot services, use VPS/paid data, or place any order as part of this completion. No auto-run service was created. **Formal financial PAPER remains 0/9 independently accepted operating gates, NO-GO**, until separately evidenced.
