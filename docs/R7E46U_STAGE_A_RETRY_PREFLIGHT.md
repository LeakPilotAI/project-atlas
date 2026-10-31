# R7E46U Stage A retry — read-only ownership, persistence and backup preflight

**Engine/ownership metadata verified; overall Stage A readiness BLOCKED; production release NO-GO. Stage B NOT AUTHORIZED / NOT EXECUTED.** Observation date October18,2026 America/Chicago (CDT UTC−05); exact UTC evidence accompanies the report. Branch chatgpt/atlas-rebuild-v1;HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0 unchanged. Read latest permanent master/checkpoint and U/T preflight/ownership/recovery/migration/acceptance documents. No implementation repair was performed under this read-only authorization.

## Availability and positively identified Atlas resources

The initial restricted probe returned permission denied. An independent read-only local-pipe probe established that the Engine is available, version29.8.1, via npipe:////./pipe/dockerDesktopLinuxEngine. This is distinct from the previous unavailable-pipe failure; no Desktop/Engine action was taken.

Both exact-name discovery records passed independent ID/label/root/config/service validation before following resource references. Names alone were never accepted as ownership proof.

| Fact | PostgreSQL | Redis |
|---|---|---|
| Full container ID | `c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1` | `13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193` |
| Service/name | postgres / atlas-postgres | redis / atlas-redis |
| Compose project | projectatlas | projectatlas |
| State / PID / exit | exited /0/0 | exited /0/0 |
| Stored Health.Status | unhealthy | unhealthy |
| Restart policy/count | unless-stopped /0 | unless-stopped /0 |
| Stop signal | SIGINT | optional field absent (Docker default signal; no actual send) |
| Volume | projectatlas_atlas_pgdata | projectatlas_atlas_redis |
| Mounted destination | /var/lib/postgresql/data | /data |

Both have exact working_dir D:\Work\Project Atlas, the single matching docker-compose.yml, correct service labels and oneoff=False. Their attached projectatlas_default bridge network ID is `f18c270fd70d5dc5c663ed237f1658d5fc4a9b9d0a4723daaa18efbbee5f5b8d`; its project/network labels match projectatlas/default. No network member inventory was queried.

Actual container image IDs and local RepoDigests match the source-pinned digests:
- PG: `sha256:d8336a5c9cc49bdbf1e935234e8c87ab64b6d6d195fd2ecedff7b00185557631` (timescale/timescaledb).
- Redis: `sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` (redis).

Each named volume independently has projectatlas Compose ownership and its expected atlas_pgdata/atlas_redis volume label, local driver, and mountpoint matching that exact container mount. The only followed image/volume/network references came from positively identified Atlas containers. No global container list, unrelated-container inspect or Genesis-resource access occurred. Config.Env, arbitrary arguments, health-command output and database contents were not dumped.

Both containers are currently stopped. Stored unhealthy health fields are not proof of current running failure or readiness; no healthy start was observed. Exit0 and prior Docker timestamps are not certification of the new Complete Shutdown path, nor new shutdown-provenance correlation.

## Persistence configuration: what is and is not established

Selected non-secret configuration metadata shows PGDATA=/var/lib/postgresql/data, matching the actual PG volume. Redis WorkingDir=/data and its exact default redis-server command match the actual /data volume; image declares /data. Only the PGDATA environment path was projected; no credentials or other environment values were read. Full volume contents, PG settings/database catalogs, Redis CONFIG/INFO, logs containing data, container exec and backup payloads were not accessed.

Effective PostgreSQL config overrides/WAL/tablespace coverage, Redis prior save/AOF settings, persistence errors and data recoverability remain unverified. A declared/mounted volume and default command do not prove durability. Both services are stopped; starting them merely to query settings is not authorized.

## New release-blocking actual-adapter finding

The production format extracted from scripts/windows/Atlas-CompleteShutdown.ps1:74 references .Config.StopSignal directly. On the positively owned Redis container the optional key is absent, and the exact production format fails during a read-only inspect:

```text
template parsing error: template: :1:78: executing "" at <.Config.StopSignal>: map has no entry for key "StopSignal"
```

The actual reproducer exits1; it invokes only docker inspect, never the Complete script or a lifecycle action. A null-safe diagnostic projection read the metadata successfully, without bypassing ownership validation. The production source remains unchanged. Source control flow indicates this failure would refuse shutdown at dependency preflight, rather than permit a safe Complete acceptance. **The adapter needs a separately authorized isolated optional-field repair/regression before Stage B.** Passing fake-CLI/ownership tests did not exercise Docker's real Go-template optional-key behavior.

