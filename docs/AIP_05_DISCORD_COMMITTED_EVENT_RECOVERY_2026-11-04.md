# AIP-05-DISCORD-COMMITTED-EVENT-RECOVERY

**AIP-05 COMPLETE — SOURCE-ONLY/DISPOSABLE. PAPER:NO. Production:NO-GO.**

November4,2026 (America/Chicago). Base `cbdcdd97c7e2aee01db8b4eb513b00a5e8bed518`; branch `chatgpt/atlas-rebuild-v1`.

## Canonical scope and architecture

The canonical audit requires the isolated lifecycle outbox/consent recovery adapter: commit identity -> unique lifecycle event/outbox; active consent generation/revocation, recipient/type/rate scope, UNKNOWN-send quarantine and no stale financial messages. E132/E133/E135, strict E136 recovery/rollback/concurrency/failure contracts and fake reconciliation alerts must genuinely pass without xfail substitution. The central production sender must remain denied until separately consented transport. AIP-01–04 remain complete at source/disposable scope.

Existing E133 supplies lifecycle identity, recipient-scoped durable SQLite delivery state, ordering, claim leases and bounded retries. Existing E135 supplies activation watermark, source-prefix cursor, frozen staging and idempotent outbox transfer. E136 supplies explicit consent generations, witness, coordinator, diagnostic recovery and an isolated delivery-admission prototype. The new canonical adapter reuses those stores rather than creating another notification system. None is registered with an operational runtime or real sender.

No installed application, selected release, financial runtime, operational account, provider, real Discord recipient/credential, Windows setting, browser or Genesis was used. All financial rows were generated through the existing pure accounting model. Actual central Discord delivery remains disabled at its original unconditional first `return False`; its source is unchanged.

## Exact implementation

| File/component | Completed connection or correction |
| --- | --- |
| New `scripts/observation_runtime/committed_notification_recovery.py` | Disposable canonical committed-financial-cut adapter subclasses E135, retaining its staging/state and E133 outbox. Explicit source/authority/coordinator/account scope/category/rate/clock; durable rate consumption, stale-message refusal, persistent Stop and read-only status. No background worker, runtime hook or real transport. |
| `discord_lifecycle_outbox.py` | Preserves original tables/schema/ordering/claim ACKs and3-attempt5/30-second backoff. Before recovery/enqueue/claim it validates canonical event identities, complete entity sequences and foreign keys, with4096-event capacity refusal. Corrupt-database configuration exceptions close the newly opened connection before raising. |
| `paper_lifecycle_producer.py` | Adds durable transferred-event IDs, staging/outbox consistency checks, exact event comparison against staging **and original source**, and a category-narrowing hook whose default preserves existing E135 behavior. Handoff checks use the existing producer transaction to avoid mixed concurrent snapshots. No second journal. |
| `discord_consent_generations.py` | Explicit create provisions a local append-only checkpoint outside the SQLite file: database UUID, canonical hash chain and monotonic recipient transitions. Reads are bounded to4096 transitions/2048 bytes per record. Missing, partial, corrupt or inconsistent checkpoint refuses; construction never adopts/repairs it. |
| `discord_consent_coordinator.py` | Retains consent-lock-before-witness order. Verify current checkpoint, update witness, append checkpoint, then commit consent; incomplete publication quarantines. No-op updates check the checkpoint too. Authorization rechecks current consent after witness comparison. |
| `discord_consent_recovery.py` | Rechecks state after witness observation and compares checkpoint state. A concurrent revocation cannot publish stale CONSISTENT/subscribed diagnostics. Assessment remains read-only and grants no permission. |
| `discord_consent_delivery_adapter.py` | Repairs the existing isolated prototype: duplicate enqueue cannot reset terminal delivery state or rebind consent; expired dispatch becomes uncertain, not sendable; only literal True acknowledges; completion is fenced to its retained lease token. It is not a second active transport for the canonical adapter. |
| `paper_reconciliation_alert.py` | Existing typed HEALTH warning/cooldown semantics retained. Operational Discord and legacy-history imports are lazy, so fake summary/sender tests do not construct those runtime objects. No actual reconciliation scan or alert ran. |
| Tests |40 new canonical recovery/adversarial/status cases.3 former strict xfail markers removed only after the existing refusal assertions pass. Older permissive restore/resend expectations are strengthened. E132 uses the exact tracked diagnostics handler in isolated ASGI, without importing `app.main`; subscription/settings defaults are fake fixture-only dependencies. |

