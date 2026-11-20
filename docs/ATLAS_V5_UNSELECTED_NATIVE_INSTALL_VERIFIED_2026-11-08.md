# Atlas V5 Hyperliquid funding-fix release — native installation and independent readback verified (2026-11-08)

**Actual result: NATIVE CODE INSTALLED + INDEPENDENTLY VERIFIED, UNSELECTED, NO FINANCIAL OR PAPER START.** Canonical full PAPER operational acceptance remains **0/9**. This verified success supersedes the *temporary clock block* recorded earlier in `docs/ATLAS_V5_NATIVE_CLOCK_GATE_BLOCKED_2026-11-08.md`; that historical refusal and the later successful qualification are both preserved.

## Exact release and installer evidence

- Frozen source commit `247a4f4e1d78594cdb55ef55f185ef37921bf535`, including the bounded Hyperliquid public hourly-funding timestamp compatibility fix.
- Exact selected source inventory digest `ff8635bd4f246f49234036b8aad56d9483147bb5cbba28f20f7970aebc47985c`, source archive `logs/diagnostics/atlas-funding-v5-source-candidate-20261108/atlas-source.zip`, archive SHA-256 `35c5b6b623f197f085cbe40bc0ff9e0d16672d5b5c3557ad48eb47e4bc20b437`; independently verified 957 tracked selected source inputs.
- Reviewed single-use native installer proposal `docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V5_R1_2026-11-08.json`, SHA-256 `e783bce33d6ef5a235d5ae2b07c59c38a847de9bb07d0560e2f8a602ddbd07db`. It sets selected, financial enrollment, provider activation, PAPER startup and promotion **all false**.
- CLI exact allowlist V5 R1 routing and strict archive/source/inventory pin checks passed focused regression. Verified adapter source digest for the updated guarded installer `81f890b9424eb282ad7d1c5d5d2a135b0b8e87690f8e28467118c5b6ace4cba8`.
- Native dependency receipt/inventory digest `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91` previously independently verified. Installation plan expected 957 selected source files plus 9,566 native Python/runtime dependency files, 10,523 total.

## Authentic native clock qualification

- First genuine 180-second continuous native clock preflight refused at about 116.52 seconds due to an accepted clock anchor revocation, while Windows Time reported stale sync and `Last Sync Error=2`. One attempted non-elevated `w32tm /resync` was denied with Access denied `0x80070005`. No clock policy was relaxed and no installer was started following that refusal.
- Independently probed both Google and Cloudflare NTP peers with native read-only stripchart; all three samples from each succeeded. Windows Time **later recovered autonomously**, reporting `Last Sync Error=0` with fresh successful synchronization; no administrator intervention, NTP peer reconfiguration or 120-second/1,000-ms safety threshold adjustment was performed by this session.
- Started a **brand new** actual single-instance `scripts.observation_runtime.atlas_v4_installer_clock_lease_preflight` (unaltered). It **PASSED** `CONTINUOUS_NATIVE_LEASE_PREFLIGHT_PASSED_NOT_INSTALLATION_AUTHORITY`: **35 real samples**, elapsed **181.21 seconds**, native initial uncertainty **584 ms**. This was real source-qualified Windows clock evidence, not a synthetic fixture, a shortened run or revival of the earlier revoked lease.

## Exact one-time create-only installation

- Only after the new full lease passed, executed the existing guarded `scripts.install_verified_release --execute-approved-unselected --proposal docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V5_R1_2026-11-08.json --proposal-sha256 e783bce33d6ef5a235d5ae2b07c59c38a847de9bb07d0560e2f8a602ddbd07db`.
- **Actual command exit code 0**, end-to-end native copy/verification process duration **114.33 seconds**. No retry, manual copy, upgrade in place, deleted evidence or force-promotion.
- Fresh native release created at `D:\AtlasRuntime\releases\247a4f4e1d78594cdb55ef55f185ef37921bf535`. Create-only retained final receipt `logs/diagnostics/qd-unselected-release-247a4f4e1d78594cdb55ef55f185ef37921bf535.json`, SHA-256 **`f6c359e3f216e1ef513aba3ce9d5d80ec3cb2bf170fe7aa604640bbc6a474cf8`**.
- Receipt schema `ATLAS_QD_D_RUNTIME_INSTALLATION_V1`, stage `D_RUNTIME_LAYOUT_VERIFIED`; verified **10,523 files** and **914 directories**, source commit/archive/inventory hashes and frozen installed artifact digest **`5f5940fdc1e0dbc2cdda7def83b8b138dce3d868655012a34db8e59565832879`**.
- The returned receipt explicitly records `selected=false`, `financial_effects=false`, `provider_connections=false` and `operational_acceptance=false`.
- **Independent second process** reopened this exact retained receipt and spawned isolated installed-native Python via `scripts.install_verified_release.installed_readback`. It verified all **10,523 native files**, **914 directories**, matching child PID/creation FILETIME/image identity and installed layout; **0 retained handles**. Independently confirmed process completed with exit code 0.
- Native selector `D:\AtlasRuntime\selection\r0009.json` checked before and immediately after installation: revision **9**, selected prior V4 release `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`. No V5 selection, startup, financial account publication, order, provider request or desktop shortcut modification.

## Tests and actual next blockers

- Installer CLI exact admission, proposal hashes, refusal-before-clock and native installation plan/offline clock regression: **89 passed, zero failed**. Separate previous release source installation plan + selection tests: **100 passed, 8 skipped, zero failed**. Independent native installation/readback is a **separate genuine result**, not inferred from passing tests.
- Older V4 support installation remains bound to V4. **Next: prepare a V5-specific nonfinancial support/launcher package and independent selected-release readiness decision, then require a separate actual selection/admission check**; never reuse V4 support as if it were automatically V5-compatible.
- The previous simulated Quality Dips and Hyperliquid enrollment proposals are still bound to the **V4 artifact digest**; they do not become V5 accounts by installing a code-only release. The new V5 installed artifact digest must be intentionally re-pinned in new distinct review-only account proposals, and real account owners/writers, inception and financial rights are still absent.
- Provider E1 still incomplete (weekend IEX authenticated but zero accepted quotes; Hyperliquid BTC public-book partial evidence, ETH and BTC funding refused; previous 7/7 dedicated request budget exhausted; true funding settlement/oracle and accepted fee schedule missing). Native account commissioning, single-user real PAPER owned Start/Stop/flatten, recovery/reader/browser and sustained soak remain final-launch gates.
- **No live trading, private wallet/account access, simulated financial trades, Project Genesis changes, VPS, Windows boot startup or shortcut rewiring.** This release is installed **but not selected**, and does not itself grant months-ready full PAPER operation.
