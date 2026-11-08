# R7E47K — read-only live reader and connection provenance

**Live proof-reader acceptance PASS within the retained-synthetic-helper observation profile. Daemon-generation provenance BLOCKED. Exact production-helper exit proof BLOCKED. Controlled production integration BLOCKED. Production release NO-GO.**

2026-10-18 America/Chicago, CDT UTC-05:00. Branch `chatgpt/atlas-rebuild-v1`; HEAD `f9df47b4cd80dd647d85043aba617cf00c4e6dc0`. Evidence: `logs/diagnostics/r7e47k-20261018-223521`. Latest master checkpoint, permanent contracts, H/I/J reports, native recovery authority, I adapter, retained helper evidence and H minimum integration proposal reviewed. D–J 30 source/report/fixture files remain unchanged by hash. No production startup or authority implementation modified.

## Exact proof requirements and what K establishes

| Required evidence | K result and boundary |
|---|---|
| Intended context/endpoint | `desktop-linux` metadata matches the explicit local Linux pipe; fixed endpoint independent of Docker environment/default-context routing; wrong plans refused |
| Response source | Same native pipe handle yields server PID before/after the response; actual process creation time and installed executable path checked |
| Engine identity | Exact previously observed Engine UUID, Linux OS, version/API metadata, matching before/after |
| Exact helper/image/labels | Only retained Z helper ID and approved pinned image; all expected synthetic labels must match exactly |
| Creation/start/exit facts | Typed state/PID and timezone-aware ordered timestamps; future/malformed evidence refused |
| Fresh observation window | New connection/request per observation, local request nonce and host timestamps, 2s accepted response/5s accepted collection window; stale/cached envelopes refused |
| Daemon continuity | NOT established by proxy process, Engine UUID, version, clocks or matching container records |
| Durable audit | Owner/SYSTEM native protected output, exclusive creation/flush, separate SHA-256 commitment required before return; independently reopened through protected native handles |
| Recovery authority | ALWAYS refused; no production identity or registry binding; native I consent alone cannot substitute |

Live-reader PASS means the implemented bounded read-only observation contract passed on actual retained-helper metadata and private native test pipes. It does **not** mean all prerequisites for recovery proof, real-volume inspection, startup integration or production release pass.

## Implemented files and transport

New `scripts/volume_inspector/live_docker_reader.py` and `tests/test_r7e47k_live_docker_reader.py`. Only diagnostic acceptance scripts invoke it. I's adapter/H recovery are unchanged and are not silently connected to the live reader.

The module has no generic command interface, socket, Docker lifecycle or production-volume operation. Allowed HTTP GET paths are exactly `/info`, `/version`, the exact retained helper JSON path and exact pinned image JSON path. Container listings, arbitrary other IDs, volumes, exec and lifecycle paths fail before opening a connection. The explicit synthetic scope and exact ID/image/labels are pinned in the reader. No production helper is eligible under this profile.

Transport opens `\\.\pipe\dockerDesktopLinuxEngine` with overlapped I/O. On the **same handle that supplies response bytes**, `GetNamedPipeServerProcessId`, `OpenProcess`, `GetProcessTimes` and `QueryFullProcessImageNameW` verify the server. Expected installed image is `C:\Program Files\Docker\Docker\resources\com.docker.backend.exe`. PID, creation FILETIME and image-path hash are bound to each response and must remain consistent across the collection. [Microsoft documents the server-PID query](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid). This establishes local Docker Desktop proxy provenance under the trusted-owner/OS Phase1 policy; it is not independent Authenticode enrollment, Linux dockerd process identification, administrator-compromise protection or daemon-generation proof.

HTTP framing requires complete Content-Length or bounded chunked JSON, rejects ambiguous/duplicate framing and duplicate JSON keys, caps headers at8KiB and total raw response at64KiB. Reads use fixed4KiB buffers, preventing unbounded CLI capture or background reader threads. No redirect, fallback endpoint or reconnect retry. Non-200/404, truncation, malformed metadata, uncertain source, oversized or delayed responses refuse. Missing is explicitly MISSING, never EXITED; replaced identities remain REPLACED; contradictory/running/unknown state cannot authorize recovery.

