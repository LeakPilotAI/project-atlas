# Atlas V4 Hyperliquid public-base-fee offline correction — 2026-11-08

**Status: VERIFIED SOURCE-ONLY COST-POLICY REVIEW CANDIDATE; NOT ACCEPTED/INCEPTED/PAPER STARTED.** Existing V4 r9 installed selection and native support are unchanged. Formal nine-gate PAPER operational acceptance remains **0/9**.

## Reason and authoritative reference

- Official public Hyperliquid perpetual-futures **base fee tier 0**: **maker 0.015% (1.5 basis points per side)**, **taker 0.045% (4.5 basis points per side)**, as listed at <https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees> (reviewed 2026-11-08). The older *unapproved* Hyperliquid draft used **maker 1.0 bps and taker 2.0 bps**, likely understating standard-tier fees.
- These public rates are **not private user-fee authentication** or a universal maximum: actual discounts depend on activity/referrals/staking, and certain products/add-ons may have further fee adjustments. No private Hyperliquid address, account, exchange order or wallet was accessed.
- Illustration: two $100 taker-side transactions incur **$0.04** in fees at previous provisional rate vs **$0.09** at the published base rate, before spread, slippage, funding or any extra charges. Successful simulations must not mistake the older fee assumption for a validated realized cost.

## Exact immutable reviewed artifacts and binding

- Original V4 draft **retained byte-for-byte**: `docs/ATLAS_TWO_ACCOUNT_V4_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json`, SHA-256 `fd40c907ee6f62a1eabff4d347c1ca17c4438c8ddd3e226bc92d69db8290fbd1`.
- New distinct, create-only offline proposal: `docs/ATLAS_TWO_ACCOUNT_V4_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json`, SHA-256 `8379c100d2fe1dc67a11d91d83002694f16925895680786aa0885d6487e9a53b`, status `V4_PUBLIC_BASE_PERPS_FEES_REVIEW_ONLY_NOT_ACCEPTED_OR_AUTHORIZED`.
- Remains bound to installed selected V4 artifact `d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5`, commit `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed` and selector revision 9.
- Exactly two changed financial-assumption strings within the **Hyperliquid** account's `perp_policy`: `maker_bps: "1.5"`, `taker_bps: "4.5"`. The associated native enrollment `policy_digest`, `inception_digest`, account `parameters_digest`, and FS3 report-scope `policy_digest` were recalculated against the new manifest. New HL policy digest `7f2b2f3d5a8c0508eff64f970551fdeea9bfba9136709c95df810af953afd2b4`; new manifest digest `93d4ded6f4027275dd62aa58c07d77be9ffb76c3c8a64fb841eafdb26d214073`.
- The **entire Quality Dips account proposal** (simulated USD 1,000, original root identities and report bindings) remains identical; Hyperliquid remains distinct simulated 1,000 USDC with the same 6 native root IDs/paths and epoch string. Neither account was incepted, nor was any resource changed or adopted.
- Crucial: `fee_schedule_id=PENDING_E1_VERIFIED_FEE_SCHEDULE`, `instrument_cut=PENDING_E1_VERIFIED_INSTRUMENT_CUT`, `market_source=PENDING_E1_VERIFIED_BOOK_SOURCE`, and `funding_source=PENDING_E1_VERIFIED_FUNDING_SOURCE` remain **pending**. The exact `provenance` schema token is a structural contract, **not** actual acceptance. Both full native enrollment validators correctly refused the source-only drafts because real writer process identities and accepted operator ID are missing.
- All authority flags remain **false**: no acceptance, no provider-check grant derived from the proposal, no account inception, no PAPER startup, no live orders.

## Regression and next dependency

- New tests: `tests/test_atlas_v4_public_base_fee_offline_draft.py` verify both proposal SHAs, unchanged QD lane, exact V4 artifact binding, six false authorization flags, recalculated native/report digests, account enrollment refusal, E1 placeholders and USDC fee accounting.
- Focused offline regression `test_atlas_v4_public_base_fee_offline_draft.py`, existing V4 two-account draft integrity, personal inception, personal native financial authority and personal Stop account scope: **48 passed, zero failed** (all under protected Atlas D: diagnostics).
- **Next:** operator or policy decision on published base-rate assumption and whether other fees must be modeled; then independently verified E1 usable BTC/ETH/SOL bid/ask/mark/funding settlement, genuine accepted source and writer ownership, review of the exact epoch adoption, real initial-clock authority, native once-only simulated account inception, desktop Start/Stop certification and soak. The previously approved 7/7 Hyperliquid diagnostic request budget remains **exhausted**, never reset or bypassed.
- No additional provider request, no production account/financial file, no forced kill, no real-money order, no desktop shortcut rewiring, no Genesis, no VPS and no Windows boot startup.
