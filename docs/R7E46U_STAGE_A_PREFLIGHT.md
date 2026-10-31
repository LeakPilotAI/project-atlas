# R7E46U Stage A — read-only Docker ownership, persistence and backup preflight

**Stage A readiness BLOCKED. Stage B NOT AUTHORIZED and NOT EXECUTED. Production release NO-GO.** Observed October 18, 2026, America/Chicago (CDT UTC−05); machine UTC evidence is retained. Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0 unchanged. The full master roadmap was read and its T checkpoint/recovery/strategy reconciled with source and evidence.

## Docker availability and ownership

Selected context points to npipe:////./pipe/dockerDesktopLinuxEngine. A read-only server-version probe failed with nonzero exit:

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

Docker-dependent inspection stopped immediately. No container, image, network or volume inspection followed. No Docker Desktop/Engine start, restart, termination or settings change occurred. No global container inventory or Genesis access occurred.

| Requested fact | Stage A result |
|---|---|
| Exact PostgreSQL container ID / Compose ownership | UNVERIFIED — no ID established |
| Exact Redis container ID / Compose ownership | UNVERIFIED — no ID established |
| Actual image identities, stop signals and PID1 | NOT TESTED |
| Actual networks, mounts, named-volume ownership and health | NOT TESTED |
| Unrelated resources excluded | No lifecycle target selected; no unrelated/Genesis resources inspected |

Names atlas-postgres / atlas-redis are only source expectations, never ownership proof. Container state remains UNKNOWN, not absent or stopped.

## Persistence and backup readiness

Static docker-compose.yml pins PG image timescale/timescaledb@sha256:d8336a5c9cc49bdbf1e935234e8c87ab64b6d6d195fd2ecedff7b00185557631 and Redis image redis@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99. Declared mounts are atlas_pgdata -> /var/lib/postgresql/data and atlas_redis -> /data. These declarations do not verify actual images, volume existence, project-prefixed volume names, durability or Redis save/AOF configuration. No database or credential contents were accessed.

Metadata-only checks found these scoped locations absent: D:\Work\atlas-backup (documented in docs/WINDOWS.md), repository backups/, backend/backups/, backend/data/backups/. No backup payload was opened, created or restored. This limited inventory does not prove that backups do not exist elsewhere. No usable PG/Redis backup, provenance, freshness, independent integrity evidence or successful restoration evidence was established.

Docs/WINDOWS.md describes environment/local backend-data copy/restore; it does not establish a PostgreSQL/Redis named-volume backup or certified restoration. docs/R7E46O_JOURNAL_MIGRATION_RECOVERY.md supplies a non-destructive journal/commitment recovery contract; journals or rotated logs are not substitutes for database/cache persistence backups. The T acceptance plan requires verified independent persistence/journal backups. **Backup readiness remains BLOCKED.** Next evidence must identify the actual backup location, source IDs/volumes/time/tool/provenance, integrity and a reviewed restoration procedure. Backup creation/restoration, DB queries/container exec and credential access are not authorized here.

## Stage B hold and future binding procedure

An exact reversible Stage B cannot be finalized without verified IDs and persistence/backup evidence. Do not substitute expected names or historical IDs. No executable stop/start command is issued by this report.

Required binding sheet before separate approval: local endpoint/version; PG and Redis full IDs; exact matching Compose project/root/single config/service/non-oneoff labels; image digests and signal/PID1; exact attached network/volume IDs/names and labels; health/restart/persistence state; verified backup provenance/restoration record; baseline continuity markers; candidate source hashes; allowed initial/final states; backend-running versus container-only scope; approval timestamp and stop/restore window.

After read-only Stage A prerequisites pass, use docs/R7E46T_REAL_CONTAINER_ACCEPTANCE_PLAN.md with those exact verified IDs. Separate approval must explicitly cover:

1. Verified graceful backend exit before dependency actions. Container-only acceptance while API is already stopped does not certify live backend/PAPER drain. Any Gaming/API startup needs its own explicit authorization and real cadence/authority checks.
2. Stop only the frozen Atlas IDs (current source order PG then Redis) with safe graceful signals and no forced-kill timeout. Hold on ambiguous ownership or backend timeout. Never stop Docker Desktop/Engine, unrelated resources or volumes.
3. Verify final backend STOPPED and both same IDs exited using fresh pair evidence, completed receipt, no pending intents/unconfirmed CLI and approved database shutdown/persistence evidence. Partial failure is not success.
4. Restore only retained Atlas IDs after explicit restoration approval; both dependencies must be healthy with unchanged mounts/persistence before an optionally approved API startup. Do not recreate containers or repair missing volumes automatically.
5. Prove Docker Engine/Desktop continuity through local endpoint/version/status observations; protection of unrelated resources relies on no target outside the frozen allowlist and approved external continuity evidence, without accessing Genesis. No global inventory is required or authorized.
6. Preserve receipts and logs on partial failure; never replay uncertain stops, clear records, force-kill, prune/down/remove, or silently restart. Reconciliation and backup restoration require separately approved ownership/data-recovery scope.

The plan remains conditional and blocked; Stage B approval has NOT been obtained.

## Shortcut readiness

Current Atlas-only desktop metadata confirms Atlas Background -> verified background controls GUI; Project Atlas -> ATLAS.bat / blocked legacy launch; Stop Atlas -> ATLAS-STOP.bat / blocked legacy stop. The batch can print stopped after failure. No shortcut literally named Start Atlas was found. Links and scripts remain unchanged and were not executed.

The documented future migration is docs/R7E46T_SHORTCUT_MIGRATION_PLAN.md: explicit approval of names/default Gaming versus normal/targets, per-link backups, isolated metadata review, truthful backend-only completion reporting, a separate opt-in Complete shortcut only after real acceptance, and byte-preserving rollback without running legacy paths. This is a proposal awaiting approval, not an approved or installed migration.

## Validation and preservation

60 isolated ownership/shutdown tests passed in 37.51s; 0 failed, 0 skipped/xfails in this selection. Both selected Python test modules compile. All 18 Windows scripts parse in PS5.1 with zero errors. Targeted Ruff passes; Git diff checks pass. No implementation source changed, so no full-suite rerun was necessary. Historical T full2348 passed/3 inherited E136 xfailed and whole-tree3997 Ruff findings remain historical evidence, not newly rerun results or waived gates.

The exact T source archive was verified and cleanly extracted for isolated testing; its909 manifest hashes match. All909 pre-existing release-source files matched the preflight baseline before the mandatory roadmap-only checkpoint edit; runtime source/config/scripts and shortcuts remain unchanged. No existing failure artifacts were removed. Supported Atlas Status confirms STOPPED/no background run; runtime lifecycle record directory had no active JSON/lock records before status. Evidence: logs/diagnostics/r7e46u-stage-a-20261018/result.json and raw records.

## Gates and safest next execution

U Stage A Docker availability, actual ownership and backup readiness are BLOCKED; real shutdown/persistence/restore remains NOT TESTED. Preserve cash C1-C4 acceptance, provider rights/HTTP budget, stuck-worker operational acceptance, Ruff policy, clean-machine/runtime/Gaming resources/cadence, desktop migration, E136/Discord consent and PM-V2 safeguards. No gate was closed by an unavailable daemon or passing mocks.

Safest next execution: repeat **R7E46U Stage A read-only** when the local Engine is already accessible under operator control and an attributable backup location/provenance record is available. Do not automatically start Docker or proceed to Stage B. No VPS requirement.

## Full remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Current core gate: complete U Stage A exact ownership/persistence/backup evidence before seeking separate Stage B lifecycle approval.
