# Normal Project Atlas desktop launcher repair — October19,2026

**Launcher repair PASS. Normal icon is ready to delegate a separately operator-authorized startup attempt. No startup authorized or executed by this milestone. Production release remains NO-GO.** Unattended morning PAPER-session readiness is not established by repairing a link.

## Exact before/after

Operator confirmed familiar shortcut C:\Users\renal\OneDrive\Desktop\Project Atlas.lnk. Both links are owned by the expected interactive Windows account; expected background executable has Valid Microsoft Authenticode signature. Controls/UI/manager hashes match independently tested Q sources, and current Controls delegates manager Start/Status/Stop. All source verification recorded before editing.

| Field | Before | After |
|---|---|---|
| Target | D:\Work\Project Atlas\ATLAS.bat | C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe |
| Arguments | empty | -NoProfile -ExecutionPolicy Bypass -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1" |
| Working directory | D:\Work\Project Atlas | D:\Work\Project Atlas |
| Icon | explicit Atlas favicon | D:\Work\Project Atlas\frontend\src\app\favicon.ico,0 (unchanged) |

ATLAS.bat invokes the blocked Atlas-Launch.ps1 then blocked legacy stopper. The repaired link no longer invokes either batch or legacy script. Familiar filename, explicit icon, description, hotkey, window style, owner and DACL preserved; only target/arguments/workdir assigned. Atlas Background.lnk unchanged byte-for-byte (SHA25646513BB11E2F4B0D6624407817677645552C838A236FF6288FF28E2FBF2B7448).

Existing description still mentions Stop Atlas because only three requested fields were changed. **Stop Atlas.lnk remains legacy-blocked; do not use it.** Future approved session uses the verified GUI's backend Stop; Complete Shutdown remains separate/unvalidated. No additional shortcut or source changes made.

## Backup and direct validation

Backup created with exclusive CreateNew before edit, flushed, hash-checked, and retained:

D:\Work\Project Atlas\logs\diagnostics\desktop-launcher-repair-20261019\Project Atlas.original.lnk

Original SHA256=6D544C2BA3F6DA4DDA21C880FB18EAE6E8B7FE05F8548C48E431E94A2B1037F5
Backup SHA256=6D544C2BA3F6DA4DDA21C880FB18EAE6E8B7FE05F8548C48E431E94A2B1037F5
Repaired SHA256=52B027D49FAAEAE779E195DF15ECAE42EC0FF3C10384894354383582D471626E

Backup bytes equal original. Reopened modified .lnk fields equal reviewed Atlas Background target/args/workdir. Other exposed metadata and ACL match original. Neither shortcut was executed, and COM Save was used only on Project Atlas.lnk. No registry/desktop-settings change.

Initial PS5.1 helper validation nested ConvertFrom-Json arrays and stopped before backup/edit. Original helper/failure note preserved; array assignment corrected without weakening contract/hash/owner/signature checks. Final validation passed. No product source or test assertion modified. Direct native shortcut verification is appropriate for this reversible metadata-only change; no redundant runtime test run. Prior54launcher/ownership andQ309isolated regression evidence remain historical/source-scoped, not fresh runtime proof.

## Fresh bounded Docker metadata

Observed 2026-10-19T09:26:10.402358+00:00 / 2026-10-19T04:26:10.402358-05:00. Intended contextdesktop-linux; endpointnpipe:////./pipe/dockerDesktopLinuxEngine. Linux Engine available, version29.8.1, EngineID1b4f668e-97b1-4e02-8647-454cf431e1b2.

Exact labels match projectprojectatlas, postgres/redis services, rootD:\Work\Project Atlas, exact docker-compose.yml, oneoffFalse, expected names and64hex immutable IDs. No atlas-project duplicates found. Names alone were not accepted as ownership. Metadata excludes environments, commands containing secrets, health-check logs and database payloads. No mounts/volume contents read.

| Service | Immutable ID | State | Exit code | Retained Docker health label |
|---|---|---|---|---|
| postgres | c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1 | exited | 0 | unhealthy |
| redis | 13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193 | exited | 0 | unhealthy |

Both runningFalse/PID0. **These are stopped containers, not live healthy services.** The unhealthy field is Docker's retained health status, not a fresh probe while exited; no diagnosis of its prior cause was attempted. No health-check output/logs/credentials read. Read-only image identities also recorded in docker-readonly.json. Neither container started/stopped/recreated or modified; Engine/Desktop untouched.

At 2026-10-19T09:27:05.9028924Z runtime read-only root-qualified process count0, port8000listeners0; owner/start/stop/recovery locks/runtime/stoprequest/CompleteShutdownreceipt/inspection-control absent. No manager Status called because its stale-record recovery may write metadata. These observations support Atlas stopped, not global writer exclusion or permission to initialize a missing inspection registry.

## Startup decision and remaining gates

- **GO for launcher-file correctness:** normal familiar icon delegates the verified GUI and can be used for a separately authorized startup attempt subject to all normal refusal checks.
- **NO-GO for executing startup in this milestone:** user authorized shortcut repair/read-only metadata only. No unattended-session permission inferred.
- **Production release NO-GO:** all21gate decisions unchanged5scopedPASS13BLOCKED3NOT_TESTED. Only shortcut-workflow evidence updated; full workflow remains BLOCKED because legacy Stop guidance/link and real Complete Shutdown acceptance remain open.
- Stopped databases must be restored by the existing verified manager only within an approved startup attempt; health/readiness then requires actual checks. Exact identities now verified, but no dependency-restoration acceptance performed. Do not infer current health from container existence or exit0.
- Existing current-candidate runtime/Q shutdown acceptance, source/journal durability/backup-restoration, provider rights/wire budget, cashC1-C4 scope, Gaming sustained performance, E136/Discord and clean-machine gates remain. Full uncertain-state recovery not integrated; missing registry is not recovery clearance. Do not delete records or bypass an encountered fence.
- Normal manager startup leaves dedicated extended-hours stock research disabled absent a separate explicit activation; this repair grants no premarket opt-in. Configured PAPER automation means a future start is not necessarily monitoring-only; select lane/session/duration explicitly. Prediction unattended opens remain blocked. Live trading/automatic Discord unchanged/disabled by established source controls.

Next safe execution: separately authorize a bounded manager-based PAPER_ONLY startup/dependency-restoration/readiness acceptance with fresh ownership preflight, explicit scope and graceful owned shutdown plan; do not conflate that approval with unattended monitoring or production activation. No such attempt begun here.

## Roadmap and preservation

Existing updater used; result.json independently verifies backup equals initial master, exact checkpoint read-back and byte-identical history outside managed section, plus permanent strategy/recovery/PM-V2 anchors. Allsevenphases and21gate IDs/decisions/prior evidence preserved. No Gitstage/commit/push/reset/delete. No Atlas/backend/container lifecycle, ATLAS.bat/backend code/Docker config/registry/protected recovery/trading/Discord/Genesis changes. Only authorized desktop .lnk fields plus offline docs/evidence/checkpoint changed.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

