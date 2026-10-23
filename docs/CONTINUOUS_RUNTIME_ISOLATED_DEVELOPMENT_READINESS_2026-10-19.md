# Continuous runtime, isolated development and market-session readiness

**Design/readiness milestone complete. Profile A NO-GO; Profile B NO-GO; production release NO-GO.** No session, worktree, runtime release or production integration was created. This report incorporates the preceding market-session decision request and the subsequent continuous-runtime workflow request. Date: October 19, 2026, America/Chicago (CDT, UTC−05:00). Exact observation and verification times are retained in `logs/diagnostics/market-session-decision-20261019`.

The shortest proposed path is a bounded **observation-only candidate with a fixed runtime boundary**. Broader PAPER corrections remain a separate workstream. This decision does not require completing SaaS or institutional security phases before any future observation trial; it does require the safety and provider conditions applicable to that trial. No existing gate has been waived.

## Fresh read-only state

| Check | Actual evidence | Meaning |
|---|---|---|
| Atlas processes | Final census completed 2026-10-19T10:17:59.4514689Z / 05:17:59 CDT: zero Atlas-root-associated processes after excluding the independently identified inspection parent shell. | Supports Atlas STOPPED within the known root at observation, not exclusion of arbitrary external writers. First census included that shell; original result retained. No processes killed or managed. |
| API listener | Port 8000 had no listener; query succeeded. | No running API readiness; unused port alone was not used as proof of stopped ownership. |
| Ownership/lifecycle records | Owner/start/stop/recovery locks, runtime manifest, stop request, Complete Shutdown receipt and proposed `logs/runtime/inspection-control` absent. | No retained known manager operation found. Missing proposed protected registry is **not authenticated admission or recovery clearance**; all-entry admission remains unprovisioned/unintegrated. Manager Status was not invoked because it can reconcile records. |
| Manual publication metadata | Only `perp_manual_state.json` matched the narrow store-name metadata query; 1,108 bytes, last modified 2026-10-16T14:18:30.7541709Z. No matching pending/temp publication file found. | Payload not read. No conclusion about contents, PAPER exposure or full integrity. Absence of this store's pending file is not global clean-state proof. |
| Docker | 2026-10-19T10:17:19.185455Z–10:17:25.569617Z: intended `desktop-linux`, `npipe:////./pipe/dockerDesktopLinuxEngine`, Linux Engine 29.8.1, ID `1b4f668e-97b1-4e02-8647-454cf431e1b2`. Before/after projected Engine observations equal; no environment override. | Engine available. This does not prove daemon-generation continuity or writer exclusion. No alternate context selected. |
| PostgreSQL / Redis | Exact immutable IDs, images, `projectatlas` service labels, work directory and Compose file match retained evidence. Both EXITED, running false, PID 0, exit 0; retained health label unhealthy. | **Dependencies NOT READY.** Cached unhealthy labels are not fresh probes while exited; no credential/database/health-log inspection performed. |
| Familiar shortcut | Project Atlas still targets PowerShell `-NoProfile -ExecutionPolicy Bypass -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1"`, work directory `D:\Work\Project Atlas`. SHA-256 `52B027D49FAAEAE779E195DF15ECAE42EC0FF3C10384894354383582D471626E`. | Repaired delegation remains valid; it opens a passive control panel, not an observation-only runtime. No execution or Save. |
| Stop Atlas | Still points to `ATLAS-STOP.bat`, whose legacy stopper is blocked. | **Do not use.** Safe complete-stop migration and real acceptance remain outstanding. Atlas Background shortcut unchanged. |

Exact dependency IDs:

- PostgreSQL: `c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1`; image `sha256:d8336a5c9cc49bdbf1e935234e8c87ab64b6d6d195fd2ecedff7b00185557631`.
- Redis: `13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193`; image `sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99`.

