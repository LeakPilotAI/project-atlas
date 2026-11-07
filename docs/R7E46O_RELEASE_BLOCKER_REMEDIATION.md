# R7E46O - isolated release-blocker remediation and artifact acceptance

Overall production activation remains **NO-GO**. This milestone repairs source
contracts and tests an independently packaged artifact; it does not authorize
startup, activation, migration, deployment, or a live rollback.

Date: 2026-10-16, America/Chicago, CDT (UTC-05:00).
Baseline: 13:21:46.759994 UTC / 08:21:46.759994 CDT.
Branch `chatgpt/atlas-rebuild-v1`; HEAD
`f9df47b4cd80dd647d85043aba617cf00c4e6dc0`.
Evidence: `logs/diagnostics/r7e46o-20261016/`.

## Blocker-by-blocker disposition

| Blocker | Before | After / remaining gate |
|---|---|---|
| Complete-record journal loss | Valid-prefix truncation silently allowed missing identities to be appended again. | Independent SQLite commitment records target length/digest/path/version and a pending append intent before JSONL writing. Missing/changed journal or interrupted intent fails closed across restart. Adversarial isolated tests pass. Production operation is not accepted. |
| Duplicate identity conflict | Changed price at the same symbol/source timestamp was silently skipped. | Changed price/source/session raises `JournalIntegrityError`, preserving journal and witness. Identical quote with later retrieval remains a normal duplicate. |
| Provider observation clock | Request-start clock rejected a quote generated during retrieval and understated fallback latency. | Response-receipt clocks validate RH/history/info timestamps; final fallback classification includes later info latency. LIVE <=120s and FRESH <=900s preserved; future, missing and naive RH timestamps rejected. Deterministic boundary tests pass. |
| Reproducible source artifact | Required untracked files were outside tracked release; full testing relied on an old diagnostics script. | Deterministic builder inventories tracked and explicitly allowed untracked inputs; clean extraction tested without Git metadata or original source imports. Historical recovery functions moved into a test-only fixture, not executed from logs. Packaging acceptance is distinct from production release approval. |
| Cash-scanner scope | Current scanner/calendar differ from HEAD; latest live acceptance of these exact behaviors is not established. | Both source files remain byte-identical to O baseline. Exact HEAD/current hashes and patch retained. Explicit operator scope acceptance remains BLOCKED; reverting known wake-up/freshness fixes is not a justified safe restoration. |
| Ruff | N recorded release-wide debt, including introduced findings in earlier working-tree changes. | O's new integrity/tests/builder and edited collector/test are clean. Shared provider 15 baseline ->13 current findings, no introduced code/message violations. Earlier N lint delta remains a separate unresolved release-quality gate; no unrelated formatting churn. |
| Capacity and production lifecycle | Per-call provider concurrency, residual provider threads, unbounded disk delays, opt-in/rollback unaccepted. | Not silently waived or claimed repaired. Future isolated capacity work and separately approved owned-session acceptance still required. Production feature remains disabled by default and was not activated. |

## Exact implementation changes

- `backend/app/investment/extended_hours_integrity.py`: new SQLite commitment
  protocol using only Python standard-library dependencies. FULL synchronous,
  DELETE-journal-mode transactions, exclusive witness creation, no replacement of
  missing/corrupt existing evidence. Committed file must match exact length,
  SHA-256, canonical path, version and acknowledged state.
- `backend/app/investment/extended_hours_collector.py`: verify witness under the
  existing Windows lock before reading/committing history; persist intent before
  append; flush/fsync exact appended bytes then acknowledge. A failed/uncertain
  append remains quarantined. Adds explicit offline hash-verified legacy adoption
  and conflicting-identity rejection. Existing off-event-loop cancellation drain
  and cross-process locking remain.
- `backend/app/investment/quality_dip_quotes.py`: compare timestamps to receipt
  after provider awaits; include subsequent info latency when classifying a history
  quote; reject future candidates after clock rollback and naive RH timestamps.
  Existing LIVE/FRESH/REFERENCE/STALE thresholds and provider preference remain.
  Small import sorting and UTC aliases avoid introducing new lint findings.
- `tests/test_r7e46o_release_integrity.py`: whole-row loss, zeroing/deletion,
  middle-record loss, valid JSON replacement, same-length alteration, missing/empty/
  corrupt/foreign/pending witness, before-append and post-fsync interruptions,
  restart quarantine, verified-backup restoration, explicit legacy migration,
  wrong hash/repeated migration and conflicting-identity preservation.
- `tests/test_r7e46o_provider_timing.py`: RH/history/info receipt-time boundaries,
  120s and 900s classification, 96-hour reference boundary, future and invalid RH
  times, plus subsequent fallback latency.
