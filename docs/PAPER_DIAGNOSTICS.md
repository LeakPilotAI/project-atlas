# Paper pipeline diagnostics

Observability only. No RSI / extension / score / R:R / ML changes.

## After pull + restart

```bash
# restart the Python API only (do not docker-compose down)
curl -s http://localhost:8000/diagnostics/paper | python -m json.tool
curl -s http://localhost:8000/diagnostics/paper-test | python -m json.tool
curl -s http://localhost:8000/diagnostics/discord | python -m json.tool
```

Discord (after slash sync):

- `/diagnostics` — funnel + WHY NO TRADE
- `/papertest` — isolated TEST open/close (never counted in `/paper`)
- `/paper` — real paper journal only
- `/research` — shadow funnel only

## What the funnel means

Tickers → liquid set → evaluated → candles → extension → RSI extreme → quality → R:R → paper open → Discord DM.

`trade_type=TEST` is written to the journal for path proof, excluded from stats / load / list_open.
`trade_type=SHADOW` never touches paper PnL.
