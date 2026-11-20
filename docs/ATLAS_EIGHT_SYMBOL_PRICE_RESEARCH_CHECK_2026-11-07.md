# Expanded bounded live prices-only acquisition — 2026-11-07

Ran the bounded prices-only diagnostic against configured Alpaca for `MSFT NVDA AAPL VOO`. The batch returned `acquired_count=4`, `refused_count=0`, exit code 0. Each symbol reported 1,257 completed historical daily bars and six provider receipts.

Combined with separately observed SPY, QQQ, IWM, and AVGO results, eight distinct symbols have demonstrated historical research acquisition. This is not proof of all-market coverage, executable quotes, analyst price targets, source rights, financial custody, or PAPER commissioning. Every result explicitly denied operational source acceptance and PAPER/live order authorization.

Automated tests also verified partial-outage exit code 2, complete-batch exit code 0, and refusal of invalid count types; 67 relevant tests passed.