- `tests/test_r7e46g_extended_hours_persistence.py`: replaces the previous unsafe
  automatic-retry expectation after uncertain write with required quarantine and
  unchanged in-memory seen state.
- `scripts/build_release_candidate.py`: read-only Git inventory, explicit extra
  source inputs, per-file hashes/sizes/tracked status/role, installed dependency
  versions, fixed archive metadata, deterministic source ZIP; never stages,
  commits, deploys, starts a service, or packages runtime data/credentials.
- `tests/fixtures/r7e44b_owner_only_recovery.ps1` and
  `tests/test_r7e44b_owner_only_recovery.py`: three AST-extracted inert functions
  replace a hidden dependency on the historical diagnostics script. No entrypoint,
  process inspection or production paths are in the new fixture. All filesystem
  operations in these tests use temporary paths and fake lock checks.
- `docs/R7E46O_JOURNAL_MIGRATION_RECOVERY.md`, this report, diagnostic evidence and
  managed roadmap checkpoint document the contract, results and remaining gates.
  No launcher, cash-scanner/calendar, execution policy or protected config changed.

## Journal compatibility, trust and recovery limits

The witness is an independent durable commitment, not a checksum in each record
or reliance on a trailing newline. A durable pending intent precedes the external
append, so a crash cannot leave a shorter journal silently accepted as complete.
All cooperating writers serialize the journal/witness pair through the existing
bounded Windows lock. Verification, SQLite commits and fsync run off the API event
loop. A pending intent is never automatically retried, acknowledged or rebuilt.

Existing journals without witnesses, including empty ones, require explicitly
approved offline migration after immutable backup, writer-absence verification and
historical review. `adopt_legacy_journal(expected_sha256=...)` validates the original
schema and full-line boundary, verifies the operator-reviewed bytes, creates a
witness exclusively, and does not modify journal bytes. It is not called by startup
or collection. Migration cannot prove completeness before adoption. No production
migration was performed. See the dedicated migration/recovery document for steps.

A committed witness can verify an exact immutable backup of a damaged journal;
this was tested only with fixtures. Pending intents or missing/corrupt witnesses
remain blocked pending a separately reviewed forensic recovery plan. Never delete,
truncate, rename, reset or rebuild a live pair or lock to make checks pass.

The commitment does not defend against privileged coordinated rollback/deletion
of BOTH files, witness tampering, total storage loss or dishonest quote sources.
Independent immutable backups and host access controls remain necessary. New-store
bootstrap is allowed only when both files are absent; a local system cannot infer
loss of all independent records without an external witness. Canonical-path binding
also deliberately blocks moving a committed pair to another pathname without
review. These limits are not concealed as security or durability guarantees.

## Cash-session scope decision remains required

The exact current `scan.py` and `market_hours.py` SHA-256 values match O preflight.
HEAD copies and the full diff are retained under the evidence directory; files
named `accepted-head-*` are committed comparison references, not proof of runtime
acceptance. The last fully accepted behavior of the currently loaded cash scanner
cannot be reconstructed conclusively from Git HEAD alone.

Pending differences versus HEAD are:
1. Reject future cached fetch timestamps in `_age_ok`.
2. Refresh price on the first regular-session pass even if a pre-open fetch met TTL.
3. Replace the six-hour closed-session sleep with next-opening-aware wakeup while
   preserving the minimum interval and system-offline handling.
4. Add bounded 2026-2028 NYSE holidays, early closes, DST-aware session bounds and
   fail-closed calendar horizon.

Operator decision required: explicitly accept these existing intentional repairs
as part of the whole release, or identify a verified accepted behavior and approve
a separately isolated narrowed/restored artifact. O does neither silently. Reverting
to the older six-hour sleep merely because HEAD contains it would reintroduce a
verified defect. The quote overlay repair is in the shared Quality Dips provider;
it does not change the cash scanner's separate ingestion code or its calendar.

## Artifact acceptance evidence

Initial archives A/B were byte-identical, 883 source inputs. Their first full test
run revealed a missing historical recovery test dependency: 8 failures/2237 passes/
3 expected failures. That failure was investigated, not waived. No runtime code
failure caused those eight fixture parser errors; the script was absent from the
fresh extraction. The original source-only sandbox had masked this dependency.

