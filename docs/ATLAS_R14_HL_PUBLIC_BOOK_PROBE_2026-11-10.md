# Atlas R14 selected Hyperliquid public-book probe — 2026-11-10

## Result

**DATA-ONLY PROBE IMPLEMENTED, SOURCE TESTED. ONE REAL PUBLIC BTC OBSERVATION ATTEMPT REFUSED. NO VALID QUOTE ADMITTED, NO FINANCIAL PAPER START.** Source and test changes are in the workspace; the immutable selected native R14 release and selection revision 13 were never rewritten or reselected.

The public-info endpoint supports `metaAndAssetCtxs` and `l2Book` request kinds, including a provider-native order-book timestamp in milliseconds, bid and ask levels, and mark/oracle context. The new `scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py` uses the reviewed native-compatible `HyperliquidAdapter.paper_execution_observation`, which consumes an individual durable allowance for each of its **two** concurrent HTTP public-info attempts. No wallet/account endpoint or order route is used.

## Executed read-only and data-only observations

- Existing native selection: R14 `7ff9d3dba2eabe110f843c13efac49464805de2a`; selected revision-13 file SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31`.
- Exact read-only preflight `--inspect` returned `selected_code_revision=13`, **public-request budget 4 of original 12 remaining**, no real market book admitted, no provider/trading authority.
- Canonical preexisting budget `D:\Work\Project Atlas\backend\data\personal_paper_public\hyperliquid_request_budget.sqlite3` was inspected with SQLite `mode=ro` before and after; it is an existing bounded ledger, not a new or replenished allowance.
- One explicitly data-only command, single BTC market, exact restricted scope:
  `backend\.venv\Scripts\python.exe -B -u -m scripts.observation_runtime.atlas_r14_hyperliquid_public_book_probe --execute-data-only --confirm-scope HYPERLIQUID_TWO_PUBLIC_INFO_REQUESTS_DATA_ONLY_NO_TRADING --symbol BTC`.
- The command returned exit **1**, sanitized `{"status":"REFUSED","reason":"PUBLIC_INFO_PROBE_UNAVAILABLE",...}`. Crucially, **no authenticated/executable BTC bid/ask sample was accepted**. No auto-retry or automatic source enrollment happened.
- Independent read-only budget recheck: **10 of 12 attempts consumed; 2 remain**. Exactly **two** new public HTTP allowances were consumed by this one attempt. A consumed allowance proves attempt accounting, not a successful response, freshness, quote continuity, provider-rights acceptance, or financial authority.
- The original first version of the probe reported only a generic refusal, so the precise failure category of this particular attempt **cannot be reconstructed** and should not be guessed. After the failed attempt, added future sanitized error classifications for independent NTP, HTTP status/transport/timeout, native public-book admission, and request-gate refusal. No second network attempt was made to obtain a more specific error.
- Create-only nonfinancial report `docs/ATLAS_R14_HL_PUBLIC_BOOK_OBSERVATION_2026-11-10.json` SHA-256 `c80d5eb6b6f3809544d682bf6d6373a410e4f77270ba9dd55a291baba066c07c`. These results do not represent a financial forward PAPER trade or data-rights approval.

## New source-only safeguards

The probe now has a strict `--inspect` path that verifies current R14 native identity and existing budget **without creating an NTP clock, network connection or writable budget**. The separately scoped `--execute-data-only` path restricts to BTC/ETH/SOL, exactly one public-book sampling operation, prior-existing shared durable request gate with at least two remaining (never initializes or resets it), and operational two-peer Google/Cloudflare NTP authority. It calculates book timing in real milliseconds from the verified independent monotonic/UTC anchor; Windows wall time is not substituted.

Validation requires source-matched native selected R14, unambiguous symbol, both validated uncrossed book sides, positive finite Decimal strings, provider-book timestamp inside the 5-second freshness window, and false execution/startup permissions. It never labels current book observation as financial fill, signed provider eligibility, continuous freshness, funding settlement, fee schedule, or owned PAPER account. Network errors, invalid books, and revoked NTP fail closed; all authorization claims remain false. Only sanitized refusal types will be shown on future separately authorized attempts; raw provider errors, account data, and private secrets are not logged.

New source `scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py` SHA-256 `9826ffec04cde81e333971820d1a129e9d456adf9c7e7cd88f0a91ad8f8a075a`. New focused test source `tests/test_atlas_r14_hyperliquid_public_book_probe.py` SHA-256 `3db8562202440fddd84d68b3740466544403250ee875a4561c39b0ceca14db38`.

## Verified regression and next work

Final Windows IDLE-priority focused tests across R14 selected probe, existing Hyperliquid public book adapter, R14 two-lane readiness, and public-data budget/record parsing: **103 passed, 0 failed**, with one pre-existing Starlette/httpx deprecation warning. The initial test after the real attempt expected the old 4-request balance; it was updated to the independently verified remaining 2, then full 103 passed.

**NEXT:** do not spend the final two existing public requests automatically or reset the ledger. Review the original refusal by expanding *offline* synthetic diagnostics and comparing parser assumptions with current published provider schemas. A fresh network retry or any increase/reset to the provider budget requires a separate explicit data-only decision. In parallel, separately qualify free Alpaca IEX feed/quote rights, real QD and Hyperliquid PAPER writer custody, continuous financial time, durable financial Stop/flat reconciliation, and supervised first operating session.

**R14 remains selected; formal financial PAPER operating gates remain NO-GO, 0/9 independently accepted.** No Alpaca credentials, Hyperliquid wallet/account, private provider data, live/PAPER order, desktop launcher, Docker, Windows time/boot change, installed native release mutation, GitHub push, paid data/VPS, or Project Genesis changes occurred.