Ownership includes exact service `postgres`/`redis`, project `projectatlas`, working directory `D:\Work\Project Atlas`, config `D:\Work\Project Atlas\docker-compose.yml` and one-off false. Names alone were not accepted. Only Atlas Compose-label candidates were queried; no unrelated project, Genesis resource, database payload or volume content was inspected.

## Two separately authorized profiles

| Contract | Profile A — observation-only | Profile B — bounded PAPER |
|---|---|---|
| Allowed work | Explicitly permitted market feeds, bounded collection, read-only research and a dedicated append-only observation/session history. Collection necessarily writes its authorized observation store; it does not mutate trading/recovery history. | A plus explicitly approved simulation lanes, instruments, duration, action authority and immutable execution assumptions. |
| Denied work | All PAPER order creation and prediction opens; live orders; automatic Discord; recovery clearing. Proposed minimum also excludes PAPER management/bootstrap/session-roll/shutdown-interruption writes so old simulated positions are not altered by an observation run. | No live orders, automatic Discord or recovery clearing. No unattended scope inferred. Selected manual/automatic simulation behavior must be separately explicit; excluded lanes remain denied. |
| Persistence | Observation/session writer must have a validated acknowledgement/commit boundary and unclean-exit refusal. No full-system durability claim. | Every participating ledger, pending-limit, risk snapshot, manual snapshot and prediction store must pass its required boundaries and ambiguous-retry tests. R fixed two stores, not all stores. |
| Current decision | **NO-GO.** No enforced observation-only profile or safe all-entry admission exists in the production launcher/API. Default startup has PAPER side effects. Provider permission/budget and dependency readiness are not established. | **NO-GO.** Inherits A blockers; no new lane/session authorization, incomplete participating-store durability, cross-store replay/risk acceptance and current-candidate runtime acceptance. |
| Smallest correction | Offline allowlisted observation bootstrap/capability proposal, fixed runtime/data path contract and tests; then separately approved admission/integration and bounded runtime acceptance. | Keep pending-limit/prediction durability separate, inventory the selected lane's complete stores, prove risk/replay/persistence and obtain explicit session scope. Do not enable all PAPER lanes by default. |
| Premarket equities | Not currently accepted. Pre/post quote capability is not continuous premarket collection. Dedicated extended-hours research remains disabled by default; cash C1–C4 scope and provider gates remain unresolved. Initial candidate should exclude equities unless their separate gates pass. | Same market/session restrictions plus simulation scope, fill evidence, costs and persistence. No premarket PAPER approval implied. |
| Repaired launcher | Correctly delegates existing manager, but has no profile argument or isolation policy. Current Start/Gaming Start cannot enforce A. | Can invoke normal existing startup only after separate prerequisites/approval; cannot currently enforce a narrowly approved B scope. |
| Concurrent development | Conditional future GO only with an accepted fixed release and disjoint development/test resources. Editing today's active checkout would not be isolated. | Same isolation plus all selected PAPER store/risk gates; currently NO-GO. |

These are proposed session contracts, not new authorization. PAPER_ONLY/MANUAL_ONLY limits real-capital authority; it does **not** mean every current PAPER lane is manual. No existing simulated position may be silently closed, reset, recovered or declared managed by Profile A. Any need for management must be explicitly reconciled and authorized separately.

### Concrete source/configuration blockers

Current `main.py` imports PAPER-capable singletons before lifespan admission, hydrates runtime, calls `paper_journal.bootstrap_session`, starts the micro coach, manual service and alert/PAPER mirror, prediction automation, investment scanner and other services. Startup bootstrap can append session/roll records. Shutdown also has PAPER reconciliation/interruption paths. `perp_alert_delivery.paper_once()` runs its mirror independently of the micro PAPER flag. Disabling only `PERP_MICRO_PAPER_ENABLED` is insufficient.