After the dedicated test fixture, final C/D archives are byte-identical:
`artifact-c/atlas-source.zip` and `artifact-d/atlas-source.zip`.
SHA-256: `db389b3c57b18b8cd9d32b5ab3b2467a35b3bdca2d8d6af6a475b4cd079461b1`.
884 inventoried source/support files, including 69 explicit untracked inputs.
`artifact-c/release-manifest.json` identifies every input and its hash. Runtime
files include the new commitment module, collector/service, freshness helper,
Windows launchers/ownership modules, static/vendor assets, existing source and
tracked dependency/operational configuration manifests. Credentials, production
journals/databases, virtualenvs, logs, backups, Git metadata and other sandboxes
are excluded. Tests use the declared test-only fixture, not a copied recovery
entrypoint or logs dependency. No `.env` was packaged; `.env.example` is retained.

The extracted final artifact's file hashes match the manifest. Its application
imports resolve inside that extraction; the test harness blocks live connections
and production data/credential reads. Fake providers, temporary databases and fake
launchers are used. Installed dependencies are recorded as versions, not bundled
wheels or a tested clean-machine installation. Python/Windows/dependency portability
and operational activation are therefore not claimed. Archive reproducibility was
verified twice in the same toolchain; it is a source artifact, not a deployed build.

The archive freezes source and context before O's final roadmap/report attestation.
The mandatory later checkpoint changes documentation only; do not pretend the
archive contains a future checkpoint or silently mutate its recorded bytes/hash.

## Test record

Final canonical suite from final C/D extraction: **2245 passed, 3 known xfailed,
0 unexpected failures, 2 dependency warnings, 281.59s**, exit 0.
The 44 new adversarial/provider cases pass; their full-suite inclusion is counted
once. The three xfails remain E136 rollback-witness/dual-rollback/atomic-snapshot
gaps and remain production Discord blockers.

Initial new-contract run: 46 passed, 1 failed, 2.60s. The old persistence fixture
expected automatic retry after a durable uncertain intent; the contract was
intentionally tightened to quarantine. Initial log retained.
First artifact full suite: 2237 passed, 8 failed, 3 xfailed, two dependency warnings,
254.60s. All eight failures were missing recovery-script fixture dependencies.
Targeted final-artifact recovery fixture rerun: 8 passed, 11.97s.
Focused feature/provider suite on A: 112 passed, 31.42s. Runtime source/tests are
unchanged between A and final C/D except portability of the old recovery fixture.
All focused cases are also run by the final full suite; counts are not additive.
750 extracted Python source/test files compile. Sixteen Windows production scripts
parse; the additional test-only fixture parses and its three function bodies
exactly match the historical AST source. Dependency consistency and diff integrity
checks pass. No package installation was performed.

Ruff for new commitment/collector/builder/new tests/edited persistence test: clean.
Provider baseline 15 findings ->13, with no introduced code/message findings.
Expanded candidate subset: 478 findings across 76 files. This adds coverage of the
provider file previously outside N's 71-file subset; directly comparable N-covered
files fall from 466 to465. Together with the provider's baseline15, the comparable
expanded baseline is481 ->478 (net minus3). Earlier N release-wide lint delta,
including its introduced findings, remains open. Existing debt is not a blanket
pass, and three known E136 expected failures are not counted as passes.

## Runtime and safety verification

Final read-only verification: 2026-10-16T13:43:51.3720713Z / 08:43:51 CDT.
Supported Status still verifies API PID24804, launcher4836, run
`f670a59a-e41b-450f-9371-38208c0fc88d`, with unchanged creation identities.
Health is ok; actual Gaming false, discovery60s, paper management enabled8s,
discovery/management tasks active and execution authority false. Reconciliation:
369 opens, 368 closes, one open, zero duplicate fills, reconciliation ok. The
independent risk read shows one open, 23 UTC-day closes, net -1.8372R, limits
3 concurrent/25USD per trade/3R daily loss. Standard PAPER probe allowed=true,
consistent with current thresholds not reached; live capital and automatic real
money execution remain false. No new PAPER order was placed by this audit.

Cash last cycle finished13:30:40.244532UTC in MARKET_OPEN, about40s after regular
opening: 6VALID,17INSUFFICIENT_DATA,14STALE_DATA, no provider/rate-limit errors.
This observed wakeup supports timely opening behavior, but is not operator scope
approval or proof all37quotes are fresh. Both cash source hashes remain unchanged.
Production extended-hours journal and commitment are both absent. No production
activation was performed; actual loaded research-flag telemetry is not assumed
from absent files or source tests.

No Start/Stop/restart/recovery/process signal/Docker action/feature activation or
production migration was performed. Existing live PAPER may evolve through its
own running services; it is not claimed byte-frozen. O does not modify trading
or notification authority. PAPER_ONLY/MANUAL_ONLY remain; both central automatic
Discord senders remain denied. No Genesis inspection, shortcut modification,
Git staging/commit/push/reset/destructive cleanup, protected config change or VPS
work occurred. Historical failure evidence and unrelated source changes remain.

