# Paper pipeline diagnostics

Observability only. No RSI / extension / score / R:R / ML changes.

## After pull + restart

```bash
# restart the Python API only (do not docker-compose down)
curl -s http://localhost:8000/diagnostics/paper | python -m json.tool
curl -s http://localhost:8000/diagnostics/paper-test | python -m json.tool
curl -s http://localhost:8000/diagnostics/research | python -m json.tool
curl -s http://localhost:8000/diagnostics/discord | python -m json.tool
```

Discord (after slash sync):

- `/diagnostics` — last-24h funnel + WHY NO TRADE + bottleneck
- `/papertest` — isolated TEST open/close (never counted in `/paper`)
- `/paper` — real paper journal only
- `/research` — last-24h funnel + shadow stats (not paper PnL)

## Last 24 hours funnel

This is the experiment. Do not change gates until the funnel has a real sample.

```
LAST 24 HOURS

Markets:             232
Liquid:               78
Evaluated:           XXXX

Extension passed:     83
RSI passed:           21
Quality passed:       14
R:R passed:            9
Qualified:             9

Paper trades:          9
Shadow candidates:    XX
```

- **Markets / Liquid** = latest-cycle universe snapshot
- **Evaluated → Qualified** = rolling 24h event counts (survives restart)
- **Bottleneck** is the first stage that drops to zero

If `78 liquid / 78 evaluated / 0 extension` → extension is the problem.
If `35 extension / 2 RSI` → RSI is the problem.
If `20 RSI / 0 quality` → scoring is the problem.

Gates stay locked: RSI 28/72 · extension 1.4% · R:R 1.8.

`trade_type=TEST` is written to the journal for path proof, excluded from stats / load / list_open.
`trade_type=SHADOW` never touches paper PnL.