Typed, non-secret configuration inspection at 2026-10-19T10:17:15.768976Z confirms micro PAPER enabled, Quality Dips auto-PAPER enabled, investment and accumulation enabled; Gaming false, normal discovery 60 seconds and PAPER management 8 seconds. Settings validation passed in the inspector, **not an API process**. No credentials or whole environment were printed. High-level Discord flags are true, but both central automated sender entry points remain denied; Profile A must also avoid starting the bot/manual command dispatcher and any independent notification transport. Prediction live-execution/live-capital/automatic-real-money policy constants remain false; pre-event exit and one-position safeguards remain.

Provider configuration does not establish applicable data rights. Existing provider-rights gate remains BLOCKED. The quote dispatcher has one-process logical concurrency/pacing, not verified all-consumer wire-level entitlement. Hyperliquid has separate REST/WS/cache/candle paths: the 25-second ticker cache and reconnect/backoff do not prove an aggregate weighted request budget. Robinhood/Yahoo fallback, library internals and independent clients are not collectively covered by that cache or the quote singleton. No external feed was contacted or permission inferred from public access. A future single-provider crypto observation scope may reduce dependencies, but that provider's actual usage/retention allowance and aggregate request budget must first be evidenced. No unsupported numeric entitlement is invented.

The existing manager expects the Engine already available, restores only verified dependency identities and waits for health. Its absent-pair creation branch uses project `atlas`, while current resources are `projectatlas`. Missing resources must never be interpreted as permission to create empty replacement databases. No startup or creation policy changed. Current proposed protected admission registry is absent and production enforcement is unintegrated; this is distinct from a live UNCERTAIN record. Actual ambiguous state must always refuse. Do not import uncertainty from isolated fixtures, and do not reinterpret missing admission evidence as a successful check.

## Stable runtime boundary

**Git commit identity alone is insufficient:** this candidate has required untracked and modified sources, including R's durability helper. `git archive HEAD` would omit required work. A source archive from an earlier milestone does not certify the current release.

Proposed layout, subject to separate path/provisioning approval; **none created**:

| Resource | Proposed boundary |
|---|---|
| Fixed release | `D:\AtlasRuntime\ProjectAtlas\releases\<content-id>` outside the development checkout and its normal writable roots. Include Python sources, served HTML/static assets, launcher modules, templates, schemas, vendor companions and manifest. |
| Per-release environment | `D:\AtlasRuntime\ProjectAtlas\environments\<environment-id>`; exact interpreter/dependency/native-library identities. No shared editable installs, user site or development `.venv`. |
| Persistent state/control | Separately approved runtime state/config/session locations, independent of the release directory. Existing protected data is not relocated, cloned or reset by this design. Every mapping requires explicit acceptance. |
| Development | Separate future worktree such as `D:\Work\Project Atlas Dev\<task>` with its own environment, build output, caches and disposable tests. No worktree created now. |
| Runtime selection | Explicit approved content ID selected for the **next startup** by a stable reviewed bootstrap. No mutable `current` target followed during a run and no user-controlled fallback search path. |

A release manifest must cover the complete source/static/dependency closure, path mappings, safe configuration fingerprint, schema compatibility, accepted profile, provider scope and evidence. Verify bytes and reject symlinks/junction escapes/hard-link sharing with mutable development resources. Hashing once does not prevent replacement after verification: accepted operational write protection and development sandbox boundaries are required for the run. This milestone does not prove native permission enforcement or protection against privileged administrators/full-machine compromise.

The runtime interpreter must import only the pinned release/environment; no cwd fallback, development `PYTHONPATH`, user-site package leakage or auto-reload. Frontend responses must serve the pinned assets, not files rebuilt in the development tree. Bind the actual API PID/run ID to release/config/profile fingerprints. Runtime writers use explicit state paths, never paths accidentally inferred from the new code location.

**Existing relocation blockers:** manager `$Root` derives from its script location; settings select `.env` relative to package/repository; journal/manual state and investment storage derive `backend/data` from `__file__`; dashboard files are served from repository-relative paths. Copying current code elsewhere unchanged can select empty/new state or wrong configuration and invalidate Compose working-directory ownership. An accepted path contract and exhaustive write-capable import audit are needed before installation. Do not solve this using junctions, hard links, copying production databases, or silently changing ownership labels.

