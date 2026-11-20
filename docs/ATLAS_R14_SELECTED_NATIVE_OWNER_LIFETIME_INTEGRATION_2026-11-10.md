# Atlas R14 selected-native financial owner lifetime — isolated integration (2026-11-10)

## Outcome

**SELECTED NATIVE R14 OWNER/SUPERVISOR CODE VERIFIED WITH DISPOSABLE TWO-LANE PAPER SESSION; FINANCIAL PAPER STILL NO-GO.** This follow-up goes beyond the previous PowerShell-only installed native Stop test. The **actual selected native R14 Python 3.12.10 executable** imported the selected R14 `PersonalInstalledPaperStopOwner`, `UnifiedPaperRuntime`, `run_personal_installed_owner_session`, Python Win32 Stop event implementation, and installed R14 PowerShell Stop requester. Existing preapproved *offline* financial-owner test helpers injected synthetic quality-dips and Hyperliquid lane objects and a **temporary** real SQLite `PaperStopReceiptLedger`; no brokerage provider, real account, market data, financial order, operational Start or desktop shortcut was activated.

The standalone source is `tests/fixtures/atlas_r14_selected_native_owner_smoke.py` (SHA-256 `12b12f9885e35f15477450349091b82f92616cd7c97391e04f51e70bd2722e66`). The low-impact reproducible pytest wrapper is `tests/test_atlas_r14_selected_native_owner_interpreter.py` (SHA-256 `0281a10553a95bb18facc0c51f794a676721649b1c3d210c7c456df45aa9917b`).

## Evidence and exact boundaries

The test child ran `D:\AtlasRuntime\releases\7ff9d3dba2eabe110f843c13efac49464805de2a\python\python.exe -B`, from the selected R14 release working directory with `PYTHONPATH` restricted to the selected R14 root, its native `backend`, and the repository's **tests-only helper folder**. The test asserted module `__file__` identities are the installed R14 paths, not workspace production code, and the original SHA-256 for:

- Selected `backend/app/services/personal_installed_stop_owner.py`: `73033ec5829b9cd68daf580e6b4e4c6c958651a3e5f49c6e63bf4b84ea226113`.
- Selected `backend/app/services/unified_paper_runtime.py`: `b5d1db20202a337b7ea6a9321377b56fac523ac5c3b67e6f7213eee857742007`.
- Selected `scripts/observation_runtime/personal_paper_python_stop_signal.py`: `d002c7adf8ede7b3cc3aa0602c0807de70407061443781d203b6585fda629715`.
- Selected `scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1`: `893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc`.

The selected native revision remains **13**, SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31`, with the original R12 ancestor retained. A new revision 14 was **never created**.

Three distinct supervised, temporary session scenarios passed:
1. A genuine second-process PowerShell request using the **selected R14 native requester module** delivered the Windows named event to the actual selected R14 Python financial-owner session loop. The synthetic bridge's one-shot Stop created a `FINISHED` two-lane flat-and-drained receipt in SQLite; a newly reopened `PaperStopReceiptLedger.recover()` reproduced the receipt. The owner refused a new signal after handle close; no synthetic trade orders were dispatched.
2. A bounded owner session with no external Stop request expired and automatically closed its synthetic PAPER positions via the same durable one-shot Stop method.
3. An injected ambiguous Stop raised an error, closed entry admission, moved the runtime to `STOP_INCOMPLETE`, and retained **one** Stop attempt with no automatic retry or false success.

The standalone selected-native execution returned **exit 0**, `R14_NATIVE_OWNER_SUPERVISED_DISPOSABLE_ACCEPTANCE_3_OF_3`. The combined Windows IDLE-priority narrow wrapper + prior native-owner lifetime/binding + installed PowerShell transport tests returned **28 passed, 0 failures/skips in 9.97 seconds**. An initial fixture-hash transcription typo and wrapper string syntax error were corrected *in tests only*; final run passed. No native installed file changed.

## Operating readiness

This is a **source/transport integration prerequisite**, not evidence of a real financial session. The offline helpers synthesize installation authority and the Stop bridge: genuine provider/data entitlements, real Quality Dips and Hyperliquid PAPER writer custody, live/current market readback, per-lane owned accounting, independent financial time qualification and supervised financial operations **remain unaccepted**. The old desktop `ATLAS.bat` and `ATLAS-STOP.bat` are correctly blocked; no one-click financial Start/Stop was enabled. Kalshi newly listed YES/NO markets are a separate future operating lane and were not exercised here.

**Next critical implementation boundary:** build/qualify a real, separately authorized `PersonalOperatorInstallation` plus actual Quality Dips and Hyperliquid PAPER *provider/custody* ports and financial ledger, then pass the same selected-native owner-session/Stop contract using the real PAPER lane writers under supervised operation. Until then never substitute this fixture or its `test-only` objects into operator startup. Use no Windows startup-on-boot, paid data/VPS, live orders, private credentials or Project Genesis changes without a separate explicit requirement.

**Financial PAPER 0/9 independently accepted operating gates, NO-GO**. Code release R14 selected and operating execution still distinct.