## Committed-event and scope contract

`CommittedNotificationRecovery` requires an existing dedicated `atlas-e135-*` disposable directory directly under the configured test temp root, explicit source/authority, actual isolated consent coordinator, exact two-account scopes, policy and clock. No source, account, recipient, token or sender is defaulted. Policy fixes recipient IDs/categories,1..60 attempts per recipient/minute and1..120-second event age, and is bound to the durable activation watermark.

The read port returns `ATLAS_COMMITTED_LIFECYCLE_CUT_V1`, **DISPOSABLE only**, with source identity, current observation<=5seconds, original manifests and an append-only ordered commit list, bounded to256 commits/2MiB. Original QD USD and HL USDC epochs/currencies/accounts stay distinct. Operational domains/manifests are not accepted as disposable authority. Each item retains the original financial record and original commit-ACK declaration; an injected structured `ATLAS_COMMITTED_EVENTS_VERIFIED_V1` receipt binds the entire cut and expected account scopes. Boolean True, mutation, changed cut or foreign identity refuses.

The existing storage-neutral replay/audit independently verifies every financial command/receipt/digest/revision and duplicate operation. This **does not prove real native ACKs**; authentication is the accepted source owner's responsibility. Fixtures use explicitly synthetic ACKs, and no native acceptance is claimed. Original operation ID, revision, financial digest/receipt, account/currency/epoch, position identity and remaining quantity are preserved in event payloads.

Stable scope-bound source/entity keys prevent cross-account collisions. Source-event identity binds original operation/digest plus stable append offset; per-entity sequence stays contiguous. The canonical in-memory source byte prefix and manifest/scope identity are pinned to the durable cursor, so truncation/rewrite/reorder refuses. Retained financial journals are neither modified nor adopted as notification authority.

The original seven event types remain supported by E133. The new canonical adapter maps committed ENTRY -> PAPER_ENTRY, completed EXIT -> PAPER_CLOSE, and partial EXIT/MARK/FUNDING -> PAPER_MARK with original kind/remaining quantity. A partial exit is never falsely declared a completed position. It does not invent SIGNAL_CREATED, SIGNAL_INVALIDATED, PAPER_INTERRUPTED or PAPER_RISK_STOP producer semantics. Existing typed adapters remain; actual runtime/research event hooks and admission belong to later integration.

Explicit simulation activation begins at accepted source EOF and excludes historical trades/followups. No automatic backfill or implicit delivery approval. Event, original recipients and consent evidence commit atomically in the existing staging database before outbox transfer. Interrupted transfer replays the frozen record, not a fresh recipient list. Durable transferred IDs prevent deletion of an acknowledged outbox event from silently recreating it. Staging, outbox identity, original source event/watermark, current generation/witness/checkpoint and recipient/category policy are checked before send.

## Retry, acknowledgement and Stop

- Pending work reconstructs from the same cursor/staging/outbox after reopen. Duplicate source processing does not create a second delivery.
- Only literal True commits the original claim-token acknowledgement. Reopen or duplicate enqueue cannot requeue acknowledged/uncertain work; duplicate/foreign ACK cannot overwrite it.
- Proved non-delivery retains E133's5/30-second delays and maximum3 attempts, then dead. Retry state and attempt counts survive reopen.
- Exception, nonboolean, cancellation, lost ACK or expired inflight lease becomes uncertain/quarantined. No automatic resend, stale-lease reclamation into queued state or revival through re-subscription. Later cleanup cannot retroactively pass a failed operation.
- Corrupt/missing/conflicting source, staging, outbox or sequence refuses without reset/repair. Validation checks original event content, not merely SQLite integrity. Unknown earlier lifecycle deliveries block later ones.
- Recipient/category/freshness/rate checks run before entering the fake sender. Attempt rate is durably charged first. Guard exceptions conservatively quarantine instead of assuming safely retryable non-delivery.

There is **no exactly-once external delivery guarantee**. A remote send can succeed before local ACK failure; ambiguity is preserved rather than guessed away. A future real adapter must distinguish confirmed response, proved non-delivery and uncertainty. No such adapter, actual DM recipient or credential is enrolled.

