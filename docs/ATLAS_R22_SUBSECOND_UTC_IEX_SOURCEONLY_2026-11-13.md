# Atlas R22 source-only authenticated sub-second UTC and market-data proof
Date: November 13, 2026
Main project: D:\Work\Project Atlas
Production selected release remains original immutable R21 revision 20 (`119dd8626da32e74bd7f86db9de1c1a8fd2c20ac`).

## Root cause and actual market-open evidence

Two real, selected R21 original Windows-Job-bound Alpaca IEX `quotes/latest` data-only checks succeeded against MSFT, AVGO, SCHD and VTI after 8:30 AM Central (4/4 bid+ask each). Strict freshness was only 2/4 and 1/4. Some genuine provider timestamps appeared in the future of Atlas's **integer-floored** original NTP sample (`source_age_seconds=-1`), even though Atlas's dual-peer NTP UTC calculation already contains sub-second detail. This is a real conservative timestamp quantization ambiguity, **not proof of stale data and not permission to override the original financial gates**.

## Source-only code change

Updated:
- `scripts/observation_runtime/atlas_independent_ntp_clock.py`: original same-process independently NTP-monotonic-anchored `sample_precise()` and `verify_precise()` with schema `ATLAS_INDEPENDENT_PRECISE_UTC_V1`, nanosecond UTC, original monotonic timestamp, original measured uncertainty, original source marker, exact one-second bounded issuance cache, revocation and no Windows wall time. The former whole-second sample and all previous callers remain unchanged.
- `scripts/observation_runtime/personal_version_safe_release_clock.py`: new original selected-native `sample_precise()/verify_precise()` delegates only after original exact running process, selected release, runtime identity, peer-NTP and original ownership checks. Any revoked/reselected clock refuses.
- `scripts/observation_runtime/atlas_r20_native_iex_latest_readonly.py`: the original Job-owned authenticated HTTPS data-only request now **requires** exact same-process verified high-precision clock after each GET. Provider event is demonstrably before receipt only when `observed_utc_ns - provider_timestamp_ns >= verified_NTP_uncertainty_ms * 1e6`. Conservative upper age `age_ns + uncertainty_ns` must be <= 5 seconds; ambiguous or future-looking provider time is still REFUSED. Sanitized research-only reports `utc_clock_sample_quantization_seconds=0` and `provider_event_proven_before_sample`; no raw prices/secrets, no SIP/NBBO claim, and all financial-source, PAPER, live, inception and provider-rights approvals stay FALSE.
- `scripts/observation_runtime/atlas_r22_precise_live_ntp_readonly.py`: standalone genuine dual-NTP source-only read-only probe; does not use exchange credentials, access trading APIs, install/select code or write financial roots.

## Executed verification

Focused regression including exact clock wrapper, source-only IEX, NTP and malformed/synthetic/future timestamps: **165 passed**; Ruff clean. Broader selected native source, original QD issuer and activation, HL funding and ownership suite: **577 passed, 1 skipped**, no failure. The two obsolete R14/R15 historical release-history-only suites are NOT suitable for the present original selector: their fixtures demand 13/14 historical records and now refuse against actual native revision 20; these were excluded without tampering with selected-native immutable history or weakening the tests. Earlier full executed selected R21 original-native first two in-process market-open IEX probes are archived separately.

Real external source-only NTP qualification executed using Windows desktop and original two public NTP peers (Google/Cloudflare), without financial accounts or any market data:
- `REAL_TWO_PEER_PRECISE_UTC_SOURCEONLY_VERIFIED`
- two genuine NTP sources, original peer difference **1 ms**, original conservative bound **139 ms**
- issued precise subsecond UTC verified, observed a nonzero nanosecond fraction
- legacy original whole-second public clock remains verifiable; `financial_authority=false`
- original source-only evidence receipt at `logs/diagnostics/atlas-r22-sourceonly-real-subsecond-ntp-20261113.json`, SHA256 `d9ddeb1705f53afed11406911f38454f3ca578b06bb0755273c4360c13c4286c`

## Operational safety and remaining PAPER requirements

**This R22 improvement is currently a workspace SOURCE-ONLY change and is NOT part of selected R21.** A distinct audited immutable code-only release package, native Windows installation, selection, original Job and provider checks would be required before active original R21-dependent diagnostics can use it. Do not copy or patch the immutable R21 installation.

Nothing here grants current QD firm-originating multi-source valuation issuer, accepted provider rights, legitimate original source epoch rollover or post-inception native activation, Hyperliquid independently signed historical consensus settlement-time oracle/account fee proof, pre-inception two coordination journals, FS1/FS3 USD+USDC two simulated account inceptions, financial Stop-first authorization or read-only dashboard/Discord acceptance. Original twelve native financial root namespaces are still empty, paper financial trades disabled and live capital disabled.

Store source/test/docs/diagnostic/temp only within D:\Work\Project Atlas. Preserve immutable original D:\AtlasRuntime, D:\AtlasCustody, D:\AtlasPaper historical resource identities. Run Atlas-specific verified Windows temp cleanup at end. No VPS, no purchased provider data, no options/futures, no live trading.
