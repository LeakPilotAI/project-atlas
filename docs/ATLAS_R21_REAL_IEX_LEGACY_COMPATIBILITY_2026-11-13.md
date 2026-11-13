# Atlas — R21 genuine market-data recovery and financial admission boundary
Date: Friday, November 13, 2026
Single project root: D:\Work\Project Atlas

## Executed result

The actual installed and selected R21 source release `119dd8626da32e74bd7f86db9de1c1a8fd2c20ac`, native selector revision 20, runs the original `atlas_selected_original_selfjob_structural_readonly.py` under its own Windows Job and NTP clock. It intentionally imports the newer **workspace source-only** IEX diagnostic `atlas_r20_native_iex_latest_readonly.py` by exact path. The newer diagnostic recently required `clock.sample_precise()`, which exists only in uninstalled R22 workspace code. The selected immutable R21 original native clock has `sample()` with the complete original `QD_AUTO_NATIVE_CLOCK_V4` issuance envelope and `clock.verify()`, not the new precise interface.

**Actual failure reproduced:** original selected R21 Job-bound IEX probe crashed with `AttributeError: NativeVersionSafePaperOperatorClock object has no attribute sample_precise`; a subsequent first compatibility check correctly refused `IEX_NATIVE_SELECTED_R21_UTC_VERIFICATION_REFUSED` because the original sample has *five authenticated fields* (schema, utc, monotonic_ns, uncertainty_ms, source), not a synthetic two-field sample. No account files, provider order APIs or LIVE execution were used.

**Verified fix:** the workspace IEX adapter now requires exact authenticated same-process native precise UTC when the installed selected clock genuinely offers it. Only if the current selected original native release is **exactly R21 source** `119dd8626da32e74bd7f86db9de1c1a8fd2c20ac` with exact artifact `02c5705e586f92415612c70309bd7051ad76629278f6c22905b056558b602b27`, and only when the original clock has neither precise issuance nor precise verification, the adapter accepts the original complete `QD_AUTO_NATIVE_CLOCK_V4` five-field UTC seconds sample with a real `clock.verify` check. Legacy quote timestamps remain conservatively quantized to one second plus NTP uncertainty, and even an event timestamp at the zero-age/uncertainty boundary is refused for freshness. For all other selected releases a missing, forged, partial, unissued or altered precise-clock interface is a hard refusal.

**Genuine selected R21 data-only retest PASSED** after the fix: status `REAL_R21_DATA_ONLY_OBSERVATION_VERIFIED`, 4 original authenticated Alpaca IEX HTTPS GETs, **2 fresh quotes**, exactly four original **whole-second-precision** clock samples; `paper_start_authorized=false`, `live_trading_authorized=false`. The credential source and original Windows Job remained pinned; raw stock prices, private credentials and broker order endpoints were never exposed or used. The real test ran with actual selected R21 Python and original installed modules, not synthetic test-owned financial authorities.

## Actual safety and remaining financial status

- Focused source, independent NTP, original R21 legacy compatibility, selected clock and adversarial source tests: **171 passed, Ruff clean**.
- Original native selection rev 20 and all 12 original finance root identities remain intact. **12/12 original account root namespaces still empty**; no original FS1/FS3 account inceptions or financial PAPER writer leases were published.
- The original financial commissioning preflight returns `BLOCKED` (exit 2 by design). Legacy independent 9-gate desktop checker is a **permanent NO_GO veto**, not a dynamic progress percentage.
- The prior operator document `docs/PERSONAL_PAPER_OPERATOR_ACK_2026-10-25.json` expressly sets `operational_financial_inception_authorized=false`, `provider_connection_authorized=false`, `paper_startup_authorized=false`. The local V4 operator file is **native tests only**, while the required V5 independently approved financial scope is absent. Do not adopt the historical unapproved V5 enrollment draft, mint a signature from the user's general conversation request, or create partial original coordination journals.
- The source-only R22 high-precision UTC code and pinned archive are available inside the main project but **NOT installed or selected**. This R21-safe source-only adapter compatibility correction follows that frozen bundle; do not claim it is part of installed R21 or the earlier R22 archive.
- Original QUALITY_DIPS financial admission still needs accepted live operational issuer and genuinely originating valuation evidence/approved market-data rights. The selected SEC-only WATCH issuer cannot trade. Hyperliquid original historical consensus funding oracle, account fee evidence and rights remain independently unverified; public hourly `fundingHistory` is not signed settlement-time oracle evidence.
- Only after exact independent one-time account/operator source approvals and actual original source acceptance can original 2 native coordination journals, independent READ_ONLY+INITIALIZE_SIMULATED_ACCOUNTS activation, FS1/FS3 $1,000 USD + 1,000 USDC inceptions, post-inception CONNECT_APPROVED_DATA and distinct AUTO_PAPER+SHUTDOWN_FLATTEN scopes be accepted, followed by genuine Stop-first financial run.

**Therefore: market observation is working, not full PAPER trading.** Preserve fail-closed desktop Start and do not enable any live-money connection or create unauthorized financial files.

## Storage/cleanup

All new code, unit tests and this report are in `D:\Work\Project Atlas`. No additional project root, paid feed, VPS or Windows-startup task. Preserve installed R21 and original identity-bound `D:\AtlasRuntime`, `D:\AtlasCustody` and `D:\AtlasPaper`; finish with `Atlas-Post-Execution-Temp-Cleanup.ps1 -ExecuteVerified`, leaving original native audit evidence untouched.
