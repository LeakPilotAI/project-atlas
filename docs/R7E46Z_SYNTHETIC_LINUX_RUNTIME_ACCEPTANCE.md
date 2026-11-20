# R7E46Z — pinned helper synthetic Linux runtime acceptance

**18 synthetic Linux acceptance cases verified after correction of one fixture expectation. Production NO-GO. Real-volume execution remains separately gated.** Branch chatgpt/atlas-rebuild-v1;HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. October18,2026 America/Chicago CDT UTC-05;exact UTC timestamps and immutable synthetic IDs in logs/diagnostics/r7e46z-20261018-022818. Read latest master and Y implementation,README and approval package.

## Production preflight and scope

Supported manager STOPPED,no active Atlas lifecycle JSON/lock/temp records. Same production PG c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1 and Redis13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193,projectatlas/service/root/single Compose/nononeoff/images/mount/volume labels/CreatedAt checked read-only. Both EXITED,PID0,exit0;only expected exited production volume consumers. Final recheck and preservation evidence required;no real source mounted into any test container.

One new synthetic local volume r7e46z-c5d18d33a88e42cc-fixtures,uniquely labelled org.atlas.synthetic.operation=r7e46z-c5d18d33a88e42cc. It contains generated dummy bytes only. One initializer used this NEW volume RW to create fixtures;all inspection/probe source mounts RO,nocopy at/inspection,known subpaths. Native/nofollow tests additionally used new bounded private /tmp tmpfs. No host bind/root/Docker socket,Genesis/Atlas production volume,privileged mode or host networking. Full exact created-ID ledger retained. No --rm,stop,kill,remove,prune or down command was used. Cleanup plan explicitly retains resources.

## Image integrity/import

Recorded manifest **sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574** independently reverified:all blobs/sizes,5uncompressed rootfs diffIDs,source SHA256,entrypoint,user,environment and absence of declared image volumes. Only these verified OCI blobs were packaged/imported;no rebuild,pull,substitution or tag operation. Docker29.8.1 containerd store loaded image ID equal to manifest digest. Actual native image inspect Descriptor.digest and Id equal sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574;rootfs diffIDs and configuration/source label match artifact.

Recorded config digest sha256:218bae4bc0e60f4ea84d948ed104cf127133dc272273dc8e1f78307877456e3b is distinct from image ID in this store. Initial lookup by config digest failed;no test was started until exact manifest lookup verified. Optional Config.Volumes was absent and a manual JSON projection lacked a closing brace;both diagnostics failed closed. Native JSON for only this public helper image corrected the formatter. No digest mismatch was accepted. Imported image has no repository tags;no existing image tag overwritten or image removed.

## Actual Linux runtime cases

| Case | Verified observation |
|---|---|
| Inventory/hardlinks |5file entries,1directory,54unique logical bytes;hardlink bytes deduplicated;known layout/artifacts;no effective-config inference |
| Symlink escape |External WAL/tablespace-shaped symlinks classified blocked,targets hashed,never followed |
| Permission |Mode000 synthetic directory refused with PermissionError,exit2;capability escalation never attempted |
| Read-only source/root |Actual write attempts to synthetic source and root failed EROFS |
| Entry limit |Actual pinned core on Linux with reduced2-entry threshold reports INCOMPLETE |
| Depth limit |Reduced2-depth guard reports INCOMPLETE;separate default40-deep tree fails closed after30directories with OSError |
| Output limit |70KB generated output input becomes bounded valid INCOMPLETE/OUTPUT_LIMIT JSON |
| Malformed service |Invalid service argument refused,exit2 |
| Payload/external access guard |Python open audit recorded0fixture regular-file opens and0unapproved external opens;OS/library/kernel metadata reads explicitly allowed |
| Previously skipped native test |Exact existing test_actual_linux_descriptor_backend body extracted without skip decorator and passed inside pinned Linux image/private synthetic tmpfs;not a claim whole pytest module ran on Linux |
| CPU/security kernel evidence |cpu.max25000/100000;15throttle events during1.5second bounded work;CapEff0,NoNewPrivs1,Seccomp2 |
| PID enforcement |15children plus parent hit16PID cap with EAGAIN;all children normally reaped |
| Memory enforcement |Dedicated192MiB synthetic allocation in128MiB cgroup kernel-OOM-killed that owned container;OOMKilled=true,exit137(expected test outcome) |
| Actual helper rlimits |CPU10/10s,address space128MiB,nofile64/64;160MiB allocation refused with MemoryError |
| Native alarm |Injected blocking sleep in synthetic enumerator interrupted by actual30s SIGALRM;helper exit2/INCOMPLETE in30.407s |
| Kernel no-follow/replacement |Actual root and child symlink opens refused;normal directory inode replacement rejected |
| Observer deadline |Deliberate1s observer timeout recorded exact owned CLI uncertainty for a3s bounded synthetic workload;normal exit later reconciled without signals/cleanup |

18logical cases includes separate reduced/default depth and rlimit/nofollow tests as represented in runtime-test-results-final.json. The table groups related observations. Production entry100000/depth32 thresholds were not exhaustively stress-tested at full filesystem scale;entry/depth logic tested at reduced thresholds plus an actual over-deep filesystem. Source RO is a measured access restriction,not proof of immutable snapshot or zero host cache/atime/device bookkeeping writes.

## Security/resource evidence

