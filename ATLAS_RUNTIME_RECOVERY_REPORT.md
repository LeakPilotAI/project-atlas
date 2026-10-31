# Atlas runtime recovery — COMPLETE

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
Follow-up critical tests: 28 passed. Index rotation/caller-isolation checks were added afterward. The exact-source
pre-soak gate below subsequently completed with 1038 passing tests.

## Runtime comparison (not the final soak)

PID 22808, normal desktop launch, private memory approximately 835–891 MB then
871 MB; zero sampled >=1s loop stalls, max heartbeat age 453 ms; tasks 25,
Python threads 20, OS threads 33–39, no queued executor jobs in latest sample.
Health samples 2–30 ms. PAPER duplicate fills zero and reconciliation true.
These short observations do not establish long-duration success.

## Final long-duration runtime acceptance

Tested commit: `d33b71aa9994846225af2717df8a22789e59f68e`.
Operator startup used the normal supported Atlas desktop path. The dedicated
`scripts/runtime_recovery_soak.py` sampler verified the server PID against the
desktop runtime manifest before collecting evidence.

Measured soak:
- Target: 1800 seconds; captured 900 samples through 1799.03 seconds.
- Private memory: 845.77 MB start, 901.14 MB peak, 901.04 MB end.
- Five-minute mean private-memory buckets: 865.60, 882.98, 885.77, 893.43,
  900.56, 901.04 MB. The final five-minute bucket was flat at 901.04 MB.
- OS threads: 33–36, ending at 33; no upward ratchet.
- 1306 recorded HTTP/API probes, zero failures.
- /health: 900 successful probes; median 1.798 ms, p95 26.595 ms.
- Runtime watchdog: zero >=1 second stalls; maximum sampled heartbeat age 781 ms.
- CPU: median sampled one-core utilization 12.5%; transient peak 114.06% without
  associated request failures, thread growth, executor backlog, or watchdog stall.
- PAPER reconciliation remained healthy: 124 open and 124 closed journal events,
  zero currently open, zero duplicate fills, reconciliation_ok=true, service
  running, PAPER_ONLY, live capital disabled.
- /api/live and the manual perp board each produced a new updated_at value on all
  30 rotating surface samples, confirming continuing runtime/scanner progress.
- Investment/research/Command Center surfaces were also probed 30 times each with
  no HTTP failure.
- Operator exercised the real frontend during the soak and reported all intended
  frontend data remained visible with no observed timeout/reconnect recurrence.

Memory warmed by roughly 55 MB and then plateaued. It did not reproduce the
previous 2.60 GB -> 4.47 GB runaway. Thread/task behavior remained bounded and
the runtime stayed responsive for the full acceptance interval.

Status: **ATLAS LONG-DURATION RUNTIME ACCEPTANCE: PASS**

## Exact-source pre-soak gate

1038 passed, 0 failed, 0 skipped, 2 known warnings in 70.32 seconds.
Frontend ESLint, TypeScript no-emit, and production build all passed. Build needed
normal network access for its existing Google Inter font; no dependency added.
Evidence-prefix SHA-256 inventory saved locally before final launch.
