# Atlas V4 consolidated code ? unselected native installation verified (2026-11-08)

**Result: INSTALLED + INDEPENDENTLY NATIVE-VERIFIED, UNSELECTED, NOT PAPER-ACTIVATED.** This is a genuine create-only source/dependency release milestone; it is not financial source acceptance, account inception, selector promotion, production PAPER Start, or an operational gate closure. Canonical financial launch acceptance remains **0/9**.

## Corrected host prerequisite

- The operator approved and executed `scripts/windows/Atlas-V4-Windows-Time-Poll-Cap.ps1 -ExecuteApproved` in a real elevated Windows PowerShell session. Windows reported `ATLAS_V4_WINDOWS_TIME_MAXPOLL_6_REQUESTED_CONFIG_READBACK_PASS` and explicitly did **not** grant Atlas install/activation authority.
- Independent readback from the authorized desktop found W32Time `MinPollInterval=6`, `MaxPollInterval=6`, and **both** pre-approved Google/Cloudflare peers reporting actual `PeerPoll Interval=6 (64s)` and `HostPoll Interval=6 (64s)`. No trusted NTP peers, financial clock thresholds, or registry setting other than the administrator-approved poll cap were intentionally changed.
- A real, no-provider, read-only single-instance clock lease preflight (`scripts.observation_runtime.atlas_v4_installer_clock_lease_preflight`) returned `CONTINUOUS_NATIVE_LEASE_PREFLIGHT_PASSED_NOT_INSTALLATION_AUTHORITY`, **35 real samples** across **181.3 seconds**, with an initial native uncertainty bound of **353ms**. This matched the earlier fixed 120-second maximum last-sync age and <=1000ms uncertainty policy without relaxing either.
- Existing clock and exact V4 installer source tests were rerun **after** the Windows setting changed: **193 passed, zero failures**.

## One exact approved create-only installation

- Pinned V4 code source commit: `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`.
- Pinned reviewed archive SHA-256: `3f366b14f85d6dfce990ff98ca2b573176e1a838b3054b957894b04a060f2855`.
- Pinned V4 proposal SHA-256: `43623d87993478fa89fb0ebfac5be3e2bd761f9cfe1185bab5139d17d0305869`.
- Proposal: `docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V4_2026-11-08.json`. Target was verified absent before execution; no existing partial directory, final receipt or pending journal was overwritten or repaired.
- The previously authorized installer was executed **once** via the existing `scripts.install_verified_release --execute-approved-unselected` guarded entry point. Start UTC `2026-11-08T12:58:34.9294478Z`, end UTC `2026-11-08T13:00:22.1421015Z`, elapsed approximately **107.2 seconds**, exit code **0**.
- Native release created at `D:\AtlasRuntime\releases\fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`.
- Durable private create-only receipt: `logs/diagnostics/qd-unselected-release-fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed.json`, SHA-256 `2b282dc6ee1dc84e9742f672b972e7ebd5809ba3fda073e7073be5f25d7eadd7`. Its schema is `ATLAS_QD_D_RUNTIME_INSTALLATION_V1`, stage `D_RUNTIME_LAYOUT_VERIFIED`, and it explicitly reports `selected=false`, `provider_connections=false`, `financial_effects=false`, `operational_acceptance=false`.
- Its native identity manifest lists **10,482 files** and **914 directories** with exact source commit, archive SHA, inventory digest and retained artifact digest `d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5`.

## Independent installed-process readback

- After installation completed, `scripts.install_verified_release.installed_readback()` was invoked **again**, separately, against the final retained receipt and its artifact digest. The installed Python `-I -B -S` isolated verifier reopened/rechecked the installed native identity, file hashes and directory inventory and returned **10,482 files**, **914 directories**, **0 retained verifier handles**. Independent readback **PASSED**.
- Retrying `installation_target()` against this exact release now correctly refuses `INSTALLATION_ALREADY_EXISTS_PRESERVE_NO_RETRY` before copying anything. The staged pending journal is intentionally preserved as immutable evidence, not automatically deleted.
- The selected immutable release is STILL `de437abe888a2d20746762a39402ae421417c1f6`, selector revision 8. Physical desktop `Project Atlas.lnk` and `Stop Atlas.lnk` still point to their original **observation-only** PowerShell scripts. No financial owner, provider, broker, PAPER positions, live adapters or startup process was touched.

## Next genuine dependencies

1. Review code-selection authority independently, but do not automatically promote this newly installed release or repoint shortcuts; selection is a **separate explicit decision**, and source-only installation does not confer trading authority.
2. Resolve actual Quality Dips and Hyperliquid native financial account inception, verified custody/ownership and approved data/source rights under the single-user PAPER roadmap. Kalshi newly listed simple YES/NO is a separate planned lane.
3. Preserve the consolidated **FINAL LAUNCH** for authenticated real PAPER Start/Stop, both-account flatness/receipt readback, reader/writer authorization, restart recovery, browser/listener tests and sustained soak. Formal gate acceptance remains **0/9** until those checks are genuinely completed.