Every immutable created container re-inspected BEFORE start and AFTER exit. Exact operation labels/name/image verified;actual mounts and HostConfig compared. Read-only rootfs;source RO for helpers;capdropALL;no-new-privileges;networknone;defaultseccomp;CPU0.25;RAM128MiB,memory+swap128MiB(no swap);PID16;nofile64;restartno;autoremovefalse;pullnever;user0:0. Resource/security controls verified both Engine metadata and kernel probes where applicable. Raw metadata mutation replay rejects missing labels,changed ID/image,wrong resources,RW/extra/source/socket mounts,privilege/cap/hostnetwork/hostPID and malformed booleans. Optional StopSignal absence accepted;optional ReadOnly=false omission applies only initializer with mandatory actual RW check,never makes inspection mount RO by inference.

No code changed inside the pinned helper or its image. README/lock runtime-attestation metadata updated only;runtime_verified remains false for unrestricted/production use,synthetic_runtime_verified=true. No production execution authority introduced. One execution's orchestration/probe code lives in diagnostics,not Atlas startup.

## Failures and exact test disposition

Initial native run:13passed/1failed assertion. Initial expected logical bytes53 was a test-fixture arithmetic error:three unique SYNTHETIC9byte files plus27byte SYNTHETIC_NOT_CONFIGURATION=54. Helper correctly reported54. Original failure retained;new independently verified helper run confirmed54;final18logical cases passed after correction and added safety probes. The OOM137 and expected refusal exits2 are successful negative tests,not crashes of Atlas or unhandled test failures.

Host focused tests:72passed,1Windowsplatformskip,0failed,in0.65s. This skip remains accurate for host execution;its exact native body was independently executed/passed in Linux. S/T/V isolated regressions82passed,0failed,in55.71s. Earlier W/A2sandboxstall/E136failure evidence untouched. No full canonical/whole Ruff waiver. Static/parser/compile/diff counts recorded in final evidence. Initial diagnostic/import/optional-field/harness failures are retained in failure-disposition.json and raw files;no unsafe lifecycle fallback used.

## Remaining BLOCKED / NOT TESTED guarantees

- Uninterruptible kernel/D-state I/O or daemon failure cannot be proven to exit within40s without force;not injected. Alarm/synthetic observer quarantine/normal reconciliation passed,not absolute hard-kernel shutdown. Retain exact identities/evidence and request controlled recovery on uncertainty.
- No atomic compare-and-swap fence exists for a privileged actor replacing named volumes between checks. Operator-exclusive window and fresh before/after ownership/consumer validation remain required;no real-volume fence held in Z.
- Production source UID/readability/effective config/external references/size unknown;source root0 without DAC capabilities may fail. No chmod/chown/capability/user fallback authorized.
- Full100000entry filesystem stress,physical allocation accounting across filesystem features,and source atime preservation not independently certified. Partial/error totals never accepted as complete volume size.
- This is synthetic acceptance only;protected evidence output policy,concrete real-operation wrapper/fence and uncertainty authority need operator review. Real backup capacity/destination/encryption/key recovery/usable backup/isolated restore remain unresolved.

Core synthetic helper checks PASS. These unverified guarantees remain BLOCKED/NOT TESTED rather than blanket PASS. The conditional real-volume package is ready for operator review,NOT permission or unconditional execution readiness. See R7E46Z_REAL_VOLUME_APPROVAL_ADDENDUM.md.

## Retention and safety

20created synthetic containers retained,all EXITED,one synthetic volume retained,verified pinned image retained. No removals or forced stops;memory probe was killed only by its own kernel cgroup limit as an intentional synthetic test. Initializer was the sole synthetic RW source mount;19others read-only. Kernel tmpfs scratch vanished on normal container exit;no named persistent source deletion. Final exact-ID/consumer audit in retained-resources-final.json must confirm all20exited;unexpected foreign consumer would block without inspection.

Atlas/production PG/Redis unchanged STOPPED/EXITED;no Genesis access,real source helper mount,production DB/payload/credential read,backup/restore,production ACL/shortcut change,live trading/Discord,Git staging/commit/push/reset,destructive cleanup,VPS or Engine/Desktop shutdown. PAPER_ONLY/MANUAL_ONLY and permanent low-resource Gaming/normal PAPER cadence unchanged.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Current core work:operator decision on real-volume read-only inspection package,exclusive-window/permissions/uncertain recovery contracts,fresh exact fingerprints;only separate approval permits real-volume helper. Then effective storage/sizing/capacity,protected destination/tool/fence,explicit cold backup and independently approved scratch restore. No automatic Stage B or production activation.

Next safest execution:R7E46AA real-volume inspection approval/operational-readiness review. Resolve listed BLOCKED prerequisites or explicitly accept the bounded fail-closed attempt and uncertainty retention policy;only a separate explicit authorization may mount real sources. Do not treat synthetic success as production release approval.


## Closure verification — October 18, 2026

Existing results reconciled without rerunning containers: 18 Linux cases passed; 72 focused host tests passed with 1 platform skip; 82 lifecycle regressions passed. Original 53-byte assertion failure and corrected 54-byte fixture evidence remain preserved. Atlas manager freshly reports STOPPED. Docker Linux Engine pipe is unavailable, so retained synthetic containers, production database identities/states and imported image cannot be freshly reconfirmed; prior verification remains historical evidence only. No Docker startup or lifecycle action attempted. Production remains NO-GO; no next milestone begun. Both original and closure roadmap backups/read-back and byte-identical historical preservation verified. Closure evidence: `logs/diagnostics/r7e46z-20261018-022818/closure-20261018-065910`.
