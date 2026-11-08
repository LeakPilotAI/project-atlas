# Live SPY prices-only acquisition evidence — 2026-11-07

Executed locally against configured Alpaca provider:

`python -B -m scripts.observation_runtime.qd_free_research_acquisition --prices-only --symbol SPY`

Observed result: exit code 0; 1,257 completed historical daily bars; 6 provider receipts; fundamentals unavailable; independent analyst targets not verified. The returned record explicitly denied operational source acceptance, PAPER fill authorization, and live order authorization.

This verifies a live read-only ETF price-history acquisition path, **not** executable L1 quote evidence, full-universe coverage, a license/rights grant, source custody, or commissioning. Existing startup and quality-dip valuation gates remain blocked. Do not infer the same result for every ETF or Robinhood-listed instrument.
