# Unselected operational code copy — preflight stop, October 30, 2026

Base: ddc1c886eb6cb43a248cb5e53a9c0611335ffc78, branch chatgpt/atlas-rebuild-v1. Milestone: P-QD-UNSELECTED-OPERATIONAL-CODE-COPY-V1.

**Outcome: REFUSED BEFORE COPY — WINDOWS TIME STOPPED. Operational installation did not begin. The one-copy authorization remains unused, conditional on all mandatory checks.** No destination, installation intent journal, receipt or completion ACK was created. No release was selected/promoted and no financial service, PAPER session, account, provider or Genesis resource was accessed/activated.

## Authority and exact pins

The attached directive initially named historical proposal V1. Read-only verification found its installer pin did not match the repaired source:

- Historical V1 installer SHA-256: 92fe450914682f570ce8a554d4aea28cced645c018d7543bc7455b66b95dd977.
- Current installer SHA-256: 7e383d14b0404f5d23fcbca75408a612dbf4bb413fade116cba14b9f52764fc6.
- Physical copier and source-plan hashes still match both proposals.

No V2 substitution occurred under the V1-specific instruction. The operator then explicitly answered **“Authorize current V2 pins”**, retaining the same ONE unselected copy and all exclusions.

Current authorized proposal: docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V2_2026-10-30.json. Canonical UTF-8/LF SHA-256: **09e899b09916300aec70b69d743d4c7e2383f43ecb58cea4a032f4070988917e**. All three current adapter source hashes match V2. Historical V1 and closure/native reports remain unchanged.

The application archive, selected inventory, dependencies, destination and limits are identical across V1/V2:

| Item | Pinned identity |
|---|---|
| Intended source release | 2c039af29dfefd1df77e0caa3db3fdf5ed188118 |
| Intended unselected destination | D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118 |
| Application archive SHA-256 | 0e65fae1891fc8d406f086a6aa711781053aa7d9a6b3cf1c9c7963f709c87677 |
| Selected source inventory SHA-256 | 8a19ec246e3055c105a5b6a59523dba05dfad3d439bfaf3cceb892c831a384bd |
| D-runtime dependency inventory SHA-256 | 93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91 |
| Expected plan, historical verification | 638 application + 9,566 dependency files = 10,204 files; 903 directories; 260,369,081 payload bytes |
| Limits | 600 seconds / 40,000 entries / 1 GiB |

The destination, matching final receipt and .pending.jsonl intent journal were observed absent. Values above are proposal pins and prior evidence, not an installed result. Full copy-time archive/native source admission and selected-release integrity/resource checks remain pending; no historical snapshot is substituted for them.

## Fresh clock refusal

The existing, unchanged LocalWindowsClock acquisition ran in a **normal, non-elevated, non-AppContainer Windows process**, bound to the intended installation runtime. It refused:

**CLOCK_NATIVE_QUERY_REFUSED → CLOCK_STATUS_QUERY_FAILED → The service has not been started. (0x80070426).**

A second read-only diagnostic query returned the same failure. A separate direct read confirmed:

| Current fact | Observation |
|---|---|
| W32Time state | Stopped |
| Startup type | Manual |
| Configured type | NTP |
| Configured source | time.windows.com,0x9 |
| Qualifying uncertainty | UNAVAILABLE; no accepted measurement |
| Qualifying synchronization/evidence age | UNAVAILABLE; no accepted measurement |
| Required limits | At most 1,000 ms uncertainty and 120 seconds evidence age, unchanged |
| Accepted capability | None |

No W32Time start/restart/reload, explicit resync, peer/source/registry/firewall/startup change or manual time adjustment was attempted. Service startup itself would not prove synchronization or qualifying uncertainty. Old 196-ms or other accepted measurements remain historical and revoked/expired.

Private raw clock refusal evidence: logs/diagnostics/qd-unselected-operational-code-copy-clock-preflight-v1-20261030.json. The evidence is diagnostic, not durable financial custody or authority.

## Installation and validation status

- **Installed release: NOT CREATED. Copied files: 0. Created installation directories: 0. Copied bytes: 0.**
- Native installed identity/hash/ACL/namespace/readback, installed module origins, durable installation receipt/ACK and post-copy handle/process checks: **NOT EXECUTED**, because no writer started.
- Current selected installation: untouched by this execution; no selector, shortcut, previous release or protected financial path was written. Its current complete integrity was not re-audited after the mandatory stop.
- No installation-owned process/listener/port started. Only read-only preflight/Windows queries ran and returned; no service or financial process was launched.
- No new regressions were run: no implementation changed, the mandatory clock gate failed before the installation, and prior completed tests should not be repeated merely to increase counts. The historical **223 passed / 0 failed / 0 skipped** closure evidence remains preserved; it is not this task's installed acceptance.
- Unrelated modified research test, untracked private evidence, original two native harness failures, lint-cache variance and unattributed intermediate metadata-digest mismatch remain unchanged. B1/C1/D1/E1, all 21 decisions, seven phases and the sole-operator personal policy remain intact.

## Exact next action

The immediate missing authority is **a narrowly bounded start of the existing Windows Time service**, leaving Manual startup and time.windows.com,0x9 unchanged, with no explicit resync or configuration change. Observe normal behavior for no more than 180 seconds, then use the unchanged native clock validator. If Windows requires administrator permission, that permission must be explicitly supplied rather than bypassed. The present copy directive did not authorize that service action, and its mandatory clock-failure stop was obeyed.

After separately authorized service recovery, qualifying clock evidence is still mandatory. If it passes, the existing **unused V2 one-copy grant** can continue through the remaining real source/resource/selected-release preflight and the exact reviewed adapter. No duplicate account, release selection/promotion, provider, financial startup or PAPER authority is added. On any further refusal, preserve the state and stop; never retry uncertain installation publication.

**Operational code copy: authorized with V2 clarification, NOT STARTED. Selection/promotion and financial activation: NOT AUTHORIZED. PAPER startup: NO. Production: NO-GO.**
