# Offline descriptive replay acceptance — 2026-10-20

Scoped offline functionality accepted. Production remains NO-GO. All 21 canonical
gate decisions and the production startup lock are unchanged. The existing native
Goal remains unfinished; this is progress, not full-roadmap completion.

## Working functionality

`scripts/observation_runtime/research_replay.py` replays retained normalized minute
bars over explicit increasing decision clocks. It selects only reference vintages
available at each clock for the expected previous exchange session, and only bars
received by that clock. It reuses the existing descriptive analyzer, exchange
calendar and publisher. Scanner calculations, risk limits and activation behavior
are unchanged. Per-decision evidence excludes future archive identity so adding
valid future receipts/reference corrections cannot rewrite earlier decisions.

All requested decisions remain in the denominator: DESCRIPTIVE_RESEARCH_ONLY,
INSUFFICIENT_REFERENCE, INSUFFICIENT_HISTORY or REFUSED. Unknown metrics stay null.
No directional forecasts, labels, fills, outcomes, P&L or skill are invented.
Truncated archives, duplicate/revised bars, tied reference vintages, invalid
clocks and excessive work are refused. Bounds: 10,000 supplied bars, 512 reference
vintages, 128 decisions, 200,000 row-decisions. Supplied history is not proof of
complete monitoring. Bar-revision replay needs a separate future contract.

`research_replay_export.py` verifies caller-pinned input bytes, exports canonical
logical source chunks, individual decision artifacts, aggregate JSON, scriptless
HTML and a browser envelope. Artifact names bind hashes; publication uses the
existing exclusive immutable publisher and readback. The final verifier rebuilds
the archive and reruns every decision before reporting success. Partial failure
preserves outputs and never reports completion. Input originals remain untouched;
exported source chunks preserve logical data, not original whitespace. There is
no independent authenticity or full-machine rollback witness.

Actual pre-browser V1 exports remain verifiable; V2 adds the exact-byte browser
envelope. Browser verification uses SHA-256 without re-encoding Python floats.
The offline controller checks denominator/count/clock/authority consistency,
preserves refused decisions, rejects bad replacements and prevents late async
loads from replacing newer views. Python performs full source reproduction;
browser checks do not independently authenticate or replay input sources.

## Exact validation

- Final broader guarded Python selection: **204 passed, 0 failed, 0 skipped**.
  Market replay, session/quote quality, retained research/export, new replay/export,
  shutdown outcome and PAPER durable-acknowledgement regressions included.
- New replay/export cases: **29** (13 engine, 16 export), included above.
- Earlier focused run: **50 passed** before the additional incomplete-fixture
  refusal case; not added to the broader total.
- Node consumers: **220 passed, 0 failed, 0 skipped**, including 12 new replay cases.
- Targeted Ruff, frontend ESLint, Python compilation, updater PowerShell parsing
  and Git whitespace diff check: PASS. Global lint debt is not waived.

Original incomplete-fixture failure and sandbox stall remain in diagnostics. An
initial fixture was accidentally copied from the deliberate missing-chunk test;
it remains preserved and is now explicitly tested as refused. The intact original
V1 export is separately verified. No validator weakening was needed. The sandbox
Windows socket-pair stall was interrupted; the guarded synthetic suite passed in
the reviewed native context. No provider sockets or production stores were used.

## Market-session readiness

Offline quote/bar normalization, receipt/event clocks, provenance, storage, API,
descriptive research and consumers cover U.S. equity/ETF PRE_MARKET, REGULAR and
AFTER_HOURS fixtures with exchange calendar/timezone/DST/missing-data checks from
prior accepted increments. This replay extends accountability, not live ingestion.
The offline CLI and scriptless artifact are runnable without a server. Actual
main Atlas/dashboard startup remains blocked by the existing admission lock;
isolated tests are not authorization to start it. No fresh runtime census occurred.

Actual live collection still needs provider-specific automated-use/API permission,
feed/exchange/session entitlements, historical/storage/display rights, credentials
validated without disclosure, measured wire budgets/throttling/reconnect handling,
vendor timestamp/delay and adjustment semantics, and separately approved bounded
read-only runtime acceptance. A key or subscription alone proves none of these.
Premarket and after-hours data cannot be promised from regular-session rights.

Shortest safe path: select an expressly authorized equity/ETF feed and documented
session/use/storage/display scope; close the existing provider-budget and runtime
admission prerequisites; then request a bounded observation-only acceptance with
all PAPER/prediction/live/Discord boundaries denied. No automatic activation.

## Continuation

Next selected offline task: paired descriptive-replay comparison over identical
symbol/decision clocks and explicit immutable manifests. Separate unavailable,
refused and comparable decisions; refuse denominator mismatch and unsupported
pooled skill claims. Reuse existing source reproduction and per-decision identities.
Then continue independent Evidence Engine/AFI and reliability work. AFI-1 through
AFI-10 remain PENDING; synthetic progress is not calibrated forecasting evidence.

The checkpoint retains the complete seven-phase inventory and all 21 decisions:
core ops/provider/cash/lint/package/backup/Gaming reliability; Evidence Engine;
bounded crypto PAPER research; Cross-Market Intelligence; SaaS; institutional
governance/security; commercial validation. E136 consent/recovery, PM-V2 safeguards,
Atlas/Genesis separation, PAPER_ONLY/MANUAL_ONLY and no-VPS restrictions remain.

Evidence: `logs/diagnostics/research-replay-20261020`; verified updater result and
final hashes are stored there. No lifecycle, real-volume, provider, Genesis,
protected configuration, shortcut, trading, Discord or Git mutation occurred.
