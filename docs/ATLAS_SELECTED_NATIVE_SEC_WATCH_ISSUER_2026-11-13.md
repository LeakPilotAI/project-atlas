# Atlas — original-native SEC-corroborated Quality Dips WATCH issuer (2026-11-13)

## Why this is needed

The existing `QualityDipsCurrentProducer` requires an `input_authority.verify_current(context, now)` proof with schema `QD_CURRENT_RESEARCH_VERIFIED_V1`. Before this change, **no actual local operator-owned issuer class existed** outside test fixtures. A local digest, syndicated analyst list, secondary market data receipt, SEC filing date or installed original Job by itself cannot grant authority for executable Quality Dips research. There were also two separate initial root stages and no production account readback.

**This execution implements one deliberately non-executable subset of that missing original issuer**. Source-only under selected original R20 Python, but not yet installed/selected or called by a real financial owner. It is not a substitute for the full originating-analyst fair-value issuer or real quote rights.

## New original-native-bound watch-only issuer

New file: `scripts/observation_runtime/personal_selected_qd_sec_watch_issuer.py`.

`NativeSelectedQualityDipsSecWatchIssuer` is instantiated **only** from these exact original class instances:

- `RetainedSelectedNativeOwnerPreflight` with phase `INITIAL_READBACK_ONLY` (after two genuine native account FS1/FS3 readbacks), a still-held original Windows Job/process and exact 5+7 writer roles for the two accounts.
- `NativePersonalOperatorAuthority` with the **existing distinct post-inception** activation action `CONNECT_APPROVED_DATA`, the same original QD account and both original account digest bindings. It cannot mint its own operator activation or simulate financial inception.
- `NativeVersionSafePaperOperatorClock`, the original current independently selected release verified at every check, and `NativePersonalResearchArchive` bound to the same clock, original account, release and protected root/native ACK. On a clock/release/owner/activation change it refuses, never retries a financial lease.
- Original `qd_sec_original_quarter_replay.inspect_original_quarter` direct-cached verifier: it rechecks SEC submissions/10-Q, original inline-XBRL, SEC Company Facts, accession, quarter, EPS and diluted-share agreement, and exact cryptographic raw-source cache receipts for **MSFT** and **AVGO**. Those cached files must be from a previously successful first-party TLS acquisition and within seven days. The user cannot supply a fabricated issuer receipt via JSON as a substitute for recomputation.

For each current operational input, the issuer insists on exact `QD_CURRENT_RESEARCH_INPUT_V1` shape, original source identity, current 30-second observation, independently reconstructed SEC-quarter result, authenticated ranking metadata, original projected **WATCH** status, and unchanged per-symbol forward observations. It allows at most MSFT + AVGO and explicitly rejects ETF/unknown symbols (ETF share portfolios do not have company SEC 10-Q earnings facts).

**NO ENTRY:** It refuses any executable `instruments`, `quotes` or `monitors`; any `valuation_sources` or `normalization_sources`; a non-WATCH patient state; expired/future ranking; missing/altered SEC first-party receipts; or changed input/provenance. The resulting receipt is bound to the exact context, original account/source identity, original activation, independent SEC digest and original timestamp, but advertises `no_entry_only=true`, `independent_equity_valuation_accepted=false`, `executable_market_quote_accepted=false`, `financial_paper_startup_authorized=false`, `live_trading_authorized=false`.

The existing `QualityDipsCurrentProducer` and original immutable native source archive accept the type of research input only after the independently supplied publisher and archive authorities also verify the complete source and timestamp. No existing original code was modified or weakened by the new issuer. No user-invented fair values, stale market quote, source rights flag, paper fill or private account are signed by the issuer.

## Executed verification

**Actual original cached SEC recheck on November 13, 2026 at 09:50:45 UTC**, run with the selected installed R20 Python interpreter and original workspace parsing:

| Symbol | Original filing | Outcome |
|---|---|---|
| MSFT | accession `0001193125-26-436133`, filed October 28, 2026 | Original 10-Q and SEC Company Facts agreed |
| AVGO | accession `0001730168-26-000080`, filed September 10, 2026 | Original 10-Q and SEC Company Facts agreed |

Both original routines still reported `operational_source_accepted=false`, as required. They do not prove three distinct current independently authenticated equity valuation issuers, share split/basis history or market-data rights.

**Disposable tests:** `tests/test_personal_selected_qd_sec_watch_issuer.py` exercises exact selected-native class/type/clock/owner/operator and release guards under clearly marked **synthetic native objects** (not live Windows financial authority). It verifies no-entry-only proof, SEC original source rechecking per symbol, forged/missing SEC evidence, fake analyst fair values, fake quotes/instruments/monitor data, stale/future ranking and observation times, altered operator activation, revoked selected Job/clock, denied release, replay/rollback, and a full synthetic original source publication -> native in-memory ACK/readback with zero trade bundles and zero duplicate re-publications.

