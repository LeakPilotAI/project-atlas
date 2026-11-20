# Eight-symbol end-to-end read-only acquisition — 2026-11-07

Executed `python -B -m scripts.observation_runtime.qd_free_research_acquisition --prices-only --symbols MSFT AVGO SPY QQQ IWM NVDA AAPL VOO` against configured Alpaca historical-data provider after sanitized failure-category hardening.

Observed `acquired_count=8`, `refused_count=0`, process exit code 0. Each of MSFT, AVGO, SPY, QQQ, IWM, NVDA, AAPL and VOO returned 1,257 completed daily bars and six provider receipts. The acquisition explicitly withheld fundamentals, independent analyst targets, operational-source acceptance, PAPER fills and live orders.

This demonstrates one bounded live research acquisition for eight named symbols. It does not certify the wider Robinhood universe, unattended continuous operation, provider rights, source custody, or PAPER production.
