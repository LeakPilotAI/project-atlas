# Atlas R24 — consumed AVGO rejection-count diagnostic refused; original evidence retained

**November 18, 2026 | MADDOG Windows desktop | actual selected native R24 | PAPER OFF and live-money OFF**

## Source-only user-approved attempt and original refusal

The operator entered exact new visible one-time approval:
`APPROVE_ONE_ATLAS_R24_AVGO_MSFT_SPY_60S_REJECTION_COUNTS_IEX_DATA_ONLY_NO_FINANCIAL_START`

This consumed the **one-shot data-only scope** and invoked the original installed selected R24 `alpaca_iex_probe.main` through the worktree-only rejected-quote reason counter. The original diagnostic wrapper returned:

- `status=ORIGINAL_DATA_ONLY_PROBE_REFUSED`
- `sanitized_result={"source_only_observation_not_accepted":true}`
- `refusal_class=null` (the original probe returned a refusal result; it did not throw an exception across the wrapper boundary)
- `elapsed_wrapper_seconds=73.906` (the bounded source observation was configured for **at most 60 seconds**, while this outer elapsed time includes original preauthorization/verification steps)
- `E1_accepted=false`, `paper=false`, `live=false`.

The **actual original result** is `logs/diagnostics/atlas-r24-avgo-reasons-data-only-20261118-r01/avgo-count-only-iex-result.json`, SHA256 **`52a536312fa38e2b8781afca20a1763301ebaeca81935d7d9476a854df5ed58c`**. The original single-use human consent `operator-one-shot-avgo-reasons-consent.json` SHA256 **`28a11dcc53ae9fee04c350687f36c8183bdacb2275e92d43ab8b678dd0eb4a2d`**. Both existing files are original immutable evidence and must **not be edited, replaced, replayed or re-approved under this scope**.

### Exact epistemic boundary

The original installed `scripts/observation_runtime/alpaca_iex_probe.py` catches `IEXRefused`, `OSError`, `ValueError` and `TimeoutError` on a data-only execution and returns generic `{"status":"REFUSED","reason":"IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"}` with nonzero exit. It deliberately redacts the specific lower-level cause. The diagnostic wrapper treated any nonzero original probe exit as `ORIGINAL_DATA_ONLY_PROBE_REFUSED` and **discarded all intermediate counters** instead of persisting counts for a refused source. Therefore this attempt did **not** generate a new original successful source-only receipt, and did **not** preserve the 11 AVGO rejection-reason counters. It is **not possible to attribute the failure to actual authentication, entitlement, IEX data availability, an overloaded socket, a source freshness test, a runtime error, or a specific AVGO quote condition** from the surviving record. Nothing permits declaring Alpaca or the validator to be defective.

The original previous, genuinely successful selected R24 IEX regular-session market sample remains separately intact and **does** prove MSFT and AVGO received fresh real IEX quotes at that earlier time: MSFT 2,353 received/2,353 accepted/1,459 fresh callbacks; AVGO 982 received/454 accepted/528 rejected/**269 fresh callbacks**; SPY 15,413 received/15,230 accepted/6,806 fresh callbacks. Genuine original source-only result `logs/diagnostics/atlas-r24-iex-msft-avgo-followup-20261118-r01/local-iex-credentialed-data-only-result.json` SHA256 **`fadc90a32eff079f0c115438aef166dee0c3b98dee0d766cd503f494aa93a2e5`**; original native source receipt SHA256 `8e0f5235e33d7404ef55100da6b1b461056ca39559c8a69af976ecf77a7a9763`. This one-time AVGO diagnostic refusal does **not retroactively invalidate** those real observations, nor prove source continuous availability.

## Independent original selected-R24 audit

Executed a **separate original selected native** `python.exe -I -B -S` with original CPU guard, original installed `atlas_r12_iex_diagnostic_receipt.read_receipt` validator for the previous successful source, exact original selected R24 code pins, original E1 rights checker and original 12-financial-root inspector, with **zero additional provider calls, zero private credential reads, no trial order, and no one-time scope replay**. Confirmed there were no new native `receipt-*.json` files with modification time at/after this consumed new local consent. This independent audit succeeded exit **0** and created read-only evidence `logs/diagnostics/atlas-r24-avgo-count-only-refusal-readback-20261118-r01/independent-original-r24-avgo-refusal-e1-hold.json` SHA256 **`e7454f5fe919bbc0117a51694e59a048e64a451c81d074a6743763ae1c1f7d78`**.

Original selected R24 selector SHA256 `afe5ae7e1e83088e14584cf942f51ba01792c375a5cc50130d1ce48c2c0747ad`, original installed `alpaca_iex_probe.py` SHA256 `b050c52a4872699d026b6108d9691853a55988af18d19d45a6d0d8c3c4237fbc`, original installed `alpaca_iex.py` SHA256 `af115f0281fae29e9e7d8f5e01ebcf3ef72fa2c46030fee593a737ba6927af79`, unchanged. New worktree-only counter module SHA256 `6cc55e24ac6c89e33bc95f449e8099cb6a3b82af0f4de4e03e646037631fd22b`, offline test suite **30/30 passing**, remains nonfinancial and not installed into R24. This actual refused network attempt changes neither selected source nor original executable quote filters.

**Original E1 provider rights 0/3**, accepted budgets 0/3, connected current financial sources 0/3, original **12/12 real financial namespace roots distinct and EMPTY**, original financial account inceptions 0/2, actual financial Stop/FLAT and first supervised PAPER not commissioned. Live-money trading disabled.

## Meaningful next step, not blind repeat

Do not invent a new scope or repeat a potentially inconclusive provider call automatically. If a **new separately reviewed operator-approved** attempt is eventually warranted, it needs a **new fail-closed source-only observability contract** that records bounded nonsecret stage status (e.g. whether the provider authenticated, exact subscription ACK was observed, count of original accepted quotes and count-only rejection labels) **even when the original probe refuses**, and retains no raw quotes/credentials/timestamps. That new design must be fully tested offline *before* a future separately authorized provider request; this consumed scope and its source script must be preserved exactly. Any returned source-only event remains separate from actual market-data rights.

Higher-value outstanding work is **authentic provider/account data-use entitlement, documented permitted personal automated IEX retention/derived indicators/private alerts, permitted Hyperliquid source/funding model, original QD source qualification, and separately scoped financial owner/account/Stop commissioning**. The Alpaca support inquiry remains an **unsent draft in `viralaiandtechnology@gmail.com`**, not proof of a provider response.

**Verdict:** AVGO real rejection reason remains **UNDETERMINED**; this attempted targeted live diagnostic **REFUSED**, its one-shot scope is CONSUMED, original three-symbol source success remains valid, E1 financial acceptance **0/3**, actual account inceptions **0/2**, financial PAPER/live OFF. Estimated **8–15+ substantive conditional financial-gate batches**, not a countdown based on synthetic tests; no VPS, paid data, C-drive Atlas scratch, auto-start or changes to the 10 protected original source pins / preexisting R23 dirty source edits.
