# Atlas R14 game-safe native install host admission (2026-11-10)

## Outcome

**SOURCE-ONLY GUARD IMPLEMENTED; NATIVE INSTALL NOT AUTHORIZED OR STARTED.** A new bounded Win32-only resource admission prevents a future heavy R14 code-only native installation from beginning while the user's NBA 2K27 game is running, or when free RAM/disk falls below conservative minimums. This is a host responsiveness safeguard; it is **not** a financial/PAPER/market provider gate. Normal future PAPER operation and gaming may coexist subject to ordinary system resource constraints.

The previously authorized R13 install reached native post-copy readback but hit its bounded 500s low-impact limit; its partial destination and refusal journal remain preserved. The separate R14 source archive exists, and its new native destination remains unused.

## Exact implementation

- New `scripts/observation_runtime/native_install_host_admission.py` reads a single Windows `CreateToolhelp32Snapshot` / `Process32FirstW` / `Process32NextW` snapshot (maximum 4,096 process entries), Win32 `GlobalMemoryStatusEx` free physical RAM and `shutil.disk_usage` for exactly `D:\AtlasRuntime\releases`. It uses **no external dependency, subprocess, task scheduler, persistent watcher, process modification, shell query, antivirus scan or network connection**.
- An exact-case-insensitive executable basename match on `NBA2K27.exe` refuses with `NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY`. **Other games are not guaranteed to be detected.** This is specifically scoped to the currently established known user game, rather than making unsupported claims of general game detection.
- Required admission headroom: **at least 8 GiB available physical RAM and 4 GiB free space** on the release volume. Unknown/malformed/over-limit resource evidence, Win32 snapshot/API failures or the wrong release parent cause refusal rather than assuming the machine is idle.
- The `scripts/atlas_r14_low_impact_installer.py::install()` sequence now checks fresh resource evidence **after exact one-shot consent and before** spending 180 monotonic seconds on NTP qualification; it checks again after clock qualification. During any subsequently authorized copy, `_native_admission()` still checks the 500-second deadline on every I/O budget tick, independent NTP on the first, every 32 and at most one second apart, Windows IDLE priority and original R12 selector on every 32, **and RAM/disk/game headroom at most 10 seconds apart** (also on first admission). A lost headroom/game-start triggers fail-closed partial preservation; **never retry an occupied path**.
- This gate is **not** applied to read-only `inspect()`, regular Atlas observation/PAPER operations, the local Git repository or the Windows boot process.
- R14 retains `APPROVAL_SHA256=None`, no executable install CLI, and no consent, selected-release, finance, provider/account, PAPER or live authority. Fresh R14 explicit one-shot approval and native acceptance remain separate requirements.

## Live lightweight observation and verification

At this checkpoint, read-only Windows process sampling detected roughly **130 process entries**, including `nba2k27.exe` while the game was running. Free physical RAM was roughly **93.5 GiB** and disk roughly **754.67 GiB**; **the game-active refusal correctly fired anyway**. That validates the native basename detection path without any 263MB native copy or gaming interruption. Live game activity is dynamic; this is a contemporaneous observation, not a claim about future system state.

Single Windows IDLE-priority pytest runner checked `tests/test_native_install_host_admission.py`, `tests/test_atlas_r14_low_impact_installer.py`, and `tests/test_atlas_r13_low_impact_installer.py`: **68 passed, 0 failed/skipped in 3.44s**. Cases include available-resource admission, case-insensitive game conflict, missing RAM/disk, invalid evidence, wrong release root, actual Windows process snapshot, refusal before any clock/source/native I/O, resource rechecks when a game starts mid-copy, and unchanged R14/R13 clock, selector, consent, failure journal and readback guards. All native install operations in tests were synthetic and disposable.

## Readiness and remaining work

R14 frozen source ZIP: `logs/diagnostics/atlas-r14-source-only-20261110-r01/atlas-source.zip`, SHA-256 `22e4d00cb61c56d0b298c059e597937696df8deeca25c7ec6b38ec5ff01e192a`. The workspace-side installer now imports this new resource guard, so its **updated exact adapter/helper hashes must be independently reviewed and re-pinned before any one-time operator install authorization**. The R14 source ZIP has not been modified to include this external orchestration helper; do not claim the two are the same release artifact.

R14 proposed native release path `D:\AtlasRuntime\releases\7ff9d3dba2eabe110f843c13efac49464805de2a` must still be empty, and existing R12 selector hash `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7` must be preserved. The occupied failed R13 location is not eligible for retry. No GitHub push, provider connection, market data/account access, trading, cleanup, Project Genesis, Windows time/boot changes or bulk copy has occurred.

**Formal financial PAPER remains NO-GO, 0/9 independently accepted operating gates.** Even a successful future code-only installation would not activate financial engines; independent release selection, source/provider eligibility, actual supervised PAPER session and months of result evidence are still required.
