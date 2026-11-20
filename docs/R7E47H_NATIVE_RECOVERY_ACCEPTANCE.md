# R7E47H — native approval and exact-helper exit-proof contracts

**Automated native/synthetic acceptance PASS. Native checked positive approval NOT ESTABLISHED. Operational integration BLOCKED. Production NO-GO.**

2026-10-18, America/Chicago (CDT, UTC-05:00). Exact completion timestamp is in the diagnostic result. Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e47h-20261018-104744. Master/permanent contract, F/G security reports and selected Phase1 policy, snapshot store, durable handoff, lifecycle bridge and D startup contracts reviewed. Prior D/E/F/G sources/reports unchanged by hash. All existing work and evidence preserved.

## Implemented files and native context

New scripts/volume_inspector/native_dialog.py, native_recovery.py and tests/test_r7e47h_native_recovery.py. No production imports them. token_context uses actual Windows current-process token APIs to bind hashed SID, token session, authentication/logon LUID hash, elevation/restriction state and issuer PID. Thread impersonation is rejected before using process identity. Input-desktop availability and nonzero session are required. Expected context must match before/after prompt and at recovery. Fixture enrollment captures the intended native context; independently approved production enrollment is not implemented.

Actual probe: session1, non-elevated, unrestricted, interactive. Identity hashes/context are retained, not usernames, raw SIDs or credentials. Wrong expected SID/logon/session/elevation/PID tests call the real context collector and refuse. Actual restricted-token thread impersonation refuses. Noninteractive context refusal is explicitly modeled, not a Session0/service UI acceptance. Alternate-user, remote/locked desktop and credential reauthentication were not accepted.

Native TaskDialog requires a verification checkbox AND explicit Yes; Cancel is default. Close/Escape/unverified/timeout refuse. It displays UNCERTAIN reason, required evidence, exact operation/helper/revision/state/proof hashes and the fixed failed-exit action, excluding startup/retry. Timer cancellation is bounded to1–45s; no automatic Yes exists. UI runs outside registry locks. Callback timers are cooperative message processing, not a hard deadline against OS/UI-thread failure.

Approval binds nonce, instance, exact revision/state hash, helper/operation, action, operator context, reviewed exit fingerprint and45s window. Evidence is recollected after UI and before recovery; facts/state must remain unchanged. Proof is fresh within5s at use, with <=2s collection latency in the synthetic transport model. A process restart cannot restore a usable ticket from files alone; fresh approval is required.

Protected native exclusive records include challenge, decision, approval, proof, refusal and consumption. Receipt native file ID/digest is checked before trust. Consumption is flushed BEFORE recovery; failures leave uncertainty or an unresolved handoff. No keys, credential enrollment, TPM changes or production ACLs. This ordinary trusted-owner desktop UI is NOT secure-attention/password/UAC reauthentication or a sandbox against same-account malware.

Primary references: [TaskDialogIndirect](https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-taskdialogindirect), [token information](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation). Native observations, not documentation alone, determine acceptance.

## Actual native UI outcome

The native timeout test created a real dialog and observed timed_out=true, buttonIDCANCEL2, approved=false. One separate full-workflow operator attempt used a45s maximum dialog and synthetic Docker evidence. human-native-result.json records NATIVE_APPROVAL_NOT_ESTABLISHED, Refused, inspection_uncertain=true. The refusal branch covers decline, timeout or unchecked verification. That original attempt did not retain structured button/checkbox data, so do NOT assert which occurred. Its traceback and protected challenge/proof/refusal evidence remain. Later source adds a bounded structured decision record for future attempts.

The prompt was not repeated; no agent clicked Yes or inferred consent. Actual checked native-positive end-to-end recovery is NOT accepted. Automated positive paths use MockDialog and are explicitly marked SIMULATED_UI. This missing native-positive result is an operational blocker, not hidden in skipped counts or relabeled PASS.

## Independent helper-exit proof interface

ExitCollector accepts ONLY non-network MockDocker. Arbitrary imported JSON, process exit codes and fixture signatures alone cannot establish production authority. Source correlation uses a fresh nonce, immutable expected helper ID, exact instance/operation/project labels, expected image content ID and manifest identity. Expected identities come from an approved synthetic plan; a real independently validated image-ID/manifest mapping remains required.

