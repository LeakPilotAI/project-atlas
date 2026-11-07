# R7E47A — real-volume helper acceptance preflight

**Preflight and isolated review completed; real-volume inspection BLOCKED; production NO-GO.**

Verified at 2026-10-18T07:04:57.676874-05:00 (America/Chicago). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Existing tracked/untracked changes and historical evidence preserved. Read latest managed checkpoint, permanent strategy/recovery contract, Y implementation/conditional package, Z Linux report/addendum and helper/policy source.

## Fresh runtime evidence

Supported manager Status reports STOPPED; no top-level active lifecycle JSON/lock/tmp records. Docker read-only availability failed: `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.` Docker-dependent inspection stopped. No Docker startup attempted. Current database/container/image state is UNKNOWN, not inferred EXITED from old evidence.

Expected historical identities, requiring fresh validation:
- PostgreSQL: c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1; projectatlas/postgres; projectatlas_atlas_pgdata at /var/lib/postgresql/data.
- Redis: 13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193; projectatlas/redis; projectatlas_atlas_redis at /data.
- Helper manifest: sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574. Local lock/source hash matches; imported image verification is BLOCKED. Z imported-image/Linux results are historical evidence only. No import, rebuild, image execution or real-volume mount.

## Independent launch-plan assessment

policy.py is deliberately NON-EXECUTABLE and requires separate approval. It validates exact frozen container IDs, Compose project/service/root/single configuration/nononeoff labels, one expected mount and volume ownership/CreatedAt/local driver/options/mountpoint, exited PID0, STOPPED backend, pending=false, exact exited consumer list, ordered evidence at most 5 seconds old, exact pinned manifest and source hash. Missing optional StopSignal is not an admission requirement.

The Y package, Z addendum and plan specify one verified source per helper, sequentially: exact readonly volume-nocopy at /inspection; no other mounts/socket/host root; no privileged/host network/host PID; cap-drop ALL, no-new-privileges, rootfs RO, network none, default seccomp, user0:0, no capability upgrades. CPU0.25, RAM128MiB, RAM+swap128MiB, PID16, nofile64, restart=no, pull=never, auto-remove=false; entrypoint python3 -I -B /opt/atlas-inspector/helper.py postgres|redis. Metadata output <=65536 bytes; entries100000/depth32, internal alarm30 seconds and observer40 seconds. Regular source files (including configuration and database payloads) are never opened. Directory descriptors, stat/readlink and /proc/self/mountinfo are used; unknown names/targets are hashed. Metadata can still be sensitive.

Finding: normalized verify_controls does not itself verify seccomp/host PID, output capture limits, host observer, lifecycle lock or continuous exclusive access. Pull/deadline/output are plan/orchestrator obligations, not all Docker normalized fields. This is an execution-adapter gap, not proof of bypass in a production path: no production executor exists. No current launch command is approved. A future reviewed wrapper must validate actual full Docker controls and exact created helper identity before start, with bounded output capture. It must recheck sources by exact immutable ID and volume fingerprints, not names alone; absent sources must fail before creation, never silently create a volume.

## Deadline and concurrency reconciliation

A safe authorization can be narrower than guaranteed completion: one metadata attempt with incomplete/permission-denied/timeout outcomes accepted as failure. SIGALRM and resource limits do not guarantee a hard wall-clock exit during kernel D-state, daemon failure or stuck storage. At40 seconds classify UNCERTAIN, retain exact helper/operation evidence and writer/start prohibition; do not retry, start the second helper, release the operational fence, terminate Docker or signal processes automatically. Independent exact-ID status reconciliation and explicit recovery approval are required. If a guaranteed40-second exit is mandatory, this method remains BLOCKED.

Read-only mounting constrains this helper; it neither excludes other writers nor produces a crash-consistent snapshot. Named volume identity lacks atomic compare-and-swap against a privileged replacement. Five-second before/after checks detect some drift but are not a continuous fence. Operator-exclusive no-start/no-write/no-replacement control plus supported Atlas lifecycle serialization must be demonstrated for the entire operation; if it cannot be, do not run. Do not invent a lock as proof against privileged actors. Kernel/cache/atime/device zero-write guarantees remain unestablished.

Production UID/readability is unknown. User0 with dropped capabilities may fail on PostgreSQL0700; accept safe failure. No automatic UID switching, capability additions, chmod/chown, config reads or alternate tooling. Partial results, external references and invalid output cannot establish storage coverage or capacity. Effective configuration remains NOT_ESTABLISHED.

## Gate matrix

| Gate | Decision | Required evidence |
|---|---|---|
| Atlas manager/lifecycle preflight | PASS | Fresh STOPPED and no active records |
| Docker availability | BLOCKED | Operator independently makes Engine available; separate read-only recheck |
| Exact DB ownership/state/volume consumers | BLOCKED | Fresh exact IDs, EXITED PID0, mounts/labels/CreatedAt/options and no active consumers |
| Imported image | BLOCKED | Fresh native image ID/descriptor/config/rootfs/source verification |
| Existing plan and synthetic helper contracts | PASS within isolated scope | 50 host tests; Z historical Linux evidence; no production claim |
| Reviewed real execution wrapper/full controls/output | BLOCKED | Isolated adapter acceptance and pre-start actual-control checks |
| Exclusive writer/replacement/lifecycle window | BLOCKED | Demonstrated supported fence plus explicit operator control |
| Uncertain helper retention/recovery authority | BLOCKED | Explicit policy, ownership and no-start continuation on uncertainty |
| Production permission/output handling | NOT TESTED | Restrictive existing output location, no ACL changes, safe permission-failure acceptance |
| Real-volume coverage/capacity | NOT TESTED | Separately approved bounded attempt; partial results stay incomplete |
| Backup/restore/production lifecycle | BLOCKED/separate | No authorization in this milestone |
| Other release gates | BLOCKED/unchanged | Cash scope, provider rights/HTTP/stuck workers, Ruff disposition, clean-machine/runtime/Gaming, shortcuts, E136/Discord, PM-V2 |

## Validation and scope

50 passed, 1 skipped, 0 failed in0.51s (tests/test_r7e46y_volume_inspector.py). Skip: Linux-specific native descriptor test on Windows; previously passed exact body in Z Linux, not rerun here. Targeted Ruff PASS. Five Python files compiled in-memory without execution/bytecode output. Local helper source matches pinned lock. Git diff and checkpoint preservation checked at finalization. No full canonical or Linux container rerun; prior failures and inherited lint debt not waived.

No runtime source changes. Only new documentation/diagnostics and mandatory roadmap checkpoint. No service lifecycle, production helper/mount, Genesis access, payload/secret reads, backup/restore, production ACL/shortcut changes, trading/Discord activation, Git stage/commit/push/reset or cleanup. PAPER_ONLY/MANUAL_ONLY and permanent low-resource Gaming objective with normal PAPER management cadence remain.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Additional current core work: restore Docker availability independently; finish read-only identity/image verification; implement/review isolated real-operation admission/fence/observer/output contracts; resolve explicit bounded-failure and permission decisions; then seek separate one-time metadata authorization. Backup coverage/capacity/destination/encryption/key recovery, real backup, isolated restoration, Complete Shutdown and shortcut acceptance remain separate.

Next safest proposed milestone: R7E47B isolated real-volume execution-adapter and operational-fence contract acceptance, with fresh read-only Docker verification if independently available. No real helper, lifecycle or backup operation implied. Requires separate authorization.
