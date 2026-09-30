# Atlas runtime recovery — validation in progress

Original starting HEAD: `92405d60276d7b32a817e28e73c28b3a80e203df`.
Branch: `chatgpt/atlas-rebuild-v1`. First repair: `a2b7117`.

## Proven baseline

The normal `ATLAS.bat` launch reached 2.60 GB private memory, then 4.47 GB.
The browser reproduced API reconnecting while scanner timestamps advanced.
The watchdog sampled V4 shadow replay on the loop, investment history reads,
and an import-lock wait while funnel history hydrated. Bounded thread samples
identified repeated PAPER/shadow JSON decoding and three investment journal
readers. The hub loaded all three workspaces and hidden frames kept polling;
Command Center requested full validation reports every eight seconds.

## Repairs saved

- Shared latest-per-symbol investment index consumes appended complete lines;
  detects replacement/truncation/regrowth and retains only current rows.
- Streaming tolerant PAPER/shadow reader replaces decoded whole-file lists.
- Funnel hydration is bounded while loading; daily history has a 64-file cache.
- Background startup hydrates funnel/V4 before their service consumers start;
  investment history calculations yield the loop.
- Single-flight live, Quality Dips and validation snapshots serve last-good data.
- Hub lazily loads other workspaces; polling pauses in hidden frames, avoids
  overlap, and keeps transport failures separate from render/optional failures.
- Bounded watchdog counters/profile and refresh/cache diagnostics.

No strategy thresholds, execution gates, paid services, infrastructure, or
runtime dependencies changed. Live execution remains forbidden. Journals and
user-provided failure/audit artifacts are preserved.

## Tests completed so far

First full Python suite (including actual JavaScript contract execution):
1037 passed, 0 failed, 0 skipped, two known dependency warnings, 70.76 seconds.
Follow-up critical tests: 28 passed. Index rotation/caller-isolation checks were
added afterward, so a final full run is still required.

## Runtime comparison (not the final soak)

PID 22808, normal desktop launch, private memory approximately 835–891 MB then
871 MB; zero sampled >=1s loop stalls, max heartbeat age 453 ms; tasks 25,
Python threads 20, OS threads 33–39, no queued executor jobs in latest sample.
Health samples 2–30 ms. PAPER duplicate fills zero and reconciliation true.
These short observations do not establish long-duration success.

## Next validation

Run full suite after final source checks, commit, stop/relaunch through the
normal Windows scripts, then run:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q --basetemp=logs/diagnostics/pytest-emergency-final
Start-Process -FilePath 'D:\Work\Project Atlas\ATLAS.bat' -WindowStyle Hidden
.\backend\.venv\Scripts\python.exe scripts/runtime_recovery_soak.py --seconds 1800 --output logs/diagnostics/recovery-soak-final
```

Sampler records process identity/start time, private/RSS memory, CPU relative to
one core, OS threads/children, health latency every two seconds, rotating surface
latency, scanner timestamps, watchdog/tasks/executor queue, refresh counters and
PAPER reconciliation. Exercise real browser workspace navigation during sampling.
Capture final integrity, stop cleanly, and update this report with measured results.

Status: NOT YET VALIDATED — 30-minute final soak has not started.

## Exact-source pre-soak gate

1038 passed, 0 failed, 0 skipped, 2 known warnings in 70.32 seconds.
Frontend ESLint, TypeScript no-emit, and production build all passed. Build needed
normal network access for its existing Google Inter font; no dependency added.
Evidence-prefix SHA-256 inventory saved locally before final launch.
