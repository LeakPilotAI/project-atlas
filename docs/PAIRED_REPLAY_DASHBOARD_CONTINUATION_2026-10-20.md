# Paired replay dashboard contract — 2026-10-20

Third autonomous offline increment, continuing after the previous two checkpoints.
Production remains NO-GO; the native Goal is unfinished. No services were activated.

## Implemented and verified

The paired-replay CLI additionally publishes a bounded exact-byte browser envelope
through the existing immutable publisher. An actual CLI-generated export is saved
as `tests/fixtures/market-replay-v1/research-comparison.json`; Python regenerates
and byte-compares it from source-verified synthetic archives in regression tests.

The offline dashboard consumer now verifies native WebCrypto SHA-256 before
display. It validates exact fields, immutable identities, ordered decision clocks,
all planned pairs, the complete status matrix, same/changed evidence counts,
comparable/not-comparable counts and metric subtraction. Unknown RVOL stays null;
negative RVOL and unauthorized/skill claims refuse. Rehashed contradictory counts,
metrics and authority refuse even when envelope bytes are internally consistent.

Failed replacement/rendering clears previous evidence. Delayed asynchronous loads
cannot restore an explicitly cleared view. The consumer does not independently
reproduce archives or authenticate provider evidence; that remains the Python
verifier's consistency check, not an external trust anchor.

## Final validation across these three increments

- **214 selected Python tests passed; 0 failures, 0 skips.** Includes 39 new
  replay/export/comparison cases; actual browser fixture equality is included.
- **237 Node tests passed; 0 failures, 0 skips.** Includes 29 new consumer cases
  across these increments and native WebCrypto defaults for both export types.
- Targeted Ruff, frontend ESLint, Python compilation, checkpoint updater
  PowerShell parsing and Git whitespace checks passed. Prior original failures
  remain in diagnostics. No global lint waiver or full-suite acceptance is claimed.

Evidence resides in `logs/diagnostics/research-replay-20261020`. Prior 204/214 Python
and 220 Node stage reports are retained with their original scoped results; the
latest browser result/checkpoint and hashes describe the final working tree.

## Actual local and live readiness

Locally usable offline: deterministic quote/bar ingestion and normalization,
explicit replay storage/API, quality/research/replay/paired-comparison JSON and
scriptless HTML, and tested offline frontend consumers. PRE_MARKET, REGULAR and
AFTER_HOURS fixture paths preserve exchange calendars, timestamps, provenance,
missing data and freshness contracts from prior increments. No real provider
connection, native-browser visual acceptance or main-dashboard runtime was tested.

Main Atlas startup remains denied by the protected production startup lock. An
isolated API/consumer test is not permission to launch the full application.
No fresh process or Docker census occurred; no runtime health claim is made.

Actual live collection remains blocked pending exact provider/exchange automated
use and session entitlements, storage/display/historical rights, validated feed
delay/adjustment semantics, wire budgets/reconnect acceptance, and separately
approved observation-only runtime admission. A configured credential does not
establish these rights. No subscription/key was assumed or exposed.

Shortest safe path: select a documented authorized equity/ETF feed and session
scope, satisfy existing provider/runtime gates, then separately authorize a bounded
observation-only acceptance denying all PAPER/prediction/live/Discord actions.
Offline development may continue only against isolated resources; actual concurrent
runtime isolation remains a separate acceptance gate.

## Exact continuation

Next automatically selected work: bounded point-in-time **bar correction vintage**
support in the isolated replay path. First inspect existing immutable ingestion and
default conflict-refusal contracts. Add only an explicit opt-in receipt-vintage
companion if compatible, preserve original bars/corrections, select only corrections
known by each clock, and prove future-revision perturbation invariance. Never
silently weaken default conflict refusal, migrate real databases, or rewrite a
storage engine. Integrate existing research/export/consumer contracts where safe.
Then continue independent Evidence Engine/AFI and reliability work.

The complete seven-phase inventory and all 21 decisions are retained in the verified
master: core reliability/provider/cash/lint/package/backup/restoration/Gaming;
Evidence Engine; bounded crypto PAPER research; Cross-Market Intelligence; SaaS;
institutional governance/security; commercial validation. AFI-1–10 stay PENDING.
E136 consent/recovery/no-backfill/quarantine, prediction PAPER exactly-once/
predeadline/autoflat, PM-V2 no-combo/stacking/averaging/opposing-YES-NO,
PAPER_ONLY/MANUAL_ONLY, Atlas/Genesis separation and no-VPS restrictions remain.

No lifecycle, real-volume, provider, Genesis, protected config/ACL/shortcut,
trading, Discord, registry, Git staging/commit/push/reset/cleanup or external
scheduler operation occurred. Immutable prior artifacts remain preserved.
