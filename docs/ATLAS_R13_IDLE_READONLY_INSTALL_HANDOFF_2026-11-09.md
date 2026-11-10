# R13 low-impact inspection and exact installation handoff — 2026-11-09

## Completed in this checkpoint

- Updated `scripts/atlas_r13_low_impact_installer.py::inspect()` to enter `LowImpactEnvelope` **before** calling `prepare_readonly()`, then check the deadline/priority before leaving the scope. The R13 read-only CLI now performs its source/dependency hashing and layout validation with Windows IDLE priority and restores the original process class. A refusal also restores it.
- Added two synthetic regression cases: read-only inspection under IDLE with successful restoration and rejected pinned-plan inspection under IDLE with failure-path restoration.
- Single existing idle-priority offline regression runner checked the R13 adapter, native install plan/copy and release selection: **116 passed, 0 failed/skipped, 47.58 seconds**, exit 0. This includes the genuine pinned R13 `inspect()` contract; no native bulk copy was executed. Do not claim the duration guarantees host responsiveness.
- Exact read-only plan remains: pinned source commit `c7dfb85665bbcd5ba4494c33365d4dff8ea92b12`, `952` source + `9,566` Python dependency files, total `10,518` files and `263,440,156` bytes. The operating R13 destination was checked absent before the run; selected native R12 selector retained SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7` (recheck after commit).
- The earlier disposable native ACL/content readback and eight-module Python smoke proof remain historical and separate. This checkpoint does not promote that test tree or substitute for a new creation-handle-custody verified operational installation.

## Operator-ready next milestone — NOT yet authorized

**One new, create-only, low-impact CODE-ONLY R13 installation** of the exact pinned source/dependency payload to `D:\AtlasRuntime\releases\c7dfb85665bbcd5ba4494c33365d4dff8ea92b12`, using independent NTP qualification, exact Windows operator SID and new one-shot consent receipt, native owner/ACL/identity/byte verification, independent installed runtime readback and unchanged selected R12. Preserve partial destinations on any refusal, never retry into an occupied path. Follow only with an independently approved release selection.

**Authorization state:** `APPROVAL_SHA256=None` in the adapter; there is no install CLI; even a manually supplied `execute_approved=True` fails before touching the source. This document and a broad request to “execute next” are not themselves a one-shot approval pin. A later separately reviewed source/consent revision and exact operator authorization are prerequisites. Do not create/approve such a receipt or perform the 263MB bulk installation implicitly.

**Not granted:** operational R13 selection, Atlas startup, PAPER financial writer/account activation, account/provider access, actual PAPER or live orders, or any Windows clock/boot/shortcut changes. Financial PAPER remains NO-GO, 0/9 accepted operating gates; this is a technical release prerequisite, not a financial acceptance gate. Project Genesis and deferred post-production cleanup remain untouched.

## Subsequent one-shot operator-approved attempt — REFUSED, not installed

The user explicitly authorized one low-resource CODE-ONLY R13 installation. The pinned consent record was created once, the 180-second independent NTP qualification advanced to a native copy, and the installer entered post-copy native readback. Its **500-second low-impact work deadline expired before installed readback acceptance**; terminal exit 1 after 682.27s total. The partial destination and refusal journal were preserved, no final receipt exists, and the approval pin was reset to `None`. **Never retry/reuse that occupied destination.** Exact terminal details and next recovery boundaries: `docs/ATLAS_R13_ONE_SHOT_CODE_INSTALL_REFUSAL_2026-11-09.md`.

## Host-resource boundaries

One Windows IDLE-priority process, bounded admission/deadline and periodic pacing, avoid enormous progress reports/child spawning, do not restart a partial copy. Even idle priority does not rule out disk contention or VS Code indexing of huge workspace trees; one-time operational installation requires a deliberate permission and PC responsiveness check before any large file operation.