Normalized source contains exact container Id/Image/Labels/Created and State(Status,Running,Pid,StartedAt,FinishedAt), plus image Id/Manifest. Types/ownership must match; boolPID is rejected. EXITED requires Running=false, integerPID0 and timezone-aware ordered positive Created<=Started<=Finished<=observed. Observation time is generated locally, not taken from caller input. Request mismatch, excessive latency and cached responses refuse. Fingerprints bind stable container/exit facts; restart/finish-time changes invalidate approval.

Explicit outcomes: EXITED, RUNNING, MISSING, REPLACED, UNKNOWN. Changed ID/image/labels is REPLACED. Engine disconnect is UNKNOWN/ENGINE_UNAVAILABLE. Missing is never proof of exit. Malformed, contradictory, unsupported or stale replies are UNKNOWN. Ambiguity is persisted with fixed codes, without raw Docker Config/Env/stdout/stderr. No retries or lifecycle actions. Persistence failure fails the call before approval/recovery.

This demonstrates authenticated-source CONTRACTS inside an exact synthetic transport, not authentication of a real Docker Engine. No real adapter/socket/subprocess was added or contacted. Real endpoint/CLI identity, bounded I/O/cancellation, image mapping and ownership source require separate acceptance. Mock latency checks are not real blocking-I/O timeout enforcement. Ownership is never inferred from names.

## Isolated recovery integration

ApprovalWorkflow composes F SnapshotStore and G Handoff. A ticket is minted only after native context, explicit native or explicitly simulated UI and collector checks. Recovery verifies retained ticket/native-bound receipt, context, fresh unchanged helper facts and expiry; reacquires the store guard; compares complete state hash/revision and proof freshness; persists unique consumption; only then converts facts into the existing F/G synthetic compatibility signatures. Those downstream fixtures are never sufficient operator/source authority or a production permission.

G intent/ack and F commitments retain publication failures. Corrupt snapshot/witness refuses before approval. Consumed evidence remains after interruption. Concurrent recovery is single-use. Concurrent separately requested startup cannot coexist with UNCERTAIN inspection; after recovery commits first, a separate synthetic start may enter PENDING. A rejected conflict may conservatively leave a review intent. Recovery itself never starts anything; production admission always refuses.

Actual parent/worker crashes and interrupted publication are rerun through D/F/G native regressions. H additionally tests issuer restart losing the ticket, interrupted recovery and evidence-storage failure. No real Atlas process was started/stopped.

## Exact validation and original failures

| Check | Result |
|---|---|
| New H native/model tests |44 passed,0 failed,0 skipped |
| Existing G/F/E/D/C/B/Y |358 passed,0 failed,4 skipped |
| Combined combined-native.txt |402 passed,0 failed,4 skipped;27.33s |
| Guarded S/T/V lifecycle |82 passed,0 failed,0 skipped;48.13s |
| Final automated total |484 passed,0 failed,4 skipped |
| Separate human-native attempt |Approval NOT ESTABLISHED; inspection remained UNCERTAIN |
| Targeted Ruff |PASS; helper directory and8test modules |
| Compilation/parser |20Python files compile;18PowerShell scripts parse0errors |
| Source preservation |D/E/F/G unchanged;5 lifecycle sources match guarded snapshot |

Four inherited skips: F/C native symlink privilege1314 unavailable, POSIX publisher and Linux descriptor on Windows. No waiver/full canonical/whole-tree lint acceptance. Historical Z Linux acceptance was not rerun. Native-positive acceptance is separately BLOCKED.

First-native.txt retains38pass1fail: TaskDialog E_INVALIDARG due to176byte default ctypes alignment. Microsoft's [SDK header](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/CommCtrl.h) applies pshpack1 to TASKDIALOGCONFIG; correcting this new structure to pack1 gives160bytes. Repaired focused39passed; expanded final44newpassed. No safeguard loosened; original failure and human refusal retained.

## Decision and next gate