An asynchronous wait deadline cancels **only this client's I/O**, never a Docker process/container. Acknowledged cancellation releases the private client resources. If Windows cannot acknowledge cancellation within250ms, buffers/overlapped/event/pipe handle are retained in an in-process quarantine, and further reads refuse. No unsafe close/reuse or automatic retry. Absolute return-time guarantees during uninterruptible OS calls are not claimed; no kernel-stall experiment was performed. Such uncertainty cannot return recovery permission. This isolated reader does not provision a durable production uncertainty fence; that remains part of future integration.

The five-second bound is an acceptance window checked after each response, not a guarantee that every OS operation/audit flush completes in five seconds. Native response deadlines and cancellation were exercised; hardware/power-loss persistence and uninterruptible kernel behavior remain unaccepted. Valid old FinishedAt is allowed when the current observation is fresh; an old exit timestamp alone is never fresh proof.

Only selected validated metadata is persisted. Full `/info` and exact test-container/image JSON must traverse memory to decode the API response, but raw payloads, Config/Env, mounts, paths and credentials are not logged. Their wire hashes preserve evidence correlation; accepted IDs/labels/timestamps are intentionally explicit. Unexpected ownership and malformed fields do not publish arbitrary server strings. Protected audits are at most16KiB, exclusive/non-overwriting, flushed JSON then digest. A partial audit without its digest does not return a result. SHA-256 under the same account is integrity evidence, not a rollback-independent trust anchor.

## Actual read-only acceptance

Three retained-helper observation runs were preserved separately as controls were finalized; none executed a container. Final accepted source at `2026-10-19T03:43:43.410340Z` = **October18 22:43:43.410340 CDT**, six responses ending around22:43:43.417391 CDT. Coarse Windows monotonic values report0.0 for this short collection; wall observation span is about7ms, not a claim of zero resource cost. Largest raw response13,939bytes. CLI was used only for bounded selected-context metadata; actual Engine/helper responses used the native reader.

- Endpoint: `npipe:////./pipe/dockerDesktopLinuxEngine`; context `desktop-linux` maps to it.
- Engine UUID `1b4f668e-97b1-4e02-8647-454cf431e1b2`, version29.8.1, Linux.
- Reported API1.56, minimum1.40. The diagnostic GETs used the Engine's unversioned API and validated only the required schema; broad future API compatibility is not certified.
- Actual pipe-server PID17512, creation FILETIME134368537087743486, same before/after each response. Proxy binary SHA-256 `c1214651f9de3a00c37b90139e5ac7ed57f0c686a6401e311ecace59854c070a`; CLI SHA-256 `1aaf3dd59c24ff4c83d930bc51ecac8bf6f6f4e7a310573ee69d14ca3a7ef85c`.
- Retained helper `39c207ea4fac5c578dcfc1e64bc6ff9680ef9029c68aee453c9ede1adff227c7`; exact before/after fields matched.
- Image ID and OCI descriptor digest both `sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574`.
- Labels: `org.atlas.synthetic.operation=r7e46z-c5d18d33a88e42cc`, casegood and approved inspector-source digest. No production Compose/registry/inspection binding is asserted.
- EXITED observation: Running=false/PID0; Created07:36:43.654036716Z, Started07:36:43.829437977Z, Finished07:36:44.181065639Z onOctober18.
- Result `source=LIVE_READ_ONLY`, `observation_status=EXITED`, `daemon_generation=UNVERIFIED`, `recovery_authorized=false`.
- Protected final audit/digest independently reopened: native DACL/link/file identity validated before read, bytes/hash verified. No unresolved client I/O remained.

This is actual fresh metadata of an old synthetic-test container. It is neither a replay presented as a live call nor proof of exit of a production helper. No database container, volume or Genesis resource was substituted or inspected.

## Daemon-generation and cache decision

