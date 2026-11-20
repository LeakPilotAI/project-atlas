# Desktop launcher PAPER session preflight — October19,2026

**STARTUP NO-GO. Production release NO-GO.** Read-only preflight complete; operator confirmed usual launcher is **Project Atlas**. No launcher/GUI/manager/Docker lifecycle action performed, no source correction made during preflight. Branch chatgpt/atlas-rebuild-v1;HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Q's source changes preserved.

## R7E47Q closure

Q independently finalized:309passed(187focused+40PAPER+82lifecycle),0failed/0skip/0xfail,1inheritedaudioopwarning. Original failures retained. Full canonical suite not claimed. Required checkpoint updater succeeded; backup PROJECT_ATLAS_MASTER_ROADMAP.txt.checkpoint-20261019-000918-0dfe4e22.bak exactly equals pre-Q bytes; checkpoint exact read-back/history bytes verified. Q canonical SHA256 at closure2f52f6106d973db27feb5386d78e7f1b439e3e423d3d5ef1bd2c2d31c98e8732. logs/diagnostics/r7e47q-20261018/result.json is final evidence. This preflight will create its own verified checkpoint, preserving Q history/report/evidence.

Additional timing fact from launcher review: Uvicorn is passed --timeout-graceful-shutdown20 BEFORE application's shared20s teardown stage. Together these cannot imply Windows manager30s will always succeed; no timeout changed and no runtime acceptance claimed.

## Exact launcher and invoked chain

Read-only WScript.Shell inspection at 2026-10-19T09:09:46.9324289Z (04:09:46CDT/05:09:46EDT). Only four explicitly named Atlas shortcuts in known Desktop locations were considered;3found, no unrelated shortcuts read. Operator reply confirms normally clicking Project Atlas.lnk.

| Shortcut | Exact target | Arguments | Working directory |
|---|---|---|---|
| Atlas Background.lnk | C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe | -NoProfile -ExecutionPolicy Bypass -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1" | D:\Work\Project Atlas |
| Project Atlas.lnk | D:\Work\Project Atlas\ATLAS.bat | (none) | D:\Work\Project Atlas |
| Stop Atlas.lnk | D:\Work\Project Atlas\ATLAS-STOP.bat | (none) | D:\Work\Project Atlas |

Project Atlas.lnk -> ATLAS.bat -> WindowsPowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/Atlas-Launch.ps1 -> immediate ATLAS_LEGACY_LIFECYCLE_BLOCKED/exit1. Batch then calls legacy Atlas-Stop.ps1, which immediately throws the matching safety block. Neither path is a certified background start. The unreachable legacy implementation is not approved; do not remove its guards. Stop Atlas.lnk ->ATLAS-STOP.bat -> blocked legacy stopper, followed by a misleading batch success message. Do not use that stop link either.

**Supported manager-delegating path:** C:\Users\renal\OneDrive\Desktop\Atlas Background.lnk -> C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1", workdirD:\Work\Project Atlas. Controls -> Ui.psm1 -> verified manager Start/Status/Stop, normal button or explicit Gaming button. GUI initially starts disabled, no automatic Start/Status callback; status request required. Gaming sets true; normal start does not forcibly clear inherited Gaming environment. Future actual process settings still require verification. Manager forces extended-hours false absent the separate explicit opt-in; GUI has no research activation argument.

This path is architecturally supported, **not permission to launch now**. Manager Status has stale-record recovery/archive behavior, so it was deliberately not executed during this read-only audit. Current metadata was inspected directly instead.

Smallest proposed correction if keeping the familiar Project Atlas label: after explicit approval, preserve original .lnk bytes/hash, change only that link target to the same absolute PowerShell executable, arguments and working directory as Atlas Background, verify metadata without launching; rollback restores original bytes but does not approve using the legacy path. No batch/PowerShell source edits or shortcut changes now. Alternatively use existing Atlas Background later, with no shortcut edit, only after startup prerequisites and approval. Exact shortcut hashes remain in windows-readonly.json and were reverified unchanged.

## Fresh runtime, ownership and protected-state evidence

