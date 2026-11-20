# Atlas R14 code-only installer: pinned source and publication review (2026-11-10)

## Outcome and authority

**SOURCE/ORCHESTRATION REVIEW COMPLETED, INSTALLATION NOT AUTHORIZED.** This is a local code-and-contract review with deterministic synthetic tests, **not an independent third-party audit or native operational acceptance**. The original pinned R14 source package remains uninstalled, and the separately created R14 coordinator remains local workspace code.

The exact R14 native destination `D:\AtlasRuntime\releases\7ff9d3dba2eabe110f843c13efac49464805de2a` remains absent. The failed R13 native tree is preserved, its terminal refusal journal remains pinned, the native R12 selector remains SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`. The R14 adapter's `APPROVAL_SHA256=None` still makes native installation impossible without a **separately reviewed, pinned, freshly consented** code change. No financial/PAPER/live/provider/startup permission.

## Frozen package and exact review snapshot

| Exact item | SHA-256 |
|---|---|
| Frozen R14 source ZIP (`logs/diagnostics/atlas-r14-source-only-20261110-r01/atlas-source.zip`) | `22e4d00cb61c56d0b298c059e597937696df8deeca25c7ec6b38ec5ff01e192a` |
| Source preflight review JSON (not approval) | `91c181a823c4dc20fd65067dce69356159c8beb202c4d416f68dd267c298f99d` |
| R14 workspace-side installation coordinator `scripts/atlas_r14_low_impact_installer.py` | `4b2d3bbaa193134cce6f4111680db639962a9bae1ed79d6d0520acd97c3ab13b` |
| Native creation-handle copier `scripts/native_install_candidate.py` | `2f5a203f9187b8b7c18d1bb8cd5ce2bf5fe82aecd50ea8b0097c4e37d4a767d0` |
| Native installation input planner `scripts/native_install_plan.py` | `10bf8c2dd5d2ffdc3a92a576183a701e022c8e53bf5f948a6ad2fcaeb028263f` |
| Installed-release verification `scripts/install_verified_release.py` | `bcaea829d5466a293486624a95f689cf02d60e4893ef92a92ce00202c4a78571` |
| Independent NTP clock `scripts/observation_runtime/atlas_independent_ntp_clock.py` | `230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c` |
| Native release identity `scripts/observation_runtime/personal_release_identity.py` | `7295bcfc765d50520c144068310933cceac29b43bf3b350e3dec487552337a1c` |
| R14 synthetic guard/integration tests `tests/test_atlas_r14_low_impact_installer.py` | `6c1901a86b8c46268c7a2b59e9d620a687e5c92d609b588c5c2a4675ba8e6f5c` |

The pinned R14 source commit is `7ff9d3dba2eabe110f843c13efac49464805de2a`; reviewed plan: **953 source + 9,566 native Python dependency files = 10,519 files, 912 directories, 263,456,250 bytes**. This source ZIP precedes the workspace-side R14 adapter. Bind the *exact* reviewed adapter hash and native dependencies at any later install authority review, rather than assuming their source revision appears inside the ZIP.

## Substantive repair: durable final receipt is the last irreversible write

During second-pass review the R14 future-install coordinator was found to write `RECEIPT` (the authoritative final installed artifact) before attempting the journal's success event. If that *post-publication* journal I/O failed, the broad exception handler could append `REFUSED_PRESERVE_PARTIAL_NO_RETRY` **after a final receipt already existed**, yielding contradictory acceptance/refusal records.

The code now writes and fsyncs a nonfinancial **`NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING`** journal entry, including the digest, **before** it attempts to create the final receipt. It then rechecks the 500-second guard, real two-peer clock, R12 selector and operator consent, rechecks the deadline and performs the create-only final receipt publication as the **last write**. Once that final write succeeds, it returns without any further journal operation. A failed write or lost approval retains a refusal as the journal's last stage and does **not** create the final receipt in the synthetic scenarios. The pending marker alone is **not acceptance**; consumers must require the independently validated final native receipt and original filesystem readback.

This is a fail-closed source-logic correction. It does not prove Windows atomicity of bytes/fsync on disk failures or installed native ACL/identity custody; a subsequent real installation must prove these independently. Never resume or overwrite an occupied destination after any partial failure.

## Executed lightweight verification

A single Windows IDLE-priority test runner executed targeted R14 + R13 cases: **54 passed, 0 failures/skips in 3.47s**, exit 0. New synthetic end-to-end R14 tests exercised the actual coordinator through fake approvals, fake qualified clock, artificial low-impact guard and stubbed native copy/installed-runtime verifier. They verified:

- Valid synthetic completion creates exactly one nonfinancial final receipt **after** a durable prepublication journal, without selecting anything.
- Synthetic native copier refusal leaves only a refusal journal and no final receipt.
- Synthetic failure creating the final receipt leaves a journal ending in refusal and no final receipt.
- Synthetic failure writing the prepublication journal prevents any final receipt.
- Revocation of approval **after** prepublication prevents final receipt; no trading or provider action.
- Existing per-admission deadline, 32-admission/one-second NTP continuity, 128-admission pacing, R13 reuse refusal and real read-only source plan/selector checks remain in the suite.

**Simulation only:** all write tests use pytest temporary files. No real NTP requests or 180-second qualification, 263MB runtime copy/readback, financial provider/account access, operating launcher, real release selection, live/PAPER order, Windows time/boot change, Project Genesis edit, or cleanup.

## Next independently gated actions

1. The completed code and local source pins can inform a separate **exact R14 install authorization** review; before any attempt verify the current coordinator/native component hashes still match this snapshot, R14 native destination and intent/final receipt are absent, R12 SHA is unchanged, free resources and gaming/host load are acceptable, and no separate consent has been consumed.
2. If—and only if—the operator separately authorizes **one** R14 code-only native installation to that exact fresh destination, use single-process Windows IDLE priority, independent two-peer NTP 180-second qualification, 500-second bounded copy/readback, full original creation-handle/ACL/identity/hash verification and final installed interpreter proof. A refusal preserves the partial and permanently disqualifies the occupied location; no automatic retry/deletion/selection.
3. An **independent release selection** and genuine supervised forward-PAPER operating gate acceptance are still separate: **financial PAPER NO-GO, 0/9 independently accepted**. Avoid declaring progress in production trading solely from the source installer tests.