The reviewed `/info` and `/version` responses and the [Docker Engine API reference](https://docs.docker.com/reference/api/engine/) do not establish a trustworthy runtime-generation witness for this workstation. Docker Desktop's Windows server process can proxy a different/restarted Linux daemon while its own PID/creation identity stays unchanged. Stable Engine UUID/version can also survive a restart. No restart experiment or broader infrastructure inspection was authorized or performed.

Actual `SystemTime` was identical before/after: `2026-10-19T03:27:55.309515978Z`, about15m48s older than the final capture. This is an observed clock-metadata discrepancy, not proof of a restart, a specific cache mechanism or an Engine fault. It cannot be promoted to freshness or generation authority. The code records `engine_time_is_freshness_or_generation_witness=false`. Local nonces correlate local transactions; they are not server-signed challenges and cannot independently rule out payload caching inside a trusted proxy/daemon. No claim that native connection provenance alone authenticates backend computation freshness.

**Daemon-generation provenance remains BLOCKED.** No epoch is invented from clocks, PID, UUID, duplicate files or hashes. All results refuse recovery even when EXITED is observed.

Smallest practical compensating-control proposal: an explicitly approved, bounded **manual Phase1 recovery contract** using trusted workstation/OS and fixed endpoint, operator-exclusive maintenance window, independent exact-helper ownership/exit collection immediately before and after interactive revision-bound approval, durable consumed approval/recovery intent, and refusal on any contradiction/disconnect. Require no external Docker writer/lifecycle activity during that window. This would accept residual unobservable daemon/proxy-cache risk by an explicit operator decision; it would not prove continuity or control external clients. Until that narrower requirement is expressly accepted and tested, keep the current witness requirement and recovery prohibition. Do not build an unrelated institutional PKI/VPS service to disguise this decision.

## Tests and limitations

Final focused K: **47passed,0failed,0skipped**,2.72s. Final combined K/J/I/H/G/F/E/D/C/B/Y: **480passed,0failed,4skipped**,27.36s. Guarded S/T/V lifecycle: **82passed,0failed,0skipped**,49.14s. Non-overlapping final total **562passed,0failed,4skipped**. Focused runs overlap combined totals and are not added twice.

Native private-pipe cases (five) use disposable randomly named pipes in the test process: valid response and real server PID/image; delayed response causes the intended native deadline/cancellation; size overflow; truncated framing; wrong actual server image. Threads join and private handles close; no production pipe impersonation or real Docker lifecycle. Forced-cancellation noncompletion is conservatively quarantined but not independently forced in the kernel. Existing native DACL/junction/crash/snapshot tests reran; no mocked ACL result substitutes for them.

Other adversarial cases: wrong context/endpoint/helper/image/labels, source process/Engine replacement, missing container, stale/cached/future envelope, changed before/after facts, malformed timestamps/metadata, wire-size/latency bounds, connection interruption, corrupted framing/duplicate JSON, evidence-write failure, and unchanged source/Engine values failing to prove generation. Every uncertain case refuses recovery.

Original failures preserved: initial33passed/2errors because pytest expanded a65KiB bytes parameter into a Windows environment variable; fixed short test IDs, not behavior. Native fixture run38passed/1failed because sys.executable was the venv launcher rather than the actual interpreter image; fixture now queries the real image and checks exact refusal reasons. The verifier was not loosened. A single unused-import Ruff finding was removed. Subsequent focused34/39/43/47 and combined476/480 passing results remain separately retained; final counts above supersede them without erasing failures.

Four inherited skips remain unwaived: F/C true-symlink privilege1314; POSIX publisher; Linux descriptor test on Windows. Historical Z Linux evidence preserved, no container rerun. No full canonical-suite or whole-tree lint waiver claimed. Targeted RuffPASS;25Python source/test files compile in memory;18Windows scripts parse with0errors; Git diff integrityPASS. Thirty D–J files and five lifecycle files match prior accepted hashes. Native I positive approval evidence is unchanged; no new human dialog was requested.

Read-only Atlas observation22:42:23.9265412 CDT: no port8000 listener, owner/runtime manifest or production inspection registry. Consistent with operator-reported STOPPED, not a complete process-identity audit. No status recovery action or startup/stop invoked. Production database container state was not re-audited during helper acceptance.

## Release gates and next execution

| Gate | Decision |
|---|---|
| Native operator approval | PASS, I's synthetic-state scope |
| Native live reader / exact retained test-helper observation | PASS, limited profile above |
| Daemon-generation / cache-independent backend freshness | BLOCKED |
| Exact production-helper binding and exit proof | BLOCKED |
| Controlled production integration | BLOCKED |
| Production release | NO-GO |

H's all-entry integration remains proposed: durable manager intent, independent worker admission before side effects, Gaming GUI delegation, legacy/smoke guards, pre-import/direct API and standalone writers, common lock ordering and explicit failed-start/owned-stop recovery. No registry, startup code, real helper or authority was provisioned.

Recommend separately authorized **R7E47L — Phase1 Manual Proof Policy Decision and Isolated Recovery Acceptance**: present the precise residual risk above for explicit acceptance or rejection, then test only the selected isolated contract. If the operator retains strict independent daemon continuity, remain BLOCKED and identify the missing trustworthy witness; do not silently relax it. No real recovery, helper launch, registry provisioning, startup, volume inspection or integration is implied. Stop at K's decision gate.

## Verified roadmap and complete remaining inventory

Master updated only by `scripts/windows/Atlas-Roadmap-Checkpoint.ps1`; final result records exact backup equality, read-back, outside-managed byte equality and historical anchors. No Atlas/Docker lifecycle, container execution/import/removal, volumes/DB payloads, Genesis, production ACL/configuration/shortcut changes, backups/restoration, live trading/Discord, Git staging/commits/push/reset/deletion or VPS. PAPER_ONLY/MANUAL_ONLY and low-resource Gaming/normal PAPER cadence remain permanent.

1. **Core reliability/operations:** explicit proof-policy decision and exact-helper/source/all-entry recovery gates; cash-scanner scope; provider rights/HTTP/Yahoo budgets/pacing/stuck-worker/drain acceptance; Ruff disposition; artifact/licenses/dependency/clean-machine portability; live-data/runtime/rollback/Gaming cadence/resources. Separately approve real ownership/writer window, effective storage coverage/capacity, destination/encryption/key recovery, backup/disposable restore, Complete Shutdown and shortcuts. Extended benchmarks/optimization require approval.
2. **Evidence Engine:** immutable hypotheses/outcomes, replay, precision/recall/calibration/false positives, realistic fees/slippage/funding, bias controls and Research Memory. E29 NOT_READY; corroboration context-only.
3. **Fifteen-minute crypto PAPER:** eligibility/jurisdiction/rules/fees/settlement, timestamped spot/perp/depth/volatility/funding/liquidity, probability/executable edge, realistic fills and out-of-sample regime/settlement evidence before any live proposal.
4. **Cross-market intelligence:** equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable uncertainty/invalidation and reproducibility; cautious hypotheses.
5. **SaaS:** demand/pilots, tenancy/auth/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics/licensing/unit economics; pricing unvalidated.
6. **Institutional readiness:** RBAC/audit/security/incidents, governed research/workspaces/API/compliance/pilots; independently scoped stronger principal/TPM/off-machine authority; no VPS dependency.
7. **Commercial scale:** product-market fit/retention, partnerships/integrations/white-label/API licensing, evidence-led expansion and measured economics/reinvestment.

Cross-phase: E136 independent rollback witness, dual-database consent resurrection/atomic recovery/fencing, recipient transport/render/storage and uncertainty/dead letters. Discord explicit approval/durable no-backfill/no automatic uncertain retry. Prediction exactly-once/pre-deadline/auto-flat; portfolio-versus-strategy risk undecided. Preserve PM-V2.1–PM-V2.6 discovery/calibration/edge/pre-event PAPER/evidence/dashboard; one position per market, no combos/stacking/averaging/opposing YES+NO; settlement research never overrides pre-event safeguards. Atlas/Genesis separation remains absolute.
