# Support native single-run validation V1 — grant consumed

Base: **5f92dcd185b8810d99ece2407bcd8af8a9abb763**; branch chatgpt/atlas-rebuild-v1.

**One newly authorized native validation executed: 224 passed, 1 failed, 0 skipped. Authorization CONSUMED. Restart acceptance remains incomplete. No operational installation or release selection occurred.**

## Scope and preflight

The operator supplied one fresh grant under docs/QD_SUPPORT_DEPLOYMENT_AUTHORIZATION_PROPOSAL_V1_2026-11-01.md, exact raw SHA-256 **bf1303ec30c514c0039596d0c06259d7502973cdfaca64d35e1d1777876fece2**. The operator separately clarified that fixture-only selector records were allowed and operational selection remained prohibited. No old grant was reused.

Verified branch/HEAD, roadmap/recovery state, source/package pins, absent destination, non-reparse ancestors, available storage and unchanged unrelated research-test bytes. The exact fixture was:

D:\Work\Project Atlas\logs\diagnostics\qd-selector-v1-native-support-final-20261101

Limits: 600 seconds, 40,000 entries, 512 MiB accounted storage. Application-copy preflight required less than 300 MiB/12,000 planned entries; native copy admission stops at 350 seconds. Support installation separately enforces 600 seconds/8,192 entries/64 MiB.

## Programmatic supervision

tests/run_support_native_once.py starts exactly one worker suspended, assigns its creation handle to a private Windows Job, then resumes its primary thread. Only that worker's descendants belong to the Job. No process-name, unrelated PID, firewall, service or system-configuration operation is used.

The supervisor monitors root identity, reparse/special entries, monotonic time and every filesystem name. Hardlink aliases are counted separately; accounted storage is logical bytes plus 4,096 bytes per entry. Conservative stops at 540 seconds/38,000 entries/480 MiB reserve capacity for in-flight writes, evidence and owned cleanup. Unexpected state refuses acceptance and closes only the owned group. The root/consumed marker cannot be adopted or retried.

Executed guard canonical LF SHA-256: **edb794cc1ae94178f7f1988cbc56d2f779884baf83cb63e2e1143ed8d4cbf9c4**. Later source-only hardening also refuses direct worker entry after completion and adds an exclusive worker-start claim. That addition was not retroactively treated as part of the executed guard; completed-worker refusal was tested offline.

## Actual results

| Evidence | Measured result |
|---|---|
| Entire supervised run including owned cleanup | **269.532 seconds** |
| Pytest | **224 passed, 1 failed, 0 skipped; 268.86 seconds** |
| Worker test-call measurement | 268.953 seconds |
| Native synthetic application | **10,204 files, 903 directories, 260,369,081 bytes** |
| Native application copy | **165.375 seconds**, with concurrent monitoring |
| Support installation/readback | **0.515 seconds**, 20 new entries, 167,148 written bytes |
| Independent copied-interpreter readback | Verified DISPOSABLE; zero handles after close |
| Peak monitored entries | 13,369 |
| Before final supervisor result | 13,369 entries; 264,756,092 logical / 319,515,516 accounted bytes |
| Including final result | **13,370 entries; 264,756,869 logical / 319,520,389 accounted bytes** |
| Ceiling comparison | Below 600 s / 40,000 entries / 536,870,912 accounted bytes |
| Python filesystem instrumentation | 2,936 permitted events, zero denied/outside attempts |

Raw evidence remains private inside the fixture: authorization-consumed.json, pytest-stdout.log, pytest-stderr.log, worker-result.json, native-setup-result.json, run-result.json and the case's controller progress/terminal logs. Nothing was overwritten or deleted. Python instrumentation is not whole-system Windows filesystem auditing. Caches/TEMP were confined or disabled.

## Lifecycle

First Open used the copied D:-resident Python and deployed support. Six original page GETs succeeded; selected financial values remained unavailable/null with startup false; financial POST returned 403. Then:

- PowerShell adapter Stop: **1.9351642 seconds**.
- Independently observed request-to-ack: **1.969 seconds**.
- First stopped port's explicit connection probe failed as expected.

