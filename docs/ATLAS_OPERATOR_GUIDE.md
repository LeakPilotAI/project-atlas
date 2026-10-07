# Atlas desktop operation

Use **Project Atlas** to launch and **Stop Atlas** to stop. The shortcuts target
`ATLAS.bat` and `ATLAS-STOP.bat` in this repository. The dashboard is served by the
API at <http://127.0.0.1:8000/dashboard>; Node is not needed for this workflow.

Startup starts the existing local Docker dependencies, waits for Postgres, starts
the API, and requires three consecutive healthy checks of health, research,
command center and reconciliation. The browser opens after that gate. Startup
warm-up is recorded separately from longevity measurements. A failed gate stops
startup with an explicit error; inspect `logs/diagnostics/launcher-ready.json`.

**Stop Atlas** requests graceful API shutdown using a file scoped to the current
desktop run. Uvicorn executes application cleanup, including PAPER reconciliation.
After 30 seconds, the stop script may force only verified Atlas process trees.
`logs/diagnostics/stop-latest.json` records whether force was needed. Docker Desktop,
unrelated Python servers, unrelated containers and other projects are not stopped.
Use the stop shortcut for predictable graceful cleanup; Windows can terminate a
closed console before all application cleanup finishes.

The desktop launch does not change global WSL/Docker memory or CPU settings.

## Logs and diagnostics

The desktop logger rotates `logs/api.out.log` and `logs/api.err.log` at 20 MiB each,
keeping three backups per stream. This runs throughout operation, not only at
startup. Operational logs are separate from append-only research evidence.

The permanent `scripts/windows/Atlas-Desktop-Smoke.ps1` diagnostic checks shortcut
targets and operator surfaces. With `-LongevitySeconds 300 -ProbeIntervalSeconds 15
-StartAtlasIfNeeded`, it starts Atlas if needed, stabilizes, then runs the strict
five-minute gate. Every failed measured probe counts. The result is stored in
`logs/diagnostics/desktop-smoke-latest.json`, including runtime JSON, bounded stack
samples, process/listener ownership and container health when failures occur.

Generated logs/diagnostics are ignored by Git. Never remove research journals,
stored observations, PIT evidence or immutable backtest records as log cleanup.

## Research-only boundary

`live_capital_allowed=false`, `automatic_real_money_execution=false` and brokerage
execution `MANUAL_ONLY` are permanent boundaries in this roadmap. Engineering
GREEN is software validation, not demonstrated investment profitability. The
historical perps HOLDOUT remains FAILED_NEGATIVE: 546 trades, -26.7235R and
-0.04894R expectancy. Retrospective V3 evaluation remains evidence-insufficient.