Atlas-root-filtered process query succeeded:0processes; listener query succeeded:0port8000listeners. Configured lifecycle owner/start/stop/recovery locks, runtime manifest, stop request and Complete Shutdown receipt are all absent. These combined observations support **Atlas stopped at the observation**, not just inference from a free port. Root-qualified process census cannot establish exclusion of arbitrary external writers or prove relative-command standalone utilities absent.

Proposed production inspection registry logs/runtime/inspection-control absent. Absence is not authenticated recovery clearance: prior shared-fence/storage/authority contracts remain isolated/unprovisioned and not integrated into all startup paths. No initialization, reset, recovery, mutex acquisition or uncertainty clearing occurred. Any later unknown owner/lock/receipt/fence must refuse startup; normal clean-state checks never authorize bypassing uncertainty.

Docker at 2026-10-19T09:10:40.356345+00:00 (2026-10-19T04:10:40.356345-05:00): contextdesktop-linux, endpointnpipe:////./pipe/dockerDesktopLinuxEngine; Engine unavailable. Exact failure:

failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.

Stopped Docker-dependent inspection immediately. **PostgreSQL/Redis current status, immutable IDs, health and Compose identity NOT VERIFIED**, not claimed EXITED/healthy from historical data. No other context selected, no Engine/Desktop repair/start, no containers inspected or operated, no volume data accessed. When separately made available, revalidate exact project/service/workdir/compose-file/immutable IDs before any later dependency start. Current manager supports exact atlas/projectatlas labels but creates missing services with project-nameatlas; historicalprojectatlas resources must never be silently migrated/recreated.

## Configuration, authority and simulation

Typed non-secret settings read only through the settings loader; full environment/model/credentials not printed. backend/.env preferred over root/.env, both exist and were stat-verified unchanged. Validation of non-placeholder runtime configuration PASS in inspector; this is not actual API-process environment or database connectivity. Source policy and safety boundaries checked without importing the application lifespan.

- Perp micro enabled=true; PAPER simulation=true; discovery60s normal, management8s. Gaming=false in inspected configuration; explicit Gaming source would impose>=180s discovery, preserving8s management.
- Quality Dips=true, auto_paper=true, scan interval60minutes. Investment scan=true/open900s/closed21600s, with existing C1-C4 calendar-aware wake; current combined-release C1-C4 scope remains unapproved. No scanner behavior/activation altered.
- Automatic Discord high-level settings=true do **not** grant delivery: both central automated senders return False as their first executable statement. No bot connection/message, subscription/outbox mutation or production gate activation. Other manual command responses are not certified by this central-sender check.
- Manual investment/perp APIs remain MANUAL_ONLY for real brokerage; PAPER mirror reports PAPER_ONLY/no live-capital/automatic-real-money authority. Prediction constants LIVE_EXECUTION/LIVE_CAPITAL_ALLOWED/AUTOMATIC_REAL_MONEY_EXECUTION allFalse; pre-event exit policy and1position remain. No real-capital path enabled.
- **Simulation is not globally manual-only.** Perp and equity PAPER lanes can simulate automatically when their evidence/session/risk gates pass. Manual setup PAPER mirroring is another automatic background task. Equity book fills are cash-session gated. The inspected prediction automation explicitly blocks unattended/new automatic PAPER opening and retains auto-flat management. A readiness flag is not authorization to remove that gate.
- Past approved runtime acceptances were bounded runs; this request authorizes preflight, not a new unattended session. No fresh blanket unattended PAPER authorization inferred. A future approved start needs an explicit lane/session/duration and existing risk/data/reconciliation checks; no new cap/strategy authority implicit.

## Providers and premarket coverage

Source configuration: Hyperliquid public REST/WebSocket for crypto/perps; Robinhood RHJ underlying bid/ask plus classic quote fallback and Yahoo/yfinance one-minute prepost/history/fundamentals for equities. No provider endpoint called. Runtime config validation cannot establish subscription entitlement or usable/current quotes.