Second Open refused with **OWNED_INSTALLED_DESKTOP_READINESS_REFUSED:image**.

Failed case: tests/test_support_deployment_native.py::test_real_installed_powershell_open_close_restart_http_and_rollback. Only the image predicate failed; the other twelve readiness predicates passed. That predicate compares controller/native-observed image to the retained .NET snapshot, and the snapshot to the exact Python path. Raw individual image values were not retained; this does not prove which comparison differed or establish a complete Windows root cause.

No second accepted runtime/final Stop timing exists. The refused instance was cleaned up. The combined case did not reach final baseline rollback; its fixture-only revision-one evidence remains. Separate native selector/rollback cases passed. No operational selection changed.

No new Chrome/interactive-form acceptance is claimed. The full case remains FAILED despite first-cycle HTTP/Stop success.

## Cleanup

The Job reported **zero active processes after the worker and before handle closure**. Owned Job/process/thread/log handles closed; no forced cleanup occurred. Independent native readback retained zero handles. A subsequent Windows query filtered to this exact fixture executable prefix found **zero remaining owned images**. No unrelated process was stopped or broadly inventoried.

The first port was independently probed. The rejected second instance's port was not retained for a separate probe; group emptiness establishes no surviving owned listener, not a global claim about unrelated ports.

## Post-run source repair

The adapter cached Process.MainModule.FileName immediately after Start and reused it after awaiting READY. This is a concrete ordering defect: the decision needs a fresh native observation after readiness. An early/unavailable module snapshot plausibly explains the image-only refusal, but **causal attribution remains unproven** without the raw values.

Source now initializes Image to null, waits for READY, calls Process.Refresh(), queries MainModule.FileName, then performs all exact image/path, PID, creation-time and isolation checks. Missing/foreign images still refuse. It never substitutes a claimed/expected path as evidence. Validation is a private helper; exported Open/Close behavior and eight-second Stop remain unchanged.

tests/test_support_ready_image.ps1 passed **19 offline mocked cases, zero failures**, with no controller/application or fixture creation. They cover late/stale/missing image, old apparent match, wrong claim, matching foreign claim/native image, wrong PID/creation/release/head, provider/trading/autostart changes, integer-false coercion, exited process, and default/domain/workspace refusal. Analysis cache was disabled through process environment.

One source-only negative check confirmed completed-worker reuse refuses before any worker/job/copy action. Ruff --no-cache and compilation passed. These are **not genuine native confirmation of the repair**. No second native validation/install/runtime followed grant consumption.

## Source-only repair candidate

Tested historical packet68962f.../ffb92b.../260438... remains unchanged. A separate source archive contains the repair:

- docs/QD_SUPPORT_DEPLOYMENT_MANIFEST_V1_2026-11-02.json: canonical SHA-256 **7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3**.
- Support manifest SHA-256 **5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc**.
- ZIP SHA-256 **dc6269c8b7ff6babcf73340c5aa5987a128ae1d76e6092ce1def653814af01bf**.
- Nine sources, 156,907 source bytes, plus manifest: ten entries; 49,062 ZIP bytes.
- Private archive: logs/diagnostics/qd-support-deployment-reviewed-source-20261101/readiness-image-repair/support-source.zip.

Packaging was source publication, not another native run. This hash/namespace-verified candidate is **not installed**. The supervisor still names the consumed fixture and refuses reuse. A later scope must review fresh root/runner configuration and repair pins. See docs/QD_SUPPORT_READY_IMAGE_REVALIDATION_PROPOSAL_V1_2026-11-02.md.

## Final boundary

Grant CONSUMED. Further genuine native validation requires new explicit authorization. Until then, repair and complete Open → Stop → Restart → Stop remain unconfirmed. Do not deploy/promote either packet based on offline cases.

No D:\AtlasRuntime write, operational selection/promotion/rollback, shortcut change, financial service/account/inception, provider connection, PAPER/live trade, Windows Time action or Genesis access. Original UI, unrelated research edits, prior failures, all 21 decisions, seven phases and B1/C1/D1/E1 preserved. **PAPER startup NO. Production NO-GO.**