## Shared-resource risk inventory

| Shared risk | Required isolation / acceptance |
|---|---|
| Python imports and packages | Fixed release plus independent environment; prohibit editable references, user-site/cwd fallbacks and pip changes to active environment. Test delayed imports after development changes. |
| Frontend builds/templates/assets | Separate build/cache/output roots; runtime serves hashed fixed outputs for the entire session. A browser refresh must not load development replacements. |
| Configuration/environment | Separate approved runtime configuration and explicit allowlisted environment. Fingerprint non-secret effective settings; never dump credentials. Dev `.env` must not resolve to production. Normal/Gaming flags must be explicit. |
| Database/schema/migrations | Production DSNs never available to tests; disposable databases only. No startup migration or schema DDL in observation profile without specific acceptance. Current `create_all` is not a migration/recovery contract. Promotion requires backward-compatible accepted schema or separately approved maintenance. |
| Docker dependencies/volumes | Fixed exact Atlas identities, never broad names. Dev tests use mocks now; future disposable resources need distinct labels/projects/volumes and separate approval. No test access to production mounts or Docker socket. |
| Journals/manual/pending/risk/observation state | Explicit roots; tests deny production paths. Shared history must not live inside a replaceable release. Required sidecars/intents and checkpoints belong to the same documented recovery scope. |
| Locks/admission/recovery | One accepted production coordinator; isolated test locks in test roots. Tests cannot initialize, clear, copy or consume production grants/intents. Startup races and unknown state refuse. |
| Providers/caches | Development uses deterministic fixtures and blocked live provider access. Separate test caches; runtime-wide per-provider wire budgets, bounded queue/deadline/retry and freshness. A second process must not silently double the budget. |
| Ports/listeners | Production loopback binding owned by exact run; tests do not reuse port 8000 or production endpoints. Separate test ports only when separately needed; source isolation alone is not network isolation. |
| Git worktree metadata | Separate checkout/index/build state helps, but worktrees share repository objects/refs. No branch/reset/cleanup affecting the active release; no runtime dependency on a working branch. Worktree creation does not freeze current dirty sources or isolate databases/environment. |
| Filesystem aliases and tooling | Reject shared mutable file identities; restrict development writable roots away from runtime/state, including test subprocesses. AGENTS instructions/path names alone are not an OS barrier. Native enforcement must be tested before a safety claim. |
| CPU/RAM/disk/provider contention | Shared workstation still has shared hardware. Bound test concurrency and scheduling; no heavy build/load tests during gaming without approval. Gaming CPU/RAM/cadence and disk-capacity acceptance remain separate; isolated paths do not eliminate contention. |

For today, offline source/test/docs work can continue using copied application source, temporary state and no provider/service access, as R demonstrated. A future running session must **not** load code/config/assets from the checkout Codex edits. No one-click promise is made until that separation is accepted.

## Promotion contract

Development → isolated tests → complete content-addressed candidate → independent acceptance → explicit operator approval → verified stopped-window selection → **next startup**.

1. Preserve existing work and assemble an exact candidate including required untracked sources; no staging or commit is required to define a hash-complete candidate, but provenance must record dirty inputs truthfully.
2. Run isolated persistence/profile/admission/path/provider/shutdown tests and verify dependency/license completeness. No production DSN, volumes, hooks or reload.
3. Validate native path/write restrictions, clean installation and the approved profile against disposable resources. Runtime acceptance is a separate authorization, never performed implicitly by a build.
4. Operator approves exact candidate, profile, schema/state mapping, provider scope and acceptance evidence. A policy document, green test or shortcut click is not permission to reset state or enable PAPER.
5. While a session is active, prepare candidates only in a separate staging area. Do not update its release directory, environment, config, frontend output or selected source paths. Promotion cannot replace a running process.
6. Under separately approved stopped-state controls, verify actual exit and admission evidence, then install/select the accepted next release. No automatic schema migration, deployment, hot reload or restart. Rollback must prove schema/state compatibility and preserve pending evidence; reverting code cannot clear a recovery fence.