This is source-only software. The positive tests are only synthetic; they do NOT prove real original Job/account/activation or genuine 3-source fair values. The real SEC standalone recheck provides independent original data evidence but is not connected to a native PAPER account. Broader regression/check results are recorded in the final checkpoint.

## Required next integration

1. **Install an audited successor as immutable code** before the new issuer could exist in native selected R20. Do not select a release and imply financial readiness simply from this source-only patch.
2. Finish accepting original provider personal-use rights and genuine execution quote feed for the QD watchlist (Alpaca Basic IEX is single exchange with a 30-symbol limit, not SIP/NBBO).
3. For **executable** Quality Dips entries, implement separate independently authenticated 3-originating-firm current fair-value issuer or explicitly approve a different conservative valuation methodology with full forward-validation and risk review. SEC original EPS is not an analyst price target. Unchecked syndicated firm names are not independent issuers. This new WATCH issuer categorically cannot authorize entry.
4. Commission the two original financial accounts in the correct original native order: fresh source policy; original two initial coordination journals; exact pre-inception activation for READ_ONLY+INITIALIZE_SIMULATED_ACCOUNTS; native FS1/FS3 inception ACKs; **different** CONNECT_APPROVED_DATA operator activation; genuine QD source genesis and issuer; then Stop-first PAPER financial session acceptance.
5. Complete the original immutable multi-epoch QD source rollover, actual original financial reader re-enrollment/Stop ownership and crash-safe source high-water; current archive still supports only 127 publications after genesis (63.5 minutes at 30-second cadence).
6. Verify Hyperliquid native historical consensus oracle/fee rights from a genuinely permitted free source; official public fundingHistory lacks original signed historical settlement-price actions, and Hyperliquid's raw historical S3 archive charges the requester. Do not substitute current mark/candle.

**Result:** a native-bound, local SEC-only **no-entry** issuer contract now exists in source and can be wired after real account/activation acceptance. It deliberately does **not** unblock financial PAPER, price/valuation rights, historical Hyperliquid oracle or 0/9 original financial operating gates. Live orders remain prohibited.

Storage: new code, tests and docs only under `D:\Work\Project Atlas`; no C: project storage; do not delete historical untracked user artifacts; leave original `D:\AtlasRuntime`, `D:\AtlasCustody`, `D:\AtlasPaper` identity-bound roots untouched. Run selective `Atlas-Post-Execution-Temp-Cleanup.ps1 -ExecuteVerified` on completion.

## Exact safety-test additions

The operator/SEC watch issuer tests were extended to exercise its exact integration into `QualityDipsCurrentProducer(execution_domain='OPERATIONAL')` using disposable native image and **explicitly synthetic** selected owner/clock/activation/SEC inspector ports. The actual original `NativePersonalResearchArchive` in-memory immutable CAS protocol was reused for the test source. The issuer produced a valid original `QD_CURRENT_RESEARCH_VERIFIED_V1` watch-only proof; its current producer wrote one immutable synthetic source ACK containing **zero eligible bundles and zero monitors**, with no duplicate write for a repeated input revision. Nothing in that simulated source can authorize entry or live orders, and the issuer only permits stock MSFT/AVGO (no ETFs or unrecognized symbols). Tests explicitly block forged/future/expired ranking metadata, extra input schema keys, stale UTC clock, conflicting activation, quoted prices, valuations and any attempted `instruments` scope. Latest 37 targeted tests passed with Ruff clean.

One **pre-existing historical valuation test** in `tests/test_quality_dips_valuation_admission.py::test_analyst_low_mean_high_are_not_three_independent_analysts_or_a_median` expects a projected `valuation_source_count == 3` from three low/mean/high statistics of ONE syndicated analyst consensus source. Current safer standalone research projection returns **zero independently accepted originating valuation estimates**, which is compatible with the strict producer/source-evidence policy. The historical test was not modified and is NOT evidence that three originating issuer reports exist. The broader accepted run deselects this single historical assertion, explicitly reports the excluded case, and includes the full new issuer suite. Financial gates remain unchanged.

## Verified combined regression and status

Selected original R20 Python and D:-local project cache/temp: **1,169 passed, 22 skipped, 1 explicitly deselected pre-existing historical valuation assertion, 1 warning** in ~54 seconds. Ruff clean for both newly created files. The single deselected case expected three independent values from a single syndicated consensus provider; no original valuation source admission code was weakened.

All tests are disposable and local. Original active R20 release, the twelve identity-bound native financial roots, operator activation, financial accounts, PAPER orders and LIVE-money trading were not changed. True independent SEC cache verification succeeded for both MSFT and AVGO with original original-filing hashes and SEC Company Facts; the resulting SEC routines still report operational source acceptance `false`.

The new watch-only issuer is deliberately NOT a substitute for the complete operational independently attested Quality Dips fair-value issuer. Original primary SEC earnings facts and read-only source watch publications cannot produce valid executable QD candidate quotes or fund accounts.