Stop closes admission immediately and persists the canonical adapter's stopped state. Pending records remain; reopen does not automatically resume. An already-admitted send can return its true acknowledgement while remaining sends refuse/quarantine. Notification Stop never mutates/cancels a financial runtime or resets its journals. Resuming a stopped notification scope requires explicit safe recovery, not resetting a watermark.

`status()` returns `ATLAS_NOTIFICATION_STATUS_V1`: read-only counts, stopped/disposable flags, no recipients/payloads/credentials/financial values; real Discord, startup and exactly-once flags remain false. Deterministic repeated reads and isolated GET-only ASGI compatibility are tested. AIP-04 implementation/assets are unchanged; no endpoint or transport is registered in the installed dashboard.

## Checkpoint limits and strict recovery

The checkpoint is a **local append-only high-water outside the SQLite backup files**, not an independent remote witness, cryptographic issuer or administrative authority. Restoring consent alone or both historical SQLite files while retaining the current checkpoint now genuinely refuses. Missing/corrupt/partial checkpoint evidence refuses too. Witness/checkpoint ahead of consent after interruption remains quarantined; no automatic repair.

Rollback/replacement of **all** matching local state, including the checkpoint directory, remains outside what same-user local storage can independently prove. These source fixtures do not establish physical power-loss/directory-entry durability or operational custody. Legacy stores without an accepted checkpoint cannot authorize/update through implicit migration. Real recovery still needs the appropriate accepted current checkpoint/authority and fresh explicit consent required by retained policy contracts; normal intact-store restart is distinct from restoring lost/unknown evidence.

All3 former xfail contracts now execute as strict passing tests: standalone consent restore, dual-database restore and revocation during assessment. Their prior failures remain historical, not retroactively accepted operational security evidence. No external reviewer committee is introduced.

## Exact validation

**969 Python tests passed;0 failed;0 errors;0 skipped;51 modules;77.55s console (JUnit77.530s).** All770 AIP-04 identities, all667 AIP-02/all396 AIP-01 identities and all52 AIP-03 source cases remain.40 new tests are separate from the3 existing formerly-xfailed contracts; overlapping totals are not added.

| Notification selection | Passed |
| --- | ---: |
| E132 subscription/isolated diagnostics |17|
| E133 outbox |28|
| E135 staging/recovery |34|
| E136 strict generations/witness/coordinator/recovery/rollback/concurrency/delivery |75|
| Fake reconciliation alerts |5|
| New canonical committed recovery |40|

The other770 are the preserved research/valuation/read-model/accounting/risk/maker/funding/continuation-source regressions. **42 existing Node tests passed;0 failed/skipped/cancelled**, plus the standalone polling harness passed. New Node cases:0. AIP-04's two Node integration cases remain inside the Python count, not additional browser evidence.

Warnings: existing Starlette/httpx TestClient and Discord audioop deprecations. No dependencies installed. No-cache Ruff/format checks pass all15 changed/new Python source/test files. No skips/xfails substitute for required safety cases.

Failure evidence is retained: initial strict selection137 passed. The larger run recorded190 passes/1 handoff-concurrency failure/4 cleanup errors. The mixed staging/outbox cut was corrected by existing transaction locking, and test SQLite contexts now explicitly close. The next run recorded197 passes/1 remaining corrupt-database cleanup error, exposing a real `_connect` exception leak; closing the connection before raising fixed it. Targeted39 passed, then final969 passed. Style findings and a formatter-moved lint annotation were corrected. Refusal assertions were preserved/strengthened, not weakened; the diagnostics handler was isolated from legacy startup.

Private logs/XML/test selection/proof are under `logs/diagnostics/aip-05-discord-recovery-20261104`. TEMP/TMP and test resources are confined there. Only exact owned temporary children are automatically cleaned; prior failed-cleanup remnants and raw failures are retained. Final passing fixtures close normally. No listener, actual Discord connection, forced process/port cleanup or native-handle acceptance was performed.

JUnit SHA-256: `8141fb96c514e71be0ff2878247cb02be41bd39d724f0e77134670edb3ff9ade`.