## Durable session history

Proposed session ledger is separate from PAPER performance and protected recovery authority. Required fields: unique session ID; release/environment/config/profile fingerprints; exact manager/API run identity; UTC wall-clock start/end observations and monotonic durations; feed/instrument/session permissions; provider freshness/gap/error counts; durable observation sequence/hash references; journal checkpoint/intent references; shutdown outcome and unresolved work. Credentials and confidential raw payloads never enter ordinary audit output.

Use prepared → admitted → starting → ready → quiescing → backend-drained → backend-exited → selected-dependencies-stopped → terminal outcome events. Preserve every prior session; append a new identity, never reset history to make the dashboard look clean. Readiness requires actual API/data checks, not just a successful HTTP response. Profile A reports no PAPER actions authorized, not invented zero-profit trades.

Observation records distinguish provider event time, request start/end, receipt time and committed sequence. Preserve missing fields as unknown, and distinguish live capture from any explicitly approved backfill. An in-flight observation is not committed until its validated acknowledgement boundary succeeds. PAPER outcomes under a future B scope reference actual fills/fees/slippage/funding and stable action identities; signals without fills remain separate.

A normal shutdown closes new-work admission, drains owned bounded work, confirms observation commits/checkpoints, closes clients, and records a run-bound outcome. Manager verifies application acknowledgement **and** exit before selected dependency shutdown, then durably publishes the final session outcome before presenting COMPLETE. No writer may append observations after final confirmation. INCOMPLETE, TIMED_OUT and UNKNOWN retain actual pending work and evidence; a log line or missing PID is insufficient.

An unclean exit leaves a session without a verified terminal event. Next startup must reconcile ownership, committed observation boundary, pending publication and required resource identities before new writes. Missing end time remains unknown; do not synthesize a graceful end or assume absent data was never committed. A pending manual snapshot or protected UNCERTAIN condition remains refused until its separate authorized recovery contract is satisfied. Observation/profile isolation is not recovery authority.

Independent backup and isolated restoration remain unaccepted. Successful fsync or atomic replace is not certification against Windows directory-entry loss, device/controller failure, full-machine rollback or lost volumes. R's 420 isolated passes are historical regression evidence, not runtime power-loss or backup acceptance. No archival deletion/retention policy is activated here.

## Target desktop experience

- **Project Atlas:** reviewed stable bootstrap, explicit accepted observation profile, exact stopped/admission checks, intended Engine check, approved dependency restoration, exact release launch, data/profile verification and truthful READY/DEGRADED/FAILED reporting. Docker must already be available for the minimum path; automatic Desktop launch needs its separate shared-Engine policy and approval. Never restart or terminate Docker Desktop/Engine.
- **Stop Atlas:** exact active run, close ingress/drain/persist/verify application outcome and exit, then graceful stop of explicitly selected verified Atlas dependencies. Preserve Docker Desktop/Engine and all persistent data. Truthful four-state result and retained interrupted receipt; no force kill or global cleanup. Backend-only developer stop is a distinct explicit operation, not the ordinary operator button.

The familiar Project Atlas link is already repaired but currently points into the editable checkout and cannot select the proposed profile/release. Stop Atlas is still unsafe legacy guidance. No shortcut, stable bootstrap or production manager path was modified in this milestone. Future migration needs explicit approval, backup and non-executing target validation, followed by separately authorized real acceptance.

## Minimum viable execution and blockers

