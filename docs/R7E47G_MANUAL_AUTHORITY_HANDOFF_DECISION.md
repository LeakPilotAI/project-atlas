# R7E47G — practical operator authority and durable-pin handoff

**Selected Phase1 policy: trusted workstation operator, conservative manual recovery and local durable pin handoff. Isolated handoff PASS. Production integration decision BLOCKED pending a native operator/exit-evidence workflow; overall production NO-GO.**

Completed 2026-10-18T10:45:34.195355-05:00, America/Chicago (CDT, UTC-05:00). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e47g-20261018-103658. Latest master/permanent contract, E/F security reports, F implementation and rollback reproduction, E bridge and D integration contracts reviewed. D/E/F reviewed source/tests/reports unchanged by hash. All existing work, artifacts, backups and limitations retained. This is a source-based security/architecture review, not third-party certification.

## Phase1 workstation trust boundary

Trusted: the intended Windows operator, installed/reviewed Atlas code and OS, fixed approved control roots and normal NTFS security enforcement. The operational objective is preventing accidental unsafe startup and stale/forged recovery through approved Atlas paths. No autonomous permission is derived from a free port, expired timeout, missing process or inaccessible Engine.

| Threat | Phase1 mandatory behavior | Stronger boundary / residual limitation |
|---|---|---|
| Accidental corruption, process crashes and partial writes |Bounded validated state, native identity-before-read, durable intent/ack, no fallback/reset; retain uncertainty/manual review |Physical power-loss and coordinated whole-machine restore not proved by process-exit tests |
| Other-user/restricted-token file substitution |Protected owner/SYSTEM DACL, handle-relative no-follow lookup, file-ID/hash/link checks and native denial tests |Malicious ordinary code running AS the same owner is account compromise, even without administrator rights; DACL does not distinguish it from Atlas |
| Accidental same-user stale/copy/replacement |Reject inconsistent file IDs, receipts, revision chain and incomplete handoff; manual recovery |Coherent deliberate rewriting by trusted-owner code is not cryptographically excluded |
| Replay/forged recovery input through approved workflow |Exact helper/op/instance/revision/state binding, fresh independently obtained exit facts, explicit operator review and single-use recovery |Fixture HMAC tests do not authenticate a real human or actual Docker state |
| Privileged administrator/SYSTEM/kernel compromise |No security guarantee; stop relying on local state and preserve evidence |Separate-principal isolation/attested keys/independent witness can be Phase6 hardening if that threat is adopted |
| External Docker clients and independent writers |Operator-exclusive inspection window plus fresh exact ownership/writer proof is a Phase1 prerequisite; refuse if not establishable |Application registry cannot stop other Docker clients, Engine restart or arbitrary writers; not solved by TPM/PKI |
| Complete-machine rollback/compromise |No local non-rollback claim. Known image/restore/control-state rollback requires explicit manual re-verification before startup |Undisclosed coherent rollback of OS/user/state/receipts/keys requires an independent non-rollbackable/off-machine anchor to detect; a Phase6 option, not a Phase1 enterprise-service dependency |

Phase1 must retain PAPER_ONLY/MANUAL_ONLY, all-path admission before dependencies/API, correct ownership, fresh exact helper exit, Gaming normal PAPER cadence, evidence preservation and refusal on unavailable authority. Full-machine/admin-compromise resistance is explicitly NOT a Phase1 acceptance claim. This scoped policy does not waive E136's separately recorded consent/rollback gates or any existing real-operation/backup/lifecycle approvals. Same-user/account trust is stated rather than mislabeled as protection against all unprivileged attackers.

## Read-only capability discovery

capabilities.json records Windows version10.0.26200.0; an interactive environment; availability of WindowsIdentity and ProtectedData API types. Get-Tpm returned successfully with TpmPresent/Ready/Enabled/Activated all false. This is the API's current observation, not a BIOS diagnosis. No TPM/provider state changed, no key enumeration/enrollment/generation, credentials, DPAPI payload encryption, service setup or external account discovery occurred. API type availability is not acceptance of DPAPI key lifecycle or operator re-authentication. No Docker/Atlas command was invoked.

## Practical authority options

| Option | Properties / limitations | Dependencies, offline recovery and complexity |
|---|---|---|
| Windows-protected local operator authorization |Current-user DACL/identity/session and explicit recovery action can bind deliberate trusted-operator approval; DPAPI can protect local user-bound secret material. It is not independence from same-user code or rollback |Offline, built-in OS, low burden; account/profile loss and restore need explicit recovery. Prefer keyless explicit approval receipts for Phase1; native workflow still required |
| TPM non-exportable signing key |Can reduce private-key export; does not by itself establish latest state, independent human consent or a monotonic recovery witness |Get-Tpm reports unavailable here; no keys created. Hardware/attestation/recovery complexity, conditional Phase6 option |
| External/off-machine revision witness |Can detect local rollback if independently controlled, authenticated and itself durable/non-rollbackable |Needs provisioning, availability/network/recovery policy; offline failure must retain prohibition. Not selected or configured; no VPS requirement |
| Separately controlled recovery approval |A distinct person/device/principal or separately controlled retained checkpoint can provide actual separation, subject to its own rollback authority |Operational coordination and lost-device/key recovery costs. Optional stronger mode; no claim that two same-user files/keys are independent |
| Conservative manual evidence-based recovery |Trusted operator explicitly reviews fresh exact exit and current revisions; no automatic uncertainty clearing |Offline where Docker/native read-only evidence is available; unavailable/ambiguous evidence means STOP/BLOCKED. Smallest Phase1 policy |