| Tested file | Raw SHA-256 |
| --- | --- |
| `backend/app/services/discord_consent_generations.py` | `87cdd34f6fff5e08bdf9d6678a0d1c115c5b10e0c49eb244b096ef73001d3b63` |
| `backend/app/services/discord_consent_coordinator.py` | `9292e08acc0783811072f6c648101f9e667331f2d85b02b6fcd0ee5534a12c95` |
| `backend/app/services/discord_consent_delivery_adapter.py` | `7c2cc48ddf4eacaf5e277dc6c3cf4884e059bdbe04c2cbf3cd137e8629caacbd` |
| `backend/app/services/discord_consent_recovery.py` | `f0379f365a69533a24418dff20b9e04f2566f1261415d1c20c9b04bd626b9872` |
| `backend/app/services/discord_lifecycle_outbox.py` | `5d476306ef624c9e235e9b6c853c08b81ecea62955148bd3bd4ddf7232ef9fec` |
| `backend/app/services/paper_lifecycle_producer.py` | `c10976260ee5ffcbb048425247643749cef56f96e2aedf829c23134d956d5777` |
| `backend/app/services/paper_reconciliation_alert.py` | `1bce3595cda40c97832b99b27df8c016677f284ddf31e5033b6e99c4061f3d7a` |
| `scripts/observation_runtime/committed_notification_recovery.py` | `14261e5038effbfe3e73dfc70af40e8b0ab558d8bc15f5b4fcd18b251c8b29a5` |
| `tests/test_committed_notification_recovery.py` | `0ab03361a7caac0818eeaad936522dd651cbe1ba76f75135de387dd15e7085a8` |
| `tests/test_e132_discord_lifecycle.py` | `f775a2f0b45d7c42bd891e048e80506deba3cde81bbb0a774015a1fe24661d2c` |
| `tests/test_e136_consent_delivery_adapter.py` | `3eee39b6eb3cb9cc1f4cc6d6be03488dd4c3d3a953ab22b2dd32762a8dcc7916` |
| `tests/test_e136_dual_rollback_contract.py` | `070a8fc8e12ef270ebc13edc8adeec5ce3139e2b648a44fefd3937189e67d4ce` |
| `tests/test_e136_recovery_security.py` | `0153a2ab3e99d42e6bc8279b482cfe495c0f9174d86ccb71a637e41b67158263` |
| `tests/test_e136_recovery_snapshot_contract.py` | `0798a5392b11a79c144a2f1d1009c1d2f9051e788f1cace195ac29852da8a968` |
| `tests/test_e136_rollback_contract.py` | `13e027d8782046b29355675b9e2e52e0979cb9a000588a6c1de79f0fd4931094` |

The unrelated preexisting research-test edit retains SHA-256 `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb`, participated unchanged in regression and is excluded from this commit. AIP-01–04 pins, UI assets, central sender denial, personal policy and all21 historical decisions are preserved.

## Completion and remaining prerequisites

**5 of18 canonical milestones complete at source/disposable scope: AIP-01 through AIP-05.** No installed/financial/real-message acceptance or B1/C1/D1/E1 gate advances.

Real Discord requires exact recipient/DM/channel/category/rate consent, credential handling, accepted current consent/custody/recovery evidence, an explicitly scoped transport adapter and separately authorized bounded real-delivery proof. Connectivity/permissions/actual DM acceptance have not been checked. Central delivery stays denied. An explicitly approved no-notification pilot may exclude transport; that does not mark the real notification feature complete.

Actual runtime hooks/native source ACKs, operational financial accounts/custody, current research/provider rights/data, clock<=1000ms/age<=120s, V6 active-listener/trusted-browser prerequisites, installed read/control/Stop/restart, exact release/resource enrollment and explicit bounded PAPER activation remain required. Sole-operator authority stays intact; no enterprise review chain is added. Genesis, historical failures/consumed grants, B1/C1/D1/E1 and21 decisions remain unchanged.

**Next: AIP-06-COMPOSED-ACCOUNTING-RISK-RECOVERY**, under its own requested source/fault-matrix scope; actual native resources need separately reviewed bounded authorization. It is not started. Stop after this report, canonical roadmap/recovery checkpoint, validated commit, non-force push and independent remote SHA verification. PAPER:NO. Production:NO-GO.