## Complete remaining roadmap and next milestone

Completed: historical E131-E135 isolated notification contracts; R7E44 ownership
and Gaming lifecycle audit/repair/acceptance history; R7E46F collector, G locking,
H integration, I historical isolated soak, K permanent recovery contract, L updater,
M isolated activation/rollback readiness, N release review. O remediates journal,
provider and source-artifact blockers in isolation. R7E46J's production follow-up,
cash scope acceptance and operational readiness remain unfinished.

1. **Core reliability and operations:** explicit cash behavior scope decision;
   outstanding earlier lint gates; verify release manifest scope and dependencies;
   isolated shared-provider concurrency/fallback/cancellation/capacity evidence;
   separately approved owned-session opt-in startup, actual new data/witness
   acceptance, graceful disabled rollback and sustained recovery; gaming CPU/RAM/
   data continuity benchmarks; safe Windows launcher/diagnostics/backup improvements.
   No R7E45 benchmarking or further runtime optimization is approved by O.
2. **Research Evidence Engine:** immutable timestamped hypotheses/outcomes, replay,
   precision/recall/calibration/false positives, realistic PAPER fees/slippage/
   funding, anti-lookahead/leakage, reproducible reports and Research Memory/
   analogues. E29 baseline/challenger remains NOT_READY; context-only Alpha/cadence/
   corroboration cannot bypass evidence gates.
3. **15-minute crypto PAPER research:** eligible contracts/rules/jurisdiction/fees/
   settlement, timestamped depth/price, spot/perp volatility/funding/liquidity joins,
   independent probabilities/calibration, executable edge, realistic fills/costs/
   depth, actual settlement, sustained out-of-sample regimes before any separately
   approved real-capital proposal.
4. **Cross-Market Intelligence:** unified equity/ETF/crypto/derivatives evidence,
   liquidity/positioning/anomalies, explainable scores, cautious suspicious-activity
   hypotheses, uncertainty/invalidation and reproducibility.
5. **Professional SaaS:** demand/pilots/tiers, auth/tenant isolation, billing/
   entitlements, versioned research APIs, dashboards/exports/alerts, onboarding/
   support/analytics, licensing and unit economics. Pricing hypotheses remain
   unvalidated; no deployment permission follows from this roadmap.
6. **Institutional platform:** RBAC/audit/security/incidents, reproducible workspaces/
   team governance, API stability/metrics, requirements/licensing/compliance and
   enterprise pilots. No hosted/VPS work authorized.
7. **Commercial expansion:** product-market fit/retention, partnerships/integrations,
   white-label/API licensing, evidence-led markets, revenue/margin/cost/churn and
   reinvestment.

Legacy unfinished gates: E136 independent/dual rollback and atomic consent recovery,
recipient transport/render/storage/fencing/uncertainty/dead-letter handling,
explicit Discord approval and durable no-backfill watermark, no automatic retry
of uncertain sends, exactly-once prediction PAPER predeadline auto-flat, and the
portfolio-versus-strategy risk-policy decision. Historical Prediction Market
Intelligence V2 PM-V2.1-PM-V2.6 remains: discovery, probability/calibration,
executable edge, pre-event PAPER strategy, evidence/backtests and dashboard.
One position/market, no combos/stacking/averaging/opposing YES+NO, and pre-event
execution gates remain. Phase-3 settlement research cannot silently override them.
Permanent gaming objective and strict Atlas/Genesis separation remain binding.

**Single safest next milestone: R7E46P - cash-scanner scope decision and remaining
isolated release-gate acceptance.** Obtain the explicit decision on the four
existing cash behaviors, address the earlier lint delta without unrelated churn,
and validate provider concurrency/cancellation limits in isolation. Keep Atlas
running untouched and production/Discord gates closed. Only after required source
and scope gates pass should a separately approved maintenance-window activation/
rollback be proposed. O does not recommend production activation readiness.

## Mandatory roadmap checkpoint

Supported checkpoint updater completed successfully. Backup:
`PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261016-084539-c01965a3.bak`. Read-back passed; all historical bytes outside the managed
checkpoint are identical. Permanent strategy, recovery contract, seven phases
and Prediction Market Intelligence V2 retained.
Before SHA-256 `5ebdf3e7df76cd58a9148711edee29b84c863e9bdbc7a6b2f8b979e02534f5ae`;
after SHA-256 `6db2c467859ac87ae17998ea2614467f8fef4a722ced5dc1b7304c561d181f12`.
Verification: `logs/diagnostics/r7e46o-20261016/roadmap-verification.json`.
