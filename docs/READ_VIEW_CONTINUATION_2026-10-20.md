# Consistent offline market read views — 2026-10-20

Previous Goal turn: PROGRESS. This turn: PROGRESS. Existing native Goal retained;
roadmap unfinished. Production NO-GO; all 21 canonical decisions unchanged. All 80
previous intended-file hashes and the latest checkpoint were verified at entry.

## Confirmed defect and working correction

The original two-case reproducer demonstrated mixed commits: an independent fixture
writer atomically committed a new bar/quote pair between the API's two reads. JSON
and HTML both combined the old bar with the new quote. Original failures and source
are retained. The fixture uses a separate writer thread/connection and a disposable
SQLite WAL file; it never accesses a production database or service.

`scripts/observation_runtime/market_replay.py` now provides `ReplayStore.read_view`.
Each complete legacy fixture API/HTML response is built inside one explicit SQLite
read transaction. The next request can see a later committed pair, but one report
cannot mix those commits. The independent WAL writer remains able to commit while
the read view is open: this is snapshot consistency, not external-writer exclusion.

Read views never call commit. Their normal exit rolls back the owned read
transaction and verifies it ended. API response construction/serialization happens
before cleanup, and no successful data response is returned until cleanup succeeds. Source failures
and cancellation retain their original identity when cleanup succeeds. If both the
operation and cleanup fail, a BaseExceptionGroup preserves both original objects,
their context and an explicit cleanup cause. This uses the repository's existing
Python >=3.12 requirement; no dependency or global lint target was changed.

An uncertain BEGIN is never followed by rollback of unconfirmed ownership. Cleanup
failure or unexpected view termination latches refusal on that store instance.
Subsequent API/data operations refuse even if the connection appears idle. There
is no reset/recovery-authority method or protected-registry interaction. This latch
is local to the object, not a durable independent recovery fence.

Initialization, new views and replay writes refuse adopting an unrelated existing
caller transaction. Even an exact ingestion retry cannot implicitly commit pending
caller writes. Direct reads retain their existing behavior; callers needing a
coherent multi-read report must use the explicit view, as the factory now does.
Observation schemas, immutable stored rows and normal successful payloads are
unchanged. No trading, scanner, provider, runtime or Docker path is modified.

## Exact validation

- **354 selected Python tests passed; 0 failures, 0 skips**, including 40 new
  read-view cases and the prior 314-case selection. Not a full-repository run.
- **271 Node tests passed; 0 failures, 0 skips** with unchanged frontend code.
- New cases cover independent concurrent WAL commits, all nine read surfaces,
  pending caller writes, nested-view refusal, exact ingestion retries, initialization,
  BEGIN failure before/after apparent effect, no-op BEGIN, rollback failure before/
  after effect, no-op rollback, unexpected view termination, source failure,
  cancellation and combined operation/cleanup errors. Actual API failures remain
  sanitized non-success with empty data; no already-built fresh payload is emitted.
- A disposable DELETE-journal fixture verifies that a concurrent writer timeout
  preserves the old committed pair and permits a later explicit retry after the
  read view ends. No production journal mode or timeout is changed; sustained
  contention/performance remains a separate acceptance gate.
- Nine successful API/HTML **status, headers and body bytes** reproduce the saved
  source exactly. Test storage is unchanged by those requests.
- Targeted Ruff, compilation, checkpoint updater PowerShell parsing and Git diff
  whitespace checks pass. Initial scoped style/version-target diagnostics were
  corrected without changing global policy or adding a new suppression. Existing
  whole-tree lint and production gates remain unwaived.

Evidence: `logs/diagnostics/read-view-20261020`; source snapshot, original failures,
final focused/broad tests, compatibility hashes, result and verified checkpoint
are retained. No earlier artifact was deleted, reset or relabeled.

## Boundaries and readiness

The caller must serialize use of a connection and avoid arbitrary raw SQL changing
its transaction during a view. This is cooperative SQLite consistency, not a
read-only OS sandbox or authentication of a transaction against malicious
same-connection replacement. Raw/privileged actors and independent external writers
are not excluded. No hard deadline is claimed for uninterruptible filesystem or
driver calls; configured SQLite timeouts are not increased. Connection disposal
and real failure reconciliation remain caller/operator responsibilities.
SQLite establishes the snapshot at its first read. The report's as-of/receipt
clocks remain caller declarations, not authenticated commit or provider times.

All work used disposable synthetic SQLite data and in-process ASGI. No Atlas,
Docker, provider, Genesis, protected state, real volume, backup, restoration,
shortcut or trading action occurred. Current process/Docker health was not
re-enumerated. Main Atlas/dashboard startup remains locked, not cleared by these
tests. Offline artifacts and fixture factories are usable; native browser visual
and real-runtime acceptance remain separate.

Premarket, regular-session and after-hours fixture paths remain tested. Actual
live collection still needs provider/exchange automated-use/session entitlements,
historical/storage/display rights, safe credential validation, enforceable actual
wire budgets and vendor timestamp/delay/adjustment acceptance, then separately
approved observation-only runtime admission. No subscription/key is assumed.
The shortest safe live path is those prerequisites and controlled read-only
acceptance denying PAPER/prediction/live/Discord actions; no startup bypass.

## Exact next execution

Advance the provider wire-budget prerequisite offline. Inspect the existing logical
attempt ledgers, gateway and installed yfinance request paths without executing
network-capable code. Reuse existing budget accounting for a narrowly scoped injected
transport acceptance. Before executing any dependency path, replace/deny every
network and user-cache/credential path; use synthetic responses only. Demonstrate
that internal retries/fan-out consume per-wire budget before each fake attempt and
that missing/uncertain accounting refuses. Do not claim account-wide/live/provider
permission acceptance from mocks, modify production adapters or send traffic. If
safe complete injection cannot be established, retain that technical gate and
select another meaningful authorized offline defect. Avoid a new broad framework.

All seven phases remain preserved in the master: core reliability/provider/cash/
lint/package/backup/restoration/Gaming; Evidence Engine; bounded crypto PAPER;
Cross-Market Intelligence; SaaS; institutional governance/security; commercial
validation. AFI-1–10 stay PENDING. E136 consent/recovery/no-backfill/quarantine,
prediction PAPER exactly-once/predeadline/autoflat, PM-V2 no-combo/stacking/averaging/
opposing-YES-NO, Gaming resource/normal PAPER cadence requirements and Atlas/Genesis
separation remain. PAPER_ONLY/MANUAL_ONLY, no VPS, no automatic Discord and no
external scheduler are permanent. No Git staging/commit/push/reset/cleanup.
