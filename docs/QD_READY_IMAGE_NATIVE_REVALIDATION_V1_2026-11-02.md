# READY image native revalidation V1 — runtime lifecycle verified

Starting checkpoint **0ae3181afb3e39875ebed2d5bcd0e79e5edd522d**, branch chatgpt/atlas-rebuild-v1.

**Both genuine disposable Open/Stop cycles, including restart READY image verification, passed. The recorded suite is 224 passed / 1 failed / 0 skipped because of a test-harness teardown error after both cycles. That failure remains preserved; the suite is not relabelled fully green. Fresh authorization CONSUMED. No operational effects.**

## Authorized scope and preflight

One new grant under docs/QD_SUPPORT_READY_IMAGE_REVALIDATION_PROPOSAL_V1_2026-11-02.md, raw SHA-256 **1314f50ddf8ec3a59a5a9b8b3961f7306e2143ebd92d698d9fc297fb5800cd5e**. Fixture selectors/rollback expressly permitted; operational selection, promotion and rollback prohibited.

Exact fresh root: **D:\Work\Project Atlas\logs\diagnostics\qd-selector-v1-native-support-image-repair-20261102**.

Verified HEAD/branch, roadmap/state, root absence, no reparse ancestors, free space, source/package hashes, 600-second/40,000-entry/512-MiB limits and native structure layouts. Two mocked preflight checks confirmed default/completed-worker refusal without creating a Job, child or fixture.

The existing supervisor was configured only for the approved new root, proposal/hash, repaired manifest/archive and base commit. Configured/executed canonical LF SHA-256: **42a30a9c600b7c38bba6f5342424210b376e40cb26082f49668a4381acc21681**.

It launched one suspended worker, assigned its creation handle to a private Job before resuming, monitored identity/reparse/entry/storage/time and reserved cleanup capacity through conservative 540s/38,000-entry/480-MiB stops. The root/worker claims were create-new; no prior grant or fixture was adopted.

## Exact results

| Item | Result |
|---|---|
| Supervised execution and cleanup | **194.625 seconds** |
| Recorded pytest outcome | **224 passed, 1 failed, 0 skipped; 193.98 seconds** |
| Worker test-call measurement | 194.078 seconds |
| Native copied application | **10,204 files, 903 directories, 260,369,081 bytes** |
| Native copy duration | **91.063 seconds** |
| Native support install/readback | **0.422 seconds**, 20 new entries, 167,798 written bytes |
| Independent copied-interpreter support proof | Verified DISPOSABLE; zero handles after close |
| Peak monitored entries/accounted bytes | 13,368 / 319,520,425 |
| Before final supervisor result | 13,368 entries; 264,771,634 logical / 319,526,962 accounted bytes |
| Final including result file | **13,369 entries; 264,772,412 logical / 319,531,836 accounted bytes** |
| Ceilings | Below **600s / 40,000 entries / 536,870,912 accounted bytes** |
| Python write instrumentation | 2,935 permitted events; zero denied/outside attempts |
| Forced process cleanup | **None** |

Accounted storage charges logical bytes plus 4,096 bytes per entry, including hardlink aliases. Caches/TEMP confined or disabled. Python instrumentation is not whole-system native write auditing.

## Actual Control Center adapter lifecycle

Both calls used the deployed PowerShell module and actual copied D:-resident Python. Both READY records passed the unchanged exact controller PID/creation/image, selected release/head, loopback, provider-disabled, financial-disabled and autostart-disabled checks. The post-READY Process.Refresh/image query was exercised genuinely.

| Stage | Adapter Stop | Independent observer | Outcome |
|---|---:|---:|---|
| First Open → Stop | **1.8311834s** | 1.860s | READY image accepted; Stop <=8s; port probe verified closed |
| Second Open → final Stop | **1.8491529s** | 1.844s | Restart READY image accepted; Stop <=8s; port probe verified closed |

On each cycle all six original page GETs succeeded with same-origin connection policy. Selected-account cash/positions remained null and startup false; financial POST returned 403. No provider/scanner/financial initialization occurred. The controller's final exit-code/stdout/stderr assertions completed before the harness error.

This establishes the genuine nonfinancial PowerShell adapter lifecycle and read-only HTTP behavior. It does not establish financial readiness, real market evidence, new Chrome visual acceptance, the legacy interactive form's complete integration or a desktop-shortcut change. Original UI sources remain unchanged.

