# Atlas desktop Start / Stop final-launch handoff (offline inventory, 2026-11-08)

STATUS: SOURCE PREPARATION ONLY; NOT AN INSTALLED FINANCIAL LAUNCHER, AUTHORITY GRANT, OR GATE PASS.

## Current physical desktop shortcuts (read-only Win32 shell link inspection)
- `Project Atlas.lnk`: powershell.exe -> `scripts/windows/Atlas-Observation-Shortcut.ps1` (observation-only dashboard, no PAPER trading).
- `Stop Atlas.lnk`: powershell.exe -> `scripts/windows/Atlas-Observation-Shortcut-Stop.ps1` (signals observation-only shutdown, NOT financial position flatten).
- Neither shortcut currently invokes a verified owned financial PAPER session. Do not repoint until an installed authority-backed two-account Start/Stop controller is accepted.
- `scripts/windows/Atlas-Launch.ps1` and `Atlas-Stop.ps1` intentionally hard-refuse the legacy lifecycle; `ATLAS-STOP.bat` explicitly says financial flatten is unverified. Never remove these refusals or fallback to force-killing financial workers.

## Existing safe building blocks
- `scripts/windows/Atlas-Paper-Stop-Handoff.psm1` checks session and verified FINISHED / FLATTENED receipt; a standalone user-supplied `ownership_verified` boolean is never sufficient.
- `scripts/windows/Atlas-Background-Controls.ps1` supports explicitly accepted PAPER sessions but Start is disabled by default and not auto-enrolled.
- `scripts/observation_runtime/personal_commissioning_runner.py` supports bounded owned PAPER pilot and verified shutdown outcomes, but it requires actual native ownership, current L1 evidence, account inception and activation.
- `scripts/installed_nonfinancial_launcher.py` + `scripts/support_deployment.py` previously used stale `time.windows.com,0x9`; development source clock bindings were corrected to the operator's exact configured `time.cloudflare.com,0x8 time.google.com,0x8`. This source change is not yet in immutable selected release `de437abe...` (selector revision 8).

## Before desktop financial activation (offline first)
1. Complete and independently verify actual QD/HL enrollment, policy/source identities and once-only PAPER account inception; neither draft file nor directory is a granted account.
2. Finish approved provider rights and verified market-source mapping only after separate permission (currently ON HOLD).
3. Consolidate all offline source fixes, then build/install/select ONE new clean version under exact operator authorization. Preserve existing release, selector ledger and history. Do not patch installed release in place.
4. Prepare a single installed per-user PAPER-only Start/Stop dispatch, wired to both account scopes, read-only dashboard and durable stop receipts, with NO Windows boot autostart, live orders, Genesis or provider fallback. Verify the source and desktop pointer under a bounded acceptance review before repointing shortcuts.

## FINAL LAUNCH CERTIFICATION ONLY (no tests early)
- Exact native activation, ongoing owner lease and desktop Start; actual current-source bounded two-account PAPER session.
- Actual desktop Stop with owned position/order flatten, independent both-account accounting/receipts and process shutdown; explicit UNKNOWN/INCOMPLETE refusal if not verified.
- Real cold restart and reconciliation, three-reader browser/listener certification, supervised pilot then elapsed soak.
- These are DEFERRED, not waived; 0/9 canonical gates independently accepted as of the offline inventory.

## Offline evidence
- 83 passed, one skipped, zero failed: `tests/test_installed_desktop_clock_pins_offline.py`, `test_atlas_observation_shortcut_contract.py`, `test_desktop_stop_batch_safety.py`, `test_paper_gui_handoff_wiring.py`, `test_paper_stop_receipt_ledger.py`.
- None of those tests started Atlas or made provider requests; selected installed release and native account directories were not modified by this source audit.