| Order | Bounded work | Exit condition / authorization boundary |
|---|---|---|
| 1 — next recommended | Offline observation-only bootstrap/capability and runtime-path contract prototype in copied source. All other services/routes are denied by allowlist; no eager PAPER imports/bootstrap/management/shutdown writes, prediction opens, bot or broker transports. | Fake-provider tests show zero forbidden actions at import/start/API/shutdown; explicit fixed code/config/state paths, no cwd/default production fallback. **No production integration** in this step. |
| 2 | Select one minimal permitted feed and test whole-profile request accounting, freshness and observation commit/replay. Provider allowance/retention and actual aggregate wire budget require specific evidence. | No public-endpoint/credentials/PAPER-use assumption; no live request before authorization. Start without equity/prediction lanes if their scope is unapproved. |
| 3 | Minimal normal clean-state admission and fixed-release integration proposal; manifest includes current R files/assets/environment. Keep full uncertain recovery blocked. | Separate operator approval for provisioning/path mappings/integration; missing evidence refuses. No institutional PKI/VFS redesign required or authorized. |
| 4 | Candidate packaging, native development write-denial, session-ledger/drain tests and safe desktop migration package. | Current accepted dependency IDs remain fixed; relocation cannot create new blank stores. Separate shortcut/runtime install approval. |
| 5 | One operator-authorized bounded observation acceptance and owned graceful stop/restore trial. | Fresh ownership and DB health, actual profile/feed freshness, zero forbidden activity, committed history and truthful shutdown. Real Complete Shutdown/dependency restore and resource/cadence acceptance stay explicit. |
| 6 | Authorize a defined research-session window, then continue development only in separate worktree/environment with synthetic resources. | No active-runtime writes/reloads/migrations, no doubled provider traffic, no unintended gaming contention. Not authorized now. |
| Parallel PAPER workstream | Pending-limit/prediction journal acknowledgements; then selected risk/PaperBook stores and cross-store idempotency. | Independently accepted participating stores and explicit B scope; do not block useful A implementation on unrelated PAPER features, and do not let A enable them. |

**Single highest-priority coding blocker:** there is no enforceable observation-only startup/capability boundary. Closing that in an isolated candidate is the next smallest implementation. It does not by itself close admission, provider, state-path, packaging, shortcut or runtime gates. Both current profile decisions therefore remain NO-GO; no launch instructions or activation request is issued.

## Acceptance plan and offline results

Required acceptance before continuous operation:

1. Mutate development modules/assets after runtime fixture starts; delayed runtime imports and dashboard reads remain on pinned bytes. Real runtime write protection and subprocess writable-root restrictions require native acceptance, not a hash check alone.
2. Deny shared source/environment/state/cache/DSN/volume/port mappings, traversal/reparse/hard-link aliases, production `.env` fallback, writable release files, editable package and user-site injection.
3. Observation profile refuses every PAPER/prediction/live/Discord/recovery capability at import, service boot, API/manual commands, reconnect and shutdown; unknown/missing profile fails before side effects. Existing-position history remains unchanged.
4. Account for all provider requests, fallbacks and reconnect/backfill paths; finite queue/deadline/retry, throttling, stale/future/out-of-order quotes, no dev traffic. Terms/permission are separately verified facts, not unit-test flags.
5. Durable observation/session writes fail honestly on partial write, flush/fsync/full disk and interrupted publication; duplicate actions/observations reconcile according to explicit identity policy. A missing terminal event preserves refusal.
6. Duplicate launch, concurrent stop/start, parent/worker crash, changed container identity, absent/corrupt protected state and unavailable Engine all refuse safely. No tests imply external Docker writer exclusion.
7. Promotion during an active run refuses; candidate acceptance and explicit operator approval are bound to exact bytes. A changed/untracked dependency or schema mismatch invalidates acceptance; old evidence cannot approve new bytes.
8. Real operator acceptance separately verifies exact process config, dependency health, profile, data freshness, CPU/RAM/cadence and graceful bounded shutdown. PAPER-only live-money restrictions, provider denials and PM-V2 safeguards remain permanent.

Executed now: **19 synthetic design tests passed, 0 failed, 0 skipped**. They cover disjoint/overlapping paths, shared environment/state/ports/DB/volume rejection, denied dev-provider traffic, capability/permission/budget refusal, active/unapproved promotion refusal, copy independence, runtime-hash drift, native fixture hard-link alias identity and append-preserved synthetic session history. They do **not** implement or prove production launch enforcement, native ACL isolation, real provider rights, durable power-loss storage or runtime/development concurrency. Initial sandbox run had one hard-link permission error; failure retained. Explicitly permitted native rerun created links only between two disposable fixture files and passed. No fixture was deleted.

