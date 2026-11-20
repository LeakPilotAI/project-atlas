# R13 low-impact CODE-ONLY installer adapter — 2026-11-09

**Outcome:** R13-specific code-only installation path **implemented and offline tested**. No actual native installer invoked, no financial PAPER activation, selected R12 untouched.

## Reason and exact observed risk

The previous disposable R13 native-copy rehearsal copied 10,518 files, then the user's Windows desktop became unresponsive during heavy testing and VS Code was force-closed. The original native secure-handle/ACL final readback was interrupted. A separate low-priority content-and-namespace recovery pass confirmed all 10,518 files, but **did not qualify operational native ACL/custody**. That existing disposable destination is deliberately preserved and never used as a new operational release.

The historical shared `_copy_prepared_code` loop checks a 600-second deadline and file-size bounds but does **not explicitly set Windows IDLE process priority, deliberately pace I/O, or avoid cumulative observer JSON serialization when one is supplied**. Modifying that historically byte-pinned module risks invalidating prior installer provenance. This milestone adds an R13-specific external adapter instead.

## What was implemented

New source file: `scripts/atlas_r13_low_impact_installer.py`.

- Pins the previously reviewed R13 `c7dfb85665bbcd5ba4494c33365d4dff8ea92b12` source archive SHA-256 `20167da274294223333ea4668d288514176a675e9308a298786abd0b46b8f39c`, exact selected inventory `c070130867636c27ae3ca31f01921a186445e7f4bc8b7ea2e9b14900893680e4`, retained native Python dependency receipt `b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0` and dependency file inventory `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`. Pins the actual R13 review JSON SHA-256 `be11c3a9353b00014f11324eb94fa6e007de03c19d2ab2ec52a832319bbf601f`; refuses any review containing enabled install or financial permissions.
- `inspect()` is **read-only**, revalidates the exact existing source/package/receipt and unchanged R12 selector, enforces the existing native install planner's namespace/capacity contract (952 source files + 9,566 dependencies = 10,518), and refuses an occupied new operational R13 destination. `python -m scripts.atlas_r13_low_impact_installer` exposes **inspection only**.
- `LowImpactEnvelope` sets the caller's *own process* to Windows `IDLE_PRIORITY_CLASS` **before any native copy**, restores its prior priority after success or error, and refuses failure to acquire idle priority. It adds bounded pacing (one 60 ms pause per 32 native admission checks), a stricter 500-second internal elapsed-time limit, a lightweight unchanged R12 selector check, and explicit failure preservation. Only one Python process is used; no worker pool.
- Correctly separates preflight **create-only** destination checks from repeated during-copy selector checks. An active copy must not incorrectly fail because the destination it just created now exists.
- A future explicitly approved `install(execute_approved=True,clock=...)` path uses existing 180-second independent two-peer NTP qualification and separate consent checks, the historical Windows native secure copy/readback primitives, create-only journal, and readback receipt. **Actual use is hard-blocked in this source revision: `APPROVAL_SHA256=None`**, and there is **no install CLI**. Approval would require a distinct reviewed exact one-shot operator consent and a separate source change. This review is not a substitute.
- Crucially, the new adapter invokes the legacy native copier with `observer=None`, avoiding huge cumulative `files` JSON snapshots every 250 files; the separate create-only journal retains intent and terminal result. Any failure is fail-closed; partial native trees must not be silently repaired/reused. It never modifies a selected release or grants financial access.

## Verification

Added `tests/test_atlas_r13_low_impact_installer.py`, covering simulated Windows process priority setup/restore after normal and failed runs; pace interval; deadline; invalid unbounded configuration; selector and create-only checks; preserving a created destination during resource checks; explicit approval refusal before native I/O; and genuine read-only R13 plan compatibility.

Ran **one low-priority, small offline pytest process** with `tests/test_atlas_r13_low_impact_installer.py`, `tests/test_native_install_candidate.py`, and `tests/test_native_install_plan.py`: **55 passed, 0 failed/skipped in 5.79 seconds**. No giant file copy, native ACL scan, provider, Python installation or account activity. This verifies adapter logic and source planner, **not a full R13 native install**.

Existing source ZIP was built from an *earlier pinned commit* `c7df...` and intentionally does **not** contain this new installer adapter; the new adapter is an independently reviewed workspace-side installation coordinator. Its own source review must be completed before new native installation is ever approved.

**2026-11-09 follow-up:** The existing disposable copy subsequently passed an independent native owner/ACL/identity/SHA readback (10,518 files, 912 directories), and the copied interpreter smoke receipt reports eight isolated module imports. This does **not** recover the original copy-creation handles or qualify an operational installation. The adapter was then strengthened with mandatory Windows IDLE-priority readback before native work, periodic drift refusal, and post-pacing deadline checks; **58 focused idle-priority tests passed**. Full boundary details: `docs/ATLAS_R13_DISPOSABLE_NATIVE_PROOF_AND_RESOURCE_GUARD_2026-11-09.md`.

## Remaining critical path

1. Independent review and separate one-shot consent for a **new** create-only operational native code installation, including qualified Windows ACL/ownership and independent clock.
2. Select an independently verified installed CODE-ONLY release under a separate approved native selection record. Installed R12 remains authoritative until then.
3. Commission actual original Quality Dips source/valuation issuer, Hyperliquid funding/oracle and fee sources, financial clock, distinct PAPER cash accounts, owned Start/Stop flatten, and supervised forward soak. **Financial PAPER still NO-GO: 0/9 operating gates accepted.**

No Genesis modifications, paid market data, external provider calls, credentials, private brokerage accounts, PAPER/live trades, selected release changes, Windows boot/clock/shortcuts, or GitHub push.