Microsoft documents current-user DPAPI protection and machine-scope implications: [CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata). It does not make two same-user records independently trusted. TPM key protection/non-exportability are distinct from maintaining an application's authoritative revision: [TPM fundamentals](https://learn.microsoft.com/en-us/windows/security/hardware-security/tpm/tpm-fundamentals). The latter separation is this architecture assessment; no hardware/remote anti-rollback was tested.

## Selected minimum viable authority

Select conservative manual recovery under an explicitly trusted workstation operator, with native current-user protected records and no new signing key requirement. Logical independence means fresh read-only evidence obtained separately from the interrupted worker's claims and a human recovery decision; it does NOT mean a separate cryptographic rollback authority. Local handoff receipts provide durable continuity against partial failure, not full-machine rollback independence. Native operator identity/session and the actual read-only proof collector remain unimplemented, so no fixture issuer is accepted as production proof.

Proposed manual procedure, NOT executed: preserve pending intent/uncertainty; verify fixed root/instance and latest complete local handoff; independently inspect exact helper ID/image/operation/labels/state/finished time/PID and source writer/ownership evidence using reviewed read-only controls; present exact state/revision/evidence hashes and consequences to the trusted Windows operator; require explicit one-time approval; revalidate evidence freshness/identity/revision under the common lifecycle gate; commit FAILED/exit-proven recovery and durable acknowledgement. Recovery never implies automatic startup, successful inspection, retry or an authorization for live trading. Missing/changed helper, stale evidence, unknown create identity, mismatched records, inaccessible Engine or missing approval retains prohibition.

Interrupted pin handoff/storage-latch recovery is a DIFFERENT manual reconciliation case. Do not delete or edit fences, choose the newest-looking file, reconstruct manifests, overwrite receipts or auto-expire uncertainty. Preserve all candidates and require an independently reviewed reconciliation/migration procedure. Known machine restore requires manual baseline re-verification; complete compromise cannot be solved with local records.

## Implemented isolated durable-pin handoff

New scripts/volume_inspector/manual_handoff.py and tests/test_r7e47g_manual_handoff.py. Handoff accepts exact synthetic SnapshotStore and ManualFixtureAuthority types only. production_admission always refuses. No Windows authentication/proof collector, DPAPI/TPM API/key or production module integration was added.

A separately created disposable protected NTFS handoff root holds an exclusive initial ack0 and bounded sequential intent/ack records. These records carry the exact F pin (instance/root IDs/revision/snapshot and commit IDs/digests), hash-chain linkage and action/recovery-grant digest. SHA-256 protects against accidental inconsistency; it is NOT a signature against the same account. Root identity is pinned by the caller's trusted configuration. Native DACL/no-follow/single-link/bounded reads reuse F; production root is absent.

Under F's native cooperating mutex: authenticate local receipt chain/current pin and snapshot; flush handoff intent BEFORE the state transition; perform exactly one F revision change; flush ack carrying new pin and reservation hash; validate chain/state again before return. Reopen reconstructs the latest local pin only from a complete contiguous valid chain and then F verifies exact snapshot/witness identity/commitment. It never initializes absent state. Publication limits remain128revisions/64KiB per record for the prototype, not a production retention policy. No network/process waits occur under the mutex.

Missing ack, sparse tail, stale/foreign/root-changing progression, corrupt envelope, snapshot/witness mismatch or unavailable authority prevents admission. Integrity/uncertainty detection writes a durable manual-review-required marker when storage permits; byte repair alone cannot clear it. Interrupted effects leave intent and no automatic retry. If storage is unavailable, no new durable marker is promised; the operation still refuses. Future operator reconciliation needs separate implementation, not editing or deleting these markers.

ManualFixtureAuthority models availability and composes F's synthetic exit-witness/operator signatures. Recovery verifies fresh proof and revision-bound approval BEFORE writing a new handoff reservation, and again during the serialized state change; invalid proofs cannot create a successful acknowledgement. A valid grant is consumed by the new revision. Missing/unavailable authority rejects even normal synthetic startup through this bridge. It cannot guard code bypassing the bridge; all actual manager/worker/Gaming/legacy/API/migration/Docker paths remain unchanged and unprotected by it.

### Acceptance evidence