The Docker/process/configuration inspectors were syntax-checked and restricted to metadata/non-secret projections; exact commands and outputs retained. Prior R tests were not repeated or added to the 19. No candidate application, service, container, worktree or production-like database started. All production sources/configuration, existing shortcuts and the 21-gate matrix remain unchanged. Mandatory checkpoint backup/read-back/history verification is recorded in `result.json`.

## Unchanged 21-gate release decision

The authoritative matrix remains byte-identical: **5 scoped PASS, 13 BLOCKED, 3 NOT_TESTED**. Normal admission, full recovery, current-candidate runtime, real Complete Shutdown, safe complete shortcut workflow, backup/restore, actual HTTP budgets/rights, cash scope, stuck workers, Ruff disposition, clean-machine acceptance, gaming performance, E136/Discord and extended-hours activation remain outstanding. Historical source artifact and isolated passes are not promoted to live acceptance. Profile A's reduced scope can progress independently only through its own demonstrated requirements; no required gate is downgraded.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


## AFI continuity addendum — October 19, 2026

ATLAS FORECAST INTELLIGENCE is now an official permanent roadmap initiative. Read docs/AFI_INITIATIVE_AND_EVIDENCE_CONTRACTS.md, docs/AFI_MILESTONE_REGISTER.json and docs/AFI_OFFLINE_ACCEPTANCE_2026-10-19.md when resuming. AFI-1 through AFI-10 remain PENDING. Pure point-in-time selection, purged replay planning and scoring diagnostics are offline groundwork only; no real dataset/model/forecast skill, production integration or immutable production history is accepted. Reuse the existing Evidence Engine and Cross-Market Intelligence infrastructure. Preserve the production startup lock, all 21 gate decisions, Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY/Discord restrictions. Long-horizon projections through 2030/2040/2050 remain uncertain conditional scenarios. Existing content above is historical and unchanged.


## AFI contract/dataset continuity — October 19

Current evidence: docs/AFI_CONTRACT_DATASET_ACCEPTANCE_2026-10-19.md and logs/diagnostics/afi-contract-20261019/result.json. AFI_MILESTONE_REGISTER.json retains all ten PENDING milestones. Pure offline manifest review and dataset-bound diagnostics now supplement the prior evaluator; only synthetic daily-close 1D/5D technical acceptance exists. Historical permission declarations remain blocked, other horizon conventions and split-crossing evaluation refuse, and no model or calibrated market performance is established.

Next work must reuse existing backtest/Evidence Engine infrastructure. A bounded offline no-change/drift baseline fitter with actual training-cutoff/holdout tests can proceed on synthetic fixtures; real dataset acquisition requires separate source rights/provenance evidence. Immutable forecast history must reuse accepted durable publication rather than invent another registry. Do not remove production_startup_lock.py denial, alter the 21 gate decisions, start a service/provider, clear recovery uncertainty or infer PAPER/Discord permission. Prior continuity bytes and roadmap history remain preserved.


## Permanent autonomous continuation handoff - October 19

Read the permanent AUTONOMOUS DEVELOPMENT AND CONTINUATION PROTOCOL in the master roadmap, then docs/AUTONOMOUS_CONTINUATION_2026-10-19.md and logs/diagnostics/autonomous-continuation-20261019/result.json. Nine scoped increments were implemented and checkpointed without activating services. Resume the exact NEXT EXECUTION in that report; do not repeat completed baseline/replay/artifact work or stop after a local acceptance. Official AFI states and all 21 release decisions remain unchanged. No automatic production/PAPER/Discord/Genesis/provider authority follows from this standing directive. The remaining feasible offline work is distinct from external rights, real-data, operational and independent acceptance blockers.