**BLOCKED for operational integration.** Native account checks, impersonation refusal, timer refusal, protected receipts and synthetic exact-exit/recovery contracts pass. Checked native positive approval was not established, and the source remains intentionally synthetic. No complete authenticated real-helper proof or production readiness claim.

Selected Phase1 assumes trusted operator/code/OS, not same-account/admin/full-machine compromise resistance. External Docker writers remain outside application exclusion. E136 stronger gates remain unchanged. Enterprise PKI/TPM/off-machine services are not needed to fix the immediate acceptance gaps.

See R7E47H_MINIMAL_INTEGRATION_PLAN.md. Next safest proposed milestone: R7E47I independently directed native-positive approval fixture acceptance and read-only source-adapter design review. Do not repeat the unestablished prompt automatically. No next milestone executed, production source adapter/query or startup wiring implied.

## Runtime, preservation and roadmap

No Atlas/Docker status, real container inspection or lifecycle operation. User STOPPED is inherited; last independent A status/Engine-unavailable evidence remains historical. Production registry path remains absent. No real volume/helper/backup/restore, Genesis, production ACL/shortcut/key/TPM, trading/Discord, Git stage/commit/push/reset, deletion or VPS. Static scans of launchers/two standalone writer scripts did not execute them. Existing broad working-tree changes preserved.

Completed/preserved chain: Y/Z pinned-helper synthetic Linux; A preflight; B adapter; C output; D isolated registry; E VFS review/bridge; F snapshot; G manual policy/handoff; H new native/refusal/proof contracts and automated acceptance. Each retains its limitations. H native-positive/real-source/all production integration incomplete. All earlier milestones remain in the historical master.

Required updater backup/read-back/outside-marker byte checks are in final result.json. Permanent gaming efficiency/normal PAPER cadence, separation, PAPER_ONLY/MANUAL_ONLY and PM-V2 remain.

## Remaining seven phases

1. Core reliability/operations: cash-scanner scope, provider rights/HTTP budget/pacing/ownership/drain/stuck-worker acceptance, Ruff disposition, packaging/license/portability, clean-machine/live-data/runtime/Gaming and sustained recovery. Native-positive consent, real read-only proof-source authentication/deadline/image mapping, approved account/root enrollment and all-path admission/outer locks remain gated. Failed-start/owned-stop/manual-review reconciliation; fresh ownership/image/exclusive writer window; real metadata/storage coverage/capacity/destination/encryption/key recovery/backup/scratch restoration/Complete Shutdown/shortcut migration require separate approvals.
2. Evidence Engine: immutable timestamped hypotheses/outcomes, replay, precision/recall/calibration, false positives, realistic PAPER costs, bias/leakage controls, reproducible Research Memory. E29 remains NOT_READY; Alpha/corroboration context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/rules/fees/settlement, timestamped spot/perpetual/depth/liquidity joins, calibrated probability/executable edge, realistic fills and out-of-sample evidence before any separate live proposal.
4. Cross-market intelligence: equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores/uncertainty/invalidation/reproducibility; cautious hypotheses.
5. SaaS: demand/pilots, tenancy/auth/billing/entitlements, APIs/dashboards/exports/alerts, support/analytics/licensing/unit economics; pricing unvalidated.
6. Institutional readiness: RBAC/audit/security/incidents, governed research/API stability/compliance/pilots. Stronger principal/TPM/off-machine anti-compromise authority separately scoped; no VPS dependency.
7. Commercial scale: retention/product-market fit, partnerships/integrations/white-label/API licensing, evidence-led expansion and measured economics/reinvestment.

Cross-phase: E136 independent rollback witness, dual-DB consent resurrection/atomic recovery snapshot/fencing, recipient transport/render/storage and uncertainty/dead letters. Discord requires explicit approval and durable no-backfill watermark, no automatic uncertain-send retry. Prediction exactly-once/pre-deadline/auto-flat and portfolio-versus-strategy risk remain unfinished. PM-V2.1–PM-V2.6 discovery/calibration/edge/pre-event PAPER/evidence/dashboard; one position per market, no combos/stacking/averaging/opposing YES+NO. Settlement research never overrides pre-event gates. No production activation follows.