Cached R7E46S/O provider evidence still lacks established applicable Yahoo automated-access/redistribution permission, classic RH allowance and all-consumer HTTP budget. RHJ cached documentation60req/s/15scache is not proof of current account/data rights. Shared internal3workers/provider6combined,5logicalstarts/s,64queued/provider/64symbols and30squote acceptance are not a global wire-request entitlement. No fresh legal/terms/account approval asserted or inferred from public access. Source-only package license is distinct from market-data rights. Personal/PAPER use does not automatically establish vendor permission. Review applicable intended-use records, not a blanket commercial-waiver assumption.

At 2026-10-19T04:13:12.223130-05:00 / 2026-10-19T05:13:12.223130-04:00, the local calendar says MARKET_CLOSED for cash session. Source-scheduled regular open today09:30EDT=08:30CDT, close16:00EDT; not independently checked for an unscheduled closure. Cash scanner regular-open schedule does not establish premarket monitoring. Quote fallback can request prepost data, but dedicated extended-hours research is disabled by manager default and remains production NO-GO; no opt-in authorized. Therefore stock premarket collection/PAPER readiness is **NOT established**. Crypto/perp continuous source support is not proof of an active fresh feed while stopped. No fake telemetry/candles/fills substituted.

## Startup gate and safe next steps

| Check | Decision |
|---|---|
| Q offline corrections/checkpoint | PASS isolated, not runtime acceptance |
| Usual Project Atlas shortcut | BLOCKED legacy chain |
| Existing Atlas Background delegation | PASS source/metadata only |
| Atlas stopped/known lifecycle records | PASS read-only observation, no global writer proof |
| Docker Engine/dependency ownership/health | BLOCKED/unverified |
| Runtime config validation | PASS inspector only |
| PAPER/live/Discord source restrictions | PASS source scope; no live observation |
| Unattended lane/session authorization | NOT AUTHORIZED by this preflight |
| Stock premarket activation/coverage | BLOCKED |
| Current provider rights/wire budgets | BLOCKED/unverified |
| Current candidate startup/shutdown/resource/data acceptance | BLOCKED, no real run performed |

Overall **STARTUP NO-GO**, all21production release decisions unchanged5scopedPASS13BLOCKED3NOT_TESTED. Do not run either launcher now; no executable startup instruction or approval request is issued while mandatory prerequisites fail. The safe future launcher is Atlas Background, not the familiar legacy link.

Next smallest steps: operator independently makes intended Docker Desktop Linux Engine available; separately authorize read-only exact-container recheck. Choose existing Atlas Background or approve only the familiar-link redirect. Explicitly settle intended personal research/PAPER lane scope, cash C1-C4 inclusion/provider allowance and no extended-hours opt-in. Then separately approve one bounded startup/live-data/PAPER-risk/reconciliation/actual-cadence check before any unattended-session decision. No institutional authority replacement/VPS needed to do unrelated offline work; no recovery fence bypass is ever allowed.

## Development and validation

Offline source/tests/docs may continue in isolation while stopped. If later running, preserve its PID/run/owner, loaded-source identity, provider/data state; no reload/restart and no writes to protected data/config. Current services can import source lazily, so prefer a separate isolated checkout or copied test source for further behavior edits; do not assume disk edits are invisible to a live instance. Creating that checkout or integration is not performed here. No source correction was made during this preflight.

Launcher/ownership regressions run against copied Q source with fake process/Docker and no live service access: **54passed,0failed,0skipped;11.93s**. Six launcher/control modules hash-match current sources. Q309 results are reported separately, not added into a new coverage total. Central sender AST denials and legacy block guards validated; shortcut hashes/env file metadata unchanged. WindowsPS5.1 read-only metadata inspected; no application or manager script action run. Docker availability failure is a real preflight blocker, not a unit-test failure. Original evidence and all working changes preserved.

Required checkpoint updater and independent backup/read-back/outside-managed preservation verification recorded in result.json. No Git staging/commit/push/reset/delete, Genesis access, production source/config/ACL/shortcut/lifecycle change, provider request, real-volume inspection/backup/restore, live trading or automatic Discord. This execution stops at startup decision gate.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