## Preserved harness failure

After both accepted cycles and successful final controller exit, the test's finally block attempted child.stdout.read() after communicate() had already consumed and closed stdout/stderr. It raised **ValueError: read of closed file**, at tests/test_support_deployment_native.py:148 in the executed version.

This is a harness error, not recurrence of the READY image refusal. The whole recorded case remains FAILED. Its later combined baseline-rollback/result-emission section did not execute. Separate native selector/rollback cases passed in this same suite; do not claim the combined post-lifecycle rollback ran.

The error also skipped that finally block's explicit parent test handle/store close. Those worker-owned handles were reclaimed when the worker exited. Job/supervisor handles closed explicitly, and the final owned group was empty. Do not retrospectively claim every worker handle had an explicit close in the flawed teardown.

## Cleanup proof

- Both stopped ports were independently probed inside the completed cycles.
- The Job reported **zero active processes after worker exit and before Job closure**.
- Job/process/thread/log handles owned by the supervisor closed; no force was required.
- Independent support readback reported zero retained handles.
- A later Windows query restricted to this exact fixture executable prefix found **zero remaining owned images**.
- No unrelated process was killed or broadly inventoried.

Raw evidence stays private and unchanged inside the exact root: authorization-consumed.json, worker-started.json, native-setup-result.json, controller-progress.json, worker-result.json, pytest stdout/stderr and run-result.json.

Raw SHA-256:

- run-result.json: **5d7d770635b4500b3bca4fc7a7bcf77a319f1eb5555ca73a56f9877de8a740c4**
- worker-result.json: **c1753df29e4439446b9182b15b4b4162db906ad1a07fb7aada38db18efe0a83b**
- pytest-stdout.log: **8740a88d69f46f6565805d9ecf6416aea4cf8352031ee5e105acee27a24ba068**

## Offline harness correction

tests/support_native_cleanup.py now uses the exact stdout/stderr bytes already returned by communicate(), rather than rereading closed streams. Unexpectedly unavailable uncaptured evidence still refuses; it never invents empty successful output. Nested finally blocks release the owned process handle/store even when evidence collection or recording fails.

**Six in-memory regression tests passed, zero failures**, including closed communicated streams, preserved open terminal data/errors, missing uncaptured evidence refusal, diagnostic-write failure cleanup, running-child EOF/drain and invalid-capture refusal. No subprocess, native copy, port or filesystem fixture was created by these tests. Ruff --no-cache and compilation passed.

This correction affects test code only. It was not rerun natively under the consumed grant; the original 224/1 result remains. The runtime/support payload did not change, and its nine source hashes still match the genuinely exercised packet. No repacking or new runtime validation is needed merely to describe this offline harness correction; a clean native test-case result must not be asserted without an authorized rerun.

## Source package and remaining boundary

Genuinely exercised packet remains:

- Deployment **7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3**.
- Support **5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc**.
- ZIP **dc6269c8b7ff6babcf73340c5aa5987a128ae1d76e6092ce1def653814af01bf**, ten members/nine sources, 49,062 ZIP bytes.
- Frozen application **2c039af29dfefd1df77e0caa3db3fdf5ed188118**.

Both native cycles now confirm the image correction in this environment. Prior failures, the original unequal-image uncertainty and all raw partial results remain historical evidence. Current grant CONSUMED; no additional native run or operational action follows automatically.

The next substantive boundary is operator review of exact nonfinancial operational support deployment/selection and installed Control Center/browser acceptance, with fresh genuine clock and actual resource verification. The retained harness finding must be disclosed. If the operator requires a clean rerun of the corrected native test postamble, that needs separate bounded authorization; it is not silently substituted for this record. See docs/QD_VERIFIED_NONFINANCIAL_SUPPORT_DEPLOYMENT_HANDOFF_V1_2026-11-02.md.

No D:\AtlasRuntime write, operational selection/promotion/rollback, shortcut, provider, financial service/account, PAPER/live trade, Windows Time configuration or Genesis action. Unrelated work, all prior evidence, all 21 decisions, seven phases and B1/C1/D1/E1 preserved. **PAPER startup NO. Production NO-GO.**