The initial Redis discovery template failure and an audit-only missing JSON delimiter in volume/network projections are preserved. Corrected read-only projections were reissued and independently parsed/validated before facts were accepted. A diagnostic null-array preflight guard also initially refused status; a direct empty-record check corrected that observation. These diagnostic failures were not hidden or mistaken for ownership/Engine failures.

## Backup provenance and required separate plan

All four scoped locations remain absent: D:\Work\atlas-backup, repository backups/, backend/backups/, backend/data/backups/. Only directory existence/top-level metadata was checked. No backup payloads or secrets were opened, created, restored or hashed. No other drive/project/location was searched. No usable attributable database/cache backup, source/time/tool manifest, integrity record or successful restore evidence was established; a backup may exist elsewhere.

WINDOWS local-file copies and O journal/commitment recovery instructions do not establish PG/Redis volume recoverability. **Backup readiness is BLOCKED.** docs/R7E46U_RETRY_BACKUP_CREATION_RESTORE_PLAN.md proposes two separate approvals: (A) cold, read-only-source volume/journal backup creation under verified writer quiescence, reviewed tools, confidential local storage and independent manifests; (B) scratch-only isolated restoration using pinned images/no network/production mounts, approved validation access and retained evidence. No creation, restoration, database query, scratch resource or cleanup is authorized by that proposal.

## Exact Stage B binding and hold

Use the full IDs/volume/network/image bindings above only as observed evidence; revalidate them before any approved action. Stage B stays blocked by the real inspection-template defect, usable-backup gap, effective persistence verification and absent lifecycle approval. The T acceptance/rollback plan remains applicable with these bindings, not permission to execute it.

A future separately approved container-only sequence must explicitly cover starting the currently exited exact IDs, health observation, Complete shutdown without forced termination, exact persistence/receipt verification, restoration to healthy, and the approved final-state choice. Returning to the original exited baseline requires an explicitly included graceful stop; it must not be implicit cleanup. This container-only path cannot certify live backend/PAPER drain. A full running-path trial requires additional explicit Gaming/API startup approval, provider/cash prerequisites, real PID/run/creation/authority/cadence checks and a bounded final shutdown. No API starts automatically.

Engine/Desktop and unrelated-resource protection must rely on exact-ID allowlisting and approved continuity evidence without inspecting Genesis. Abort on identity/mount/state drift, backend timeout, uncertain CLI/receipt, save errors or failed restoration. Never clear receipts, retry uncertain stops, force-kill, recreate containers/volumes, prune/down/remove or broaden targets. Partial failures preserve evidence and block startup pending a separately approved recovery plan.

## Validation, runtime and preservation

60 isolated ownership/shutdown tests passed in35.85s;0failed,0xfail/skip in selection.18 Windows PS5.1 scripts parse with0errors;two selected Python modules compile;targeted Ruff and Git diff checks pass. The actual production Docker-format reproducer remains an unresolved release finding, not a successful acceptance. Historical full-suite/E136/Ruff results remain historical, not newly rerun or waived.

Supported Atlas Status confirms STOPPED/no run after directly confirming no active lifecycle records. Exact shortcut hashes match the previous Stage A inventory: verified Atlas Background GUI unchanged, legacy Project Atlas and Stop Atlas links unchanged. No shortcut executed/installed or legacy stopper invoked. Current release-source/runtime/config bytes are unchanged except the separately required managed roadmap update and new reports/evidence.

Evidence directory: `logs/diagnostics/r7e46u-stage-a-retry-20261018-004347`. Prior U/T failures, artifacts and backups remain intact. No production journal/PAPER data, trading authority, subscriptions/outbox, Discord gates or protected configuration changed. No Atlas/Docker/container lifecycle action, Engine/Desktop action, Genesis access, staging/commit/push/reset/destructive cleanup or VPS work occurred.

## Updated gate disposition and next safest execution

Engine availability, exact Atlas ownership, pinned images and declared mount/network metadata: PASS for the observed read-only facts. Running health, effective persistence and real Complete/restore: NOT ACCEPTED. Backup/provenance and real inspection-template handling: BLOCKED. Cash scope, provider rights/HTTP budget, stuck workers, Ruff, clean-machine/runtime/Gaming resources/cadence, desktop approval, E136/Discord consent and PM-V2 safeguards remain unchanged. Production NO-GO.

Next safest execution: a separately authorized **R7E46U-A1 isolated metadata-inspection adapter repair/regression** for missing optional StopSignal, without runtime activation. Backup creation/restoration validation still needs its own explicit approval. Do not proceed to Stage B.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Current core obligations: repair real optional-field inspection safely, verify effective persistence and establish independently restorable backups, then obtain separate Stage B and shortcut approvals.
