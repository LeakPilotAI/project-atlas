# Atlas V4 native Windows Time qualification — administrator-required next step (2026-11-08)

**Current result:** Windows Time maintenance is blocked by operating-system elevation. NO installation, source promotion, PAPER startup, provider queries, financial account operations, UAC bypass, NTP configuration changes, or desktop-shortcut repointing occurred. Canonical acceptance remains 0/9.

## Confirmed host findings

- Native Windows Time service `W32Time`: Running, effective peer `time.google.com,0x8`, source roster `time.cloudflare.com,0x8 time.google.com,0x8` (`Type=NTP`). The ordinary sync age exceeded Atlas's `MAX_AGE=120` seconds despite the service being otherwise healthy.
- Current user context: Medium Mandatory Level. Windows denied a standard `w32tm /resync /rediscover` with `0x80070005` (access denied). Registry readback reported `NtpClient.SpecialPollInterval=64`, and `W32Time\Config.MinPollInterval=6`, `MaxPollInterval=15`; these values are **read-only observations**, not a recommended manual registry edit.
- Historic unselected native installer needed 152.922 seconds to copy/read back 10,455 files. New V4 plan includes 10,482. One manual sync does **not** guarantee a fresh clock across the entire create-only operation. Repeated native resync and quality verification must succeed over the full qualification window before attempting a code copy, and quality must remain acceptable during the later installation as well.

## Staged operator-only repair helper

- Script: `scripts/windows/Atlas-V4-Windows-Time-Qualification.ps1`. No execution side effects on import. Defaults to **explicit refusal** (`ATLAS_V4_TIME_MAINTENANCE_EXPLICIT_APPROVAL_REQUIRED`). A command with `-ExecuteApproved` still refuses if Windows has not actually granted elevated Administrator rights (`ATLAS_V4_TIME_MAINTENANCE_ELEVATED_ADMIN_REQUIRED`). The script **does not self-elevate** or invoke a UAC prompt.
- When started in an independently authorized elevated Windows PowerShell process, after checking that the Microsoft-signed system `w32tm.exe`, the exact approved peer roster and running service are unchanged, it requests ordinary NTP resync and validates Atlas's genuine `LocalWindowsClock` after each sample. Default 6 samples 40 seconds apart span 200 seconds, with bounded ranges 5–10 samples and 30–60 seconds. It changes no registry keys, NTP peers, service configuration, clock acceptance parameters, runtime files, or release state.
- This is **qualification of the OS clock only**, NOT the installer. Successful samples are required supporting evidence, not a promise that the next actual installation cannot become partial. Before executing the exact create-only installation later, independently verify it has continuous accepted native time, the proposal checksum and the empty target; preserve/refuse any partial result.
- On the user's Windows desktop, the necessary real privilege grant is to open **Windows PowerShell using Run as administrator** and explicitly execute:

  `& 'D:\Work\Project Atlas\scripts\windows\Atlas-V4-Windows-Time-Qualification.ps1' -ExecuteApproved`

  This is an administrator authorization action; standard Desktop Commander PowerShell cannot silently perform it.

## Offline tests and unchanged installation state

- New tests: `tests/test_atlas_v4_clock_qualification_offline.py` verify no-approval refusal, non-elevated refusal, approved peer pinning, bounded scheduling, no registry/service/security-control override, and unchanged installer time authority.
- **71 tests passed, zero failed** across new maintenance, Windows clock, and exact V4 installation-proposal contracts. The safe refusals were also observed directly in separate noninteractive PowerShell processes.
- `D:\AtlasRuntime\releases\fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`, its diagnostic install receipt, and the adjacent pending journal remain absent. Current immutable selected release stays `de437abe888a2d20746762a39402ae421417c1f6`, selector revision 8.

## Acceptance boundary

Do not suppress `CLOCK_STALE_OR_NEGATIVE_QUALITY`, forge a clock reading, weaken `MAX_AGE`, change the trusted peers, overwrite a partial create-only installation, or treat an unelevated failed resync as success. Genuine V4 code installation and selection, account inception/provider rights, and final PAPER production/Stop/browser/restart/soak all remain separate gated steps.
