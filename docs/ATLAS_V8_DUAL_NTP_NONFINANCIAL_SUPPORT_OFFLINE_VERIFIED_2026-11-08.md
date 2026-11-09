# Atlas V8 dual-NTP nonfinancial native support review — 2026-11-08

**Outcome: V8 nonfinancial support source and ZIP successfully constructed and verified. NOT YET NATIVE SUPPORT INSTALLED. V7 r11 remains selected. PAPER financial NO-GO (0 of 9 accepted QD/HL prerequisites).**

## Actual installed V8 source binding

- Native V8 installed application: `D:\AtlasRuntime\releases\c8cc4846508b29483d10a0b4c4353f8a26f1fc9c`, source `c8cc4846508b29483d10a0b4c4353f8a26f1fc9c`, artifact SHA-256 `65c4b4661ec6aef7359e9dae716a416327379f5082a5b309ccdb5a148a569c95`, durable installed application receipt SHA-256 `ecb94e00e262e371caea494b1cc552352c892fa437a3b5f4946b54f7f863ae34`. Actual installed V8 has 10,562 native file records and 914 directory records from previously successful independent readback.
- `scripts/support_deployment.py` now recognizes **only the exact V8 app source, receipt and artifact hash** for the same independent Google/Cloudflare NTP nonfinancial code-selection clock profile previously limited to V7. It requires the exact installed NTP source SHA `230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c` and V8's installed operator-clock source SHA `ded15bde4e2b3ce845b2eaf95818b6c81fb3b759daf2b9375a68533710599e8d`, never a caller-written version string alone.
- `scripts/build_support_deployment.py` now permits the exact already-installed V8 (alongside historical V7) only with matching native application receipt/artifact and real NTP/operator source hashes, preserving older Windows-clock releases. It retains the original support namespace/exclusions, no financial startup, no provider writes and no automatic boot/startup.
- `support_deployment.select_release` now explicitly refuses V8 with `V8_SELECTION_CLOCK_HANDOFF_NOT_CERTIFIED` **before native receipt, support lease or selector mutation**. Selecting V8 is unsafe until a separately reviewed clock/selector handoff exists, because frozen V8 operator clock `NativeV7PaperOperatorClock` still pins selected V7 r11 exactly. No r12 selection record was created.

## Create-only V8 offline native support package

- Built independently from the actual V8 installed receipt and the prior native V7 support parent file identities (original native `launchers`, `selection`, `support-installations` IDs retained):
  `logs/diagnostics/atlas-v8-ntp-support-offline-proposal-20261108-r11/`.
- Native support manifest: `deployment.json`, exact SHA-256 **`13fbcf6b90cf1c2e6f5aa74aa60a057f6865d52097916db4d6e03669275eab86`**.
- Create-only support archive: `support-source.zip`, SHA-256 **`77ed856d98f0fec39cc45280c35299c38147014aae933adbf6e5f7f3e0dae76d`**. Exact **10 source files**, **17 bound required installed application files**, all application, native ID, package and clock source pins checked using `support_deployment.prepare`. Native support destination/control both absent when built. Support manifest explicitly `installation_authorized=false`, `promotion_authorized=false`, `financial_startup_authorized=false`, `providers_authorized=false`, `status=REVIEW_INVENTORY_NOT_PERMISSION`.
- Existing historical V7 support/selection dependencies tested, **54 passed, 1 skipped**, V8-specific support/selection refusal/native-support contract tests **63 passed, 9 skipped**, final broader source + financial-authority, NTP, V7 and V8 release compatibility regression **376 passed, 9 skipped, zero failed**. The skipped native test cases require an explicitly configured disposable Windows fixture and were not counted as native V8 installation acceptance.

## Verified operational bootstrapping blocker (read-only actual installed V8)

A separate actual isolated `D:\AtlasRuntime\releases\c8cc4846...\python\python.exe -I -B -S` process imported **only** the frozen installed V8 application's existing `scripts.support_deployment` implementation and examined this new V8 support manifest. As expected, it returned **`WINDOWS_TIME_CODE_SELECTION_V1`** because that frozen module predates the new exact V8 NTP support allowlist. It does not have the approved V8-specific support deployment logic; **do not use that old installed `-m scripts.support_deployment` entrypoint to install or select V8**.

The next milestone is an independently reviewed no-workspace-application-fallback **V8 native support installer bootstrap** that uses V8's installed Python 3.12 interpreter and verifies the exact current support adapter bytes/manifest/archive, native root identities, no existing support targets and an actual independent NTP clock, then invokes at most one create-only native support operation with independent readback and ACK. No selector r12 or financial session may be created. Only then review a separate V8 version-safe clock/selector cutover.

No changes to native selected V7 r11, private brokerage/wallet, simulated account balances, financial writers, actual orders, Project Genesis, OS Time settings, VPS, desktop shortcuts or automatic Windows startup.
