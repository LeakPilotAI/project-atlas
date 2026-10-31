# Bounded Windows Time experiment — October 30, 2026

Base `f1086079b3b84111c88a8fd457ab43987e9642da`. The operator explicitly approved **one** bounded administrator experiment with two exact setting changes and conditional rollback. That grant was used once and is now consumed. **The experiment aborted early because of an error in the diagnostic scope guard. It did not demonstrate qualifying clock evidence.** No second elevation, retry, additional system inspection or correction followed the stop.

## Exact before, application and recorded rollback

| Setting | Original, preserved before writes | Applied and effective readback | Recorded rollback and effective readback |
|---|---:|---:|---:|
| `W32Time\Config\MaxPollInterval`, REG_DWORD |15|6|15|
| `W32Time\Config\UpdateInterval`, REG_DWORD |360000|100|360000|

Both target fields were confirmed **Local** in the fresh administrator effective-configuration preflight. The complete effective output, every original `Config` value/type and source/service snapshot were durably preserved before effects. Writes were restricted to those two names: two application writes and two rollback writes. **One application reload and one conditional rollback reload** returned exit code 0. The final retained `/query /configuration /verbose` also returned 0 and explicitly reports original values **15 / 360000 (Local)**.

Service/source readbacks before and after record **Running / Manual / NTP / `time.windows.com,0x9`**. MinPollInterval 6, SpecialPollInterval 64, PhaseCorrectRate 1, FrequencyCorrectRate 4, LocalClockDispersion 10 and all other captured configuration values match, except the separately discussed `LastKnownGoodTime` timestamp. No source, firewall, service start/stop/restart, startup setting, manual clock setting or explicit resync command was issued. No Atlas clock criterion changed.

## Why the run aborted

The runner incorrectly treated **every value under `W32Time\Config` as immutable configuration**, apart from the two approved names. About 21 seconds into the applied stage, its full-snapshot comparison encountered `LastKnownGoodTime` changing and raised:

`FOREIGN_CONFIGURATION_CHANGE_LastKnownGoodTime`

The same overly broad comparison ran after restoring and reading back the original settings, so the runner recorded:

- Elevated result: **`UNRESOLVED_ROLLBACK_NOT_CONFIRMED_STOP`**, exit code **42**.
- Parent result: **`REFUSED_OR_UNRESOLVED_STOP`**.
- Original automated `rollback_verified`: **false**.

**Those original statuses and receipts remain unchanged. They are not converted into a passed experiment or a passed full-state verification.** The guard defect was my implementation error, not evidence that the two Windows setting writes failed.

Offline comparison of the retained snapshots identifies **only `LastKnownGoodTime`** as different after rollback; its REG_QWORD/FILETIME value advanced from **06:17:11.0761017 to 06:18:15.6092092 Central**, a 64.5331075-second advance. This is consistent with normal synchronization timestamp progress. No writer-attribution trace was collected, so it is not presented as forensic proof of the actor. Atlas did not write or restore that timestamp.

The recorded target registry values and successful **effective rollback query do establish restoration of the two approved settings at that readback**. The broader automated check nevertheless failed because of its timestamp comparison. No fresh system query was performed after the stop to override the original unresolved flag. The full-run verification remains incomplete, and the stop is preserved.

Pure offline replay of the exact original `Assert-Scope` function reproduces the same refusal on the retained restored snapshot. A synthetic **in-memory only** control holding that timestamp unchanged passes; no OS value or retained evidence was changed. This isolates the guard error. It does not authenticate a new live system state, fix the original receipt or grant another experiment.

## Genuine clock measurements

Both measurements used the existing native `_WindowsProbe` and unchanged `uncertainty_ms` calculation. No fixture, alternate clock declaration or packet-only substitute was accepted.

| Measurement | Before application | First applied observation |
|---|---:|---:|
| Acquisition time, Central |06:17:49|06:17:54|
| Synchronization age, seconds |39.2757191|43.9476539|
| Dispersion, ms |786.8654|786.8654|
| Absolute phase offset, ms |718.2582|709.6806|
| Half root delay, ms |15.76465|15.76465|
| Wall/QPC disagreement, ms |0.0181|0.0087|
| Drift over age, ms |19.63785955|21.97382695|
| Drift over 240-second validity, ms |120|120|
| Drift during collection, ms |0.409906|0.18986485|
| Fixed margin, ms |1|1|
| Actual rounded Atlas uncertainty |**1662 ms — REFUSED**|**1656 ms — REFUSED**|

Both status samples report Leap 0, Stratum 5 and Last Sync Error 0. No `LocalWindowsClock` capability or qualified-success file was created because neither sample passed. The small initial difference does not establish long-run efficacy. The first normal timestamp advance triggered the guard before the next scheduled sample, so **the intended observation sequence was not completed**. No inference is made that the proposed settings would or would not qualify over a complete 180-second observation.

## Limits, cleanup and evidence

- **One administrator elevation**, retained exact owned-process handle; the elevated child self-exited, and the parent closed its handle. No global termination or unrelated process action.
- Parent total duration **26.000 seconds**, well inside **300 seconds** including the rollback and its readback. Elevated final receipt retained **274.380 seconds** of the common deadline. The 180-second observation ceiling was not exceeded; safety refusal stopped it early.
- One confined nonfinancial diagnostic directory: `logs/diagnostics/qd-w32time-discipline-experiment-v1`, **9 retained files / 97,221 bytes** at review. Raw before/applied/final records, payload, reservation, both clock samples and parent receipt were preserved. No deletion; **0 bytes recovered**.
- Exact original administrator template SHA-256: `ec764032f66238d3713c9fcea2cc5b81a947fdc0298cc42b210626763daeb9e7`. Original executed payload and all raw file hashes are retained privately. Neither runner nor payload was edited after the execution.
- Offline evidence review: `logs/diagnostics/qd-w32time-discipline-offline-review-v1.json`; exact guard replay: `qd-w32time-guard-failure-reproduction-v1.ps1`. These read retained evidence only and issue no Windows query or configuration action.
- Existing clock/IEX regressions: **62 passed, 0 failed, 0 skipped, 1.56 seconds**. Preflight offline guard tests passed two controls/four expected refusals but missed dynamic timestamp advancement. Their success did not prevent this genuine uncovered failure; no claim of complete lifecycle coverage is made.

## Remaining work and authority boundary

First correct and offline-test the diagnostic guard so it distinguishes configurable policy values from narrowly identified Windows-maintained timestamp state, while still refusing actual policy/service/source/type/value changes. Keep target-setting rollback readback separate from broader snapshot differences. Never restore `LastKnownGoodTime` to make snapshots equal, ignore arbitrary keys or weaken Atlas's 1,000 ms/120-second/continuity requirements.

**No additional system action is authorized by this consumed grant.** A corrected runner must be reviewed and separately authorized before any fresh administrator experiment or live reinspection. Because the original broad rollback verification remains failed, there will be no automatic retry or commissioning continuation. Existing target-value restore evidence is retained explicitly; uncertainty about broader automation is not hidden.

The historical correction proposal stays immutable; this new dated report records the actual approved-but-aborted execution. Canonical roadmap, autonomous recovery state, queue and checkpoint preserve the exact failure and next boundary. Prior source package, installation, financial records/journals, original frontend, all seven phases and 21 decisions remain unchanged. No provider, enrollment, financial account, installation promotion, PAPER startup, live order or Genesis action occurred.

**Outcome: ABORTED / NO QUALIFYING CLOCK. Approved target values read back as restored; original full rollback guard status remains unresolved. PAPER startup: NO. Production: NO-GO.**
