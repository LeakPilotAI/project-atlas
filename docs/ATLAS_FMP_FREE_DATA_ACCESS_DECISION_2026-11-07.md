# FMP free-data route — observed access decision (2026-11-07)

- Authenticated `price-target-latest-news` returned 10 rows, all for symbols other than requested `MSFT`. This response must not be promoted into MSFT analyst estimates.
- Authenticated `tipranks-search?symbol=MSFT` returned HTTP 402. Treat this as a provider payment/entitlement restriction, **not** proof that every FMP plan or endpoint is unavailable.
- Stop retrying the same restricted endpoint absent new plan/rights evidence. Do not purchase a subscription automatically.
- Neither response proves three independently originating analyst estimates or acceptable provider licensing. The Quality Dips source gate remains blocked.
- Existing PAPER startup and financial custody gates remain unchanged; no live orders or simulated fills are authorized by these probes.
- Next research branch: evaluate lawful free originating analyst research or request explicit approval for a different valuation methodology. Do not silently weaken V2/V3 quality-dip source requirements.
