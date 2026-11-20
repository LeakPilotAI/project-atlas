# Atlas desktop operation — current supported mode (2026-10-26)

Current status: observation-only engineering verified; financial PAPER startup **NO**; production **NO-GO**. B1/C1/D1/E1 and all 21 historical decisions remain unchanged. Real current Quality Dips research requires an accepted publication source and authority; missing data is UNAVAILABLE. Retained Hyperliquid observations are historical and never executable.

## Open and close the supported observation interface

1. Use the existing **Project Atlas** desktop shortcut. The verified shortcut targets `scripts/windows/Atlas-Background-Controls.ps1`, opening **Atlas Control Center**.
2. Select **Open Atlas Observation (trading disabled)**. It creates an owned loopback host on an available port and opens the original alien-themed application. Use its actual URL; do not bookmark port 8000 as the current observation address.
3. Check the operating mode, source timestamps and freshness. Host health only proves the observation host is responding. It does not prove scanners, providers, financial writers or accounts are running. No data collection begins by default.
4. Select **Close Read-Only Dashboard Host** in that same Control Center to stop the owned observation host. Its retained process identity must match; ambiguous ownership refuses. Closing a browser tab alone does not stop the host. Closing the Control Center attempts its scoped cleanup; an unconfirmed close is an error, never a clean financial shutdown.

Equivalent command to open the existing controls from Windows PowerShell (no new launcher):

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1"
```

This guide does not authorize new provider access, financial inception, protected dependency installation or PAPER trading. Start Full Atlas and financial Stop remain disabled without accepted dependencies. Existing-account, D:-only, no-VPS and no-live-money constraints remain.

## Research and financial states

Quality Dips observation mode reads `/api/observation/quality-dips`, which refuses without accepted current source evidence; it never falls back to the legacy mutating research GET. A 503 clears previously accepted symbols, summary metrics and evidence. Navigation preserves the refusal. A later accepted publication restores research. Ordinary network failure may preserve explicitly STALE research; it is not current execution evidence.

Perp observation mode displays only retained public capture fields with source cut/timestamp and HISTORICAL / NOT EXECUTABLE labels. Missing volume, open interest, costs and balances remain unavailable. Current signals, candles or order execution are not inferred from retained marks. USD and USDC accounts remain separate; proposed $1,000 USD and1,000 simulated USDC are not initialized balances.

Selected PAPER Account is a read-only financial view. It must show UNAVAILABLE without accepted enrollment, native records, current pins and clock. UNKNOWN and INCOMPLETE cannot be cleared by opening or refreshing a page. The eventual autonomous session target has no per-trade confirmation; historical manual contract/policy documents remain preserved and unaccepted gates are not waived.

## Current acceptance limits

Actual installed Chrome passed the disposable valid research -> HTTP503 -> navigation -> valid recovery sequence at desktop and narrow viewport widths. These were explicit synthetic test publications, not current market data. Interactive Windows window manipulation remains unexecuted after computer-use approval timed out. Prior in-app-browser MutationObserver attribution remains incomplete; controlled Chrome recovery emitted no captured page errors. No real financial or seven-session trial has begun.

## Legacy instructions retained as history — NOT CURRENT LAUNCH PERMISSION

The original guide below described the older port8000/Docker lifecycle. `ATLAS.bat`, Atlas-Launch.ps1 and Atlas-Stop.ps1 now encounter explicit safety refusals. Do not remove those locks or run old smoke instructions to start dependencies. The old Stop Atlas batch shortcut must not be interpreted as a confirmed stop when its protected script refuses.

---

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