- Native complete local pin progression and restart, including process exit after durable ack: PASS. No caller must guess the in-memory latest pin after restart.
- Stale local ack, partial handoff rollback, snapshot/witness rollback, history gap, corrupt state, changed root and missing ack: refuse.
- Interruption before effect/after state commit, authority loss and actual child exit24 before ack: retain pending/manual review; no startup/inspection acceptance.
- Concurrent startup/inspection: exactly one committed winner; the rejected conflicting action can conservatively leave a review intent rather than retry.
- Forged proof/grant, replay, stale/future timestamps, mismatched helper/operation/revision, running helper, foreign signer, missing approval: refuse; uncertain state persists.
- Missing/wrong/unavailable authority: refuse. Local fixture never production authority.
- Native restricted-token READ/WRITE denial for handoff receipt: PASS; F native snapshot/witness token tests rerun.
- F full local witness+pin rollback limitation and E SQLite attacks preserved/rerun. They are NOT relabeled secure. Coordinated machine/control-state rollback remains outside demonstrated Phase1 scope.

## Security/architecture decision and minimum remaining gate

**BLOCKED for production integration.** The Phase1 manual-authority policy and synthetic durable handoff are defensible without enterprise PKI/remote services, but the real authenticated operator approval plus fresh exact helper-exit evidence workflow does not yet exist. The fixture boolean/signatures cannot substitute for it. Missing this small native workflow, rather than lack of full-machine compromise protection, is the immediate authority blocker. No production-ready claim follows from tests.

Smallest next proposed execution: **R7E47H bounded native manual-recovery workflow and proof-contract acceptance**, source-only/isolated unless separately authorized. Implement an explicit operator-review receipt tied to intended Windows principal/session, state/revision and evidence digest; validate exact read-only Docker/process proof schemas and freshness; reject forged imported claims; test mocked/unavailable Engine and native disposable identity/approval boundaries. Do not provision production roots/keys or collect real exit proof/start services without authorization. No enterprise PKI, external service, TPM enrollment or replacement storage engine is required for this proposal. Actual integration still needs its own approval and all-path/lifecycle regression acceptance.

Remaining release gates unchanged: full startup/worker/legacy/API/migration coverage and outer lock order; durable single-use spawn/real process identity; failed-start/owned-stop reconciliation; operator-exclusive external writer window and real helper proof; fresh real ownership/image; real-volume metadata/effective storage coverage/capacity/encryption/key recovery/backup/scratch restoration; Complete Shutdown real-container acceptance and shortcut migration; cash-scanner scope, provider rights/HTTP budget/stuck-worker acceptance, Ruff disposition, packaging/clean-machine/runtime/Gaming validation, E136/Discord consent and Prediction Market Intelligence V2 safeguards. TPM/off-machine witness can be separately evaluated for Phase6's stronger threat model, not imposed as a Phase1 hosting dependency.

## Exact validation

| Suite/check | Result |
|---|---|
| New G native/synthetic handoff |33passed,0failed,0skipped |
| Existing F/E/D/C/B/Y |325passed,0failed,4skipped |
| Combined verified-native.txt |358passed,0failed,4skipped;18.15s |
| Guarded S/T/V lifecycle |82passed,0failed,0skipped;46.60s |
| Total final |440passed,0failed,4skipped |
| Targeted Ruff |PASS over helper directory and7test modules |
| Compilation / parsing |17Python files compile in memory;18PowerShell scripts parse0errors |
| Source preservation |D/E/F sources/reports unchanged;5 lifecycle sources match tested isolated snapshot |

Four inherited skips: F and C true-symlink creation privilege1314 unavailable, POSIX publisher and Linux helper descriptor on Windows. No skip waived; historical Linux evidence not rerun. No full canonical/whole-tree Ruff waiver. First new run31passed; initial combined356passed4skipped; added persistent manual-review and native token cases; final358passed4skipped. No new failing run; earlier E/F original failures/attack artifacts retained. Capability discovery success is not TPM key/DPAPI operational acceptance.

## Runtime, Git and roadmap

No fresh Atlas/Docker status query or lifecycle action; user STOPPED remains inherited, not independently current process/container verification. Last A status/Engine-unavailable observation remains historical. Production inspection-control path checked absent. No real volume/database/backup payload, Genesis, production ACL/TPM/key/shortcut, trading/Discord, Git stage/commit/push/reset, deletion or VPS operations. Ephemeral fixture signing material is test-only. Existing broad tracked/untracked source changes preserved. No production startup or application source changed in G.

Required master checkpoint updater is used; final result.json records backup equality, successful read-back and byte-identical preservation outside the managed section. Historical strategy/recovery and PAPER_ONLY/MANUAL_ONLY, gaming low-resource/normal PAPER cadence and separation contracts retained.

## Complete seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Current Phase1 addition: selected local trusted-operator/manual recovery policy, native operator/exit-evidence workflow and all-path startup integration remain gated; durable handoff/manual-review recovery and restore procedures require acceptance. Full-machine/administrator/same-account compromise resistance, TPM/off-machine witness and enterprise key governance are separately scoped Phase6 options, not claimed guarantees or automatic requirements. All existing E136 consent/anti-rollback gates remain separately blocked. No production activation follows from this classification.
