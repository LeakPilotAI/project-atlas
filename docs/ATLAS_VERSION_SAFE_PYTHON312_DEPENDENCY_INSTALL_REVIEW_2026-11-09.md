# Atlas version-safe candidate Python 3.12 dependency and guarded code-only installation review — November 9, 2026

**Result: verified nonfinancial planning evidence and a strictly NON-EXECUTABLE proposal. No new release was installed or selected; 0/9 financial PAPER prerequisites accepted, financial production NO-GO.**

## Frozen source and Python 3.12 dependency records

- Frozen new source candidate commit **`2d4879878bf58bea5a3ed0a986b809791f638fec`**. Its exact **1,008** tracked source files were reverified from `logs/diagnostics/atlas-version-safe-ntp-source-candidate-20261109-r12-proposal/atlas-source.zip`, SHA-256 **`5b295cc8e60be9d078321b39197afa4d12ad31897bc258575889099b3f5f7dac`**, sorted inventory SHA-256 **`22960eadfe5c6ca3e95b799788ba02cc702bd2db66ba14f61707380472ad7331`**.
- Reused existing D-runtime source commit **`fca29cfe7760a28d2569b8b4b91ed1ea99804c3c`** as an explicitly *verified dependency source*, not as a new candidate or installed executable. Historical source receipt `logs/diagnostics/qd-d-runtime-coordination-installation-20261028.json`, file SHA-256 **`b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0`**; full native receipt file-inventory digest **`93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`**.
- Extracted **9,566** independently inventoried Python files (including genuine Python 3.12 executable/DLL/stdlib), their normalized selected-inventory SHA-256 **`2eaa943a5fa35fe4863defd9bc843dd93503367509b56c4880a0aef3c1f9960f`**.
- `prepare_install_inputs(..., require_tracked=True)` returned a consistent no-collision future **10,574-file / 914-directory / 265,175,432-byte** code-only native installation plan; candidate destination `D:\\AtlasRuntime\\releases\\2d4879878bf58bea5a3ed0a986b809791f638fec` is absent, receipt/journal absent. This is a *proposed* plan, not a completed native installation.

## Real native dependency-source verification and limitation

- Original attempted installed-runtime self-verifier **refused** because the older D-runtime source image does not contain `personal_release_identity.py`. This check was not claimed as a pass or used to alter that image.
- Second check executed isolated `-I -B -S` Python from the **installed V8** image; it loaded V8's installed native release verifier and used its native-handle constructor to verify all **10,182 D-runtime source files**, **903 source directories**, original recorded native IDs, SHA-256 contents, and the complete source namespace. Outcome **passed**, with **zero file and directory handles remaining**, in 144.73 seconds. This was a cross-image *physical dependency-source* proof, **not** D-runtime self-execution/module-origin verification and not proof of a new candidate runtime.
- Exact native readback record: `logs/diagnostics/atlas-version-safe-source-dependency-physical-20261109.json`. Historical native V8 application/support receipt hashes remained unchanged; existing native selected V7 revision 11 predecessor head **`933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997`** preserved, `r0012.json` absent.

## New guarded, non-executable review proposal

- `docs/ATLAS_VERSION_SAFE_CODE_ONLY_INSTALL_PROPOSAL_R1_2026-11-09.json` (SHA-256 **`539d8619fc52ca724762b38d4675292a38a72a29df3a0a4aa531358d8f62aa36`**) binds the exact candidate archive/inventory, Python source receipt and 9,566-file inventory, physical source readback, native plan counts/bytes, old selector head, and current adapter source hashes.
- Proposal has its **own review-only schema**, `status=DESIGN_NOT_PERMISSION`, all native install, selection, PAPER account, provider, simulated/live trading and approval flags explicitly false. **The current native installer does not allowlist this candidate and rejects the proposal.** Do not attempt to execute this proposal with historical V7/V8 installer flags or reuse an older V8 receipt/installation path.
- New dedicated tamper tests plus historical install, candidate, version-safe clock and native planning tests: **108 passed, zero failed**. No paper or live order entered; no OS clock, startup, Genesis, VPS, private account, or desktop shortcut change.

## Next dependency

1. Implement and review a **separately pinned candidate-specific code-only installer** with the exact SHA-256 pins above, preserved historical V7/V8 allowlist behavior, create-only native destination and independent installed-Python readback.
2. Only after installer review and new tests, conduct fresh continuous **180-second Google+Cloudflare NTP** installation qualification and a separately authorized one-shot nonfinancial installation. Never patch or repair immutable V8 in place.
3. Review the installed candidate's support and separate native release-selection handoff without prematurely appending r12. Remaining real PAPER critical path: Alpaca IEX and Hyperliquid data/rights, separate simulated ledgers and risk, single-click Start/Stop, dashboard/Discord and supervised reliability soak.

**Source verification does not establish financial authority or profitability. Full PAPER remains 0/9 accepted financial operating prerequisites.**
