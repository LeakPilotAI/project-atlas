# Quality Dips integration V1 — source-only acceptance and continuation

Authorization: **P-QD-INTEGRATION-V1-OFFLINE**. Base `9023f76847a7d2597566407280fa2251de87c110`; branch `chatgpt/atlas-rebuild-v1`. Status: IMPLEMENTED / DISPOSABLE VERIFIED; NOT OPERATIONALLY REGISTERED OR ACCEPTED. B1/C1/D1/E1 BLOCKED;all21decisions unchanged;PAPER startupNO;productionNO-GO.

## Implemented files

| File | Implemented behavior |
|---|---|
| `backend/app/investment/quality_dips_candidate_evidence.py` | Frozen JSON evidence from existing board/V3/forward-observation shapes and explicitly verified instrument/quote execution snapshots. Exact generation, source revision, cohort, observation/ladder, rank, score, reasons, source timestamps, expiry and injected verification receipts. No scanner/provider/mirror imports. |
| `backend/app/investment/quality_dips_selected_account.py` | Dispatcher with injected current-evidence, owner/admission lease, manual reservation, clock, financial publisher and projection verifier. FinancialStorePublisher bridges the existing FS2 store without provisioning. Manual approval binds exact account/epoch/operation/instrument/quantity/action/policy/candidate/quote/execution-rule/source/position revisions and decision time. |
| `backend/app/api/quality_dips_selected_paper.py` | Unregistered router factory for GET `/api/investments/quality-dips/selected-paper`; POST `/commands` refuses by default unless explicitly supplied a dispatcher. GET only accepts injected read/verification/clock capabilities; no writer object, legacy fallback, provider refresh or service hooks. Safe reason codes; unsupported valuation/equity/fee breakdowns explicitly unavailable. |
| `backend/app/services/quality_dips_account_policy.py` | New explicit V2 policy for a V3 selected inception, plus frozen decision/execution context binding. Prior policy V1 remains unchanged in meaning. Fresh execution price must still satisfy the existing selected reached ladder level. |
| `backend/app/services/paper_financial_replay.py` | Additive V3 inception/command/receipt dispatch into the same financial calculation engine. Original full command and evidence remain receipt-hash bound. No second ledger or replacement financial arithmetic. |
| `tests/qd_integration_harness.py` | Ordinary-file test primitives and durable fixture admission/pin journals around the actual FS2/FS3 protocol classes; explicitly not native security acceptance. |
| `tests/qd_integration_crash_child.py` | Exact test-owned self-exiting subprocess for five abrupt crash boundaries; never enumerates or terminates another process. |
| `tests/test_quality_dips_integration_v1.py` | 74 source-to-financial/read, adversarial, concurrency, restart and crash cases. |

No changes to `main.py`, production lock, actual scanner/ranking/quote algorithms, native FS2/FS3 source, legacy financial sources, Windows launchers or other strategy engines. No operational import/registration or protected provisioning.

## Current-ranking integration and immutable versions

`PAPER_EPOCH_SELECTED_QD_V3` binds `QD_SELECTED_ACCOUNT_POLICY_V2`, still **DISPOSABLE_ONLY**. It identifies the explicit account, ranking authority descriptor and reviewed instrument/execution mapping; immutable inception no longer contains a finite list of future ranking receipt hashes. New current ranking generations therefore do not require editing inception. V1 historical records and selected V2 frozen-pin histories remain replayable; no migration or automatic version promotion.

The adapter derives rank from the exact existing ordered board cohort; it does not sort, score or manufacture ranking. It retains the score and reasons. One test runs the actual pure `build_quality_dips_board` and `build_v3_entry_plan` through the complete integration chain, preserving their order/output. Other cases use explicit research-shaped synthetic evidence. No real market eligibility or fills are claimed.

Candidate publication is supplied to the injected ranking verifier. The verifier must independently enforce current issuer/generation/source/cohort/revocation/high-water and return an immutable, deterministic receipt bound to the complete source bundle. Instrument/quote verifier separately authenticates stable listing identity, supported long/fractional USD share rules, rule revision and the original execution quote. Mutable registry flags, local hashes, caller-shaped verification objects or `manual=True` are never an operational authority. No actual issuer/current-pin verifier is supplied by this implementation.

The current implementation accepts an explicit whole-second timezone-aware source timestamp or exact integer epoch; fractional-second timestamps refuse rather than being silently rounded into freshness. No binary-float financial fill price is accepted. `execution_price` must be an explicitly attested Decimal string; the adapter does not turn an existing display price, midpoint, research price or float into an invented fill. Research scores and existing classifier ladder limits remain their original research values. Actual provider snapshot normalization/price semantics, rights and precision need independent acceptance.

Ranking issued/expiry bounds are <=600s and financial quote age <=30s, with future/expired/tombstoned/missing/changed data refusing. The decision is reverified from original sources under the accepted owner lease, not from a candidate digest supplied by the client. The same lease must serialize financial writers and candidate invalidation. Returned verification receipts must stay stable for the same immutable publication; time/current eligibility is checked separately on every new attempt. Renewing a receipt must not silently grant a new financial signal.

A frozen reached observation alone is insufficient when price has moved above that level. This gap was reproduced during implementation and corrected in both adapter and canonical V3 validation. The existing ladder/classifier is retained, not recalculated into a new strategy. Held positions can remain overnight and manually exit without still meeting entry-rank/ladder conditions.

## Admission, publication and UNKNOWN contract

The dispatcher performs current evidence and owner checks, exact manual reservation, snapshot and canonical preflight before financial publication. It checks decision time again before and after durable admission preparation. The injected admission port must persist operation request digest, PENDING/ACKNOWLEDGED/UNKNOWN status and enforce complete writer exclusion. Its owner verifier must establish actual accepted ownership/resource scope; test strings or cooperative locks are not operational proof.

FS2 remains canonical. The dispatcher compares the returned receipt to its exact preflight result, including payload/policy/state/source/position identity and `projection_required=True`; then independently requires the projection verifier before final admission acknowledgement. The FS2 implementation itself retains intent/record/commit/projection/ack/current-pin ordering. A missing, inconsistent or lost acknowledgement produces UNKNOWN and blocks all new financial effects through durable admission state. Retry of an exactly acknowledged request returns the prior receipt; a conflicting request cannot reapply it. No uncertain callback is replayed or automatically reconciled. Final source review also tightened revalidation of prior acknowledgements: lost/corrupt projection proof or ambiguous admission state persists a global UNKNOWN barrier. A known operation-ID conflict is an explicit refusal, not a new ambiguous fill. Original fixture admission evidence is retained with the UNKNOWN record.

Known publication/storage/protocol exceptions produce UNKNOWN, not success. Unexpected exceptions or process interruption after prepare leave durable PENDING refusal evidence; they are not converted to clean completion. If writing the UNKNOWN marker also fails, the response explicitly says `durable_refusal_recorded=False`; no durable latch is promised. Independent recovery remains required. The shared admission port and manual reservation must be durably implemented/accepted before runtime use; this task supplies no protected version.

Native current-pin custody, clock and writer ownership are injected prerequisites. FinancialStorePublisher requires independent exact store/inception scope verification; a matching hash alone is not independent custody. Operational direct calls to a pure transition or a disposable FS2 constructor are not authorized by these schemas or interfaces.

## Read-only API contract and limitations

The router is not included in `main.py`. No HTTP listener or Atlas process was launched. Tests call the factory endpoints directly, so this is route-contract acceptance, not browser/network acceptance. POST is403 unless explicitly injected; a supplied dispatcher still checks all evidence/admission/manual conditions. Refusal messages expose only bounded uppercase reason codes, never private exception paths or credentials.

GET uses only accepted committed projection/report readers plus independent verification. It checks exact account/epoch/version/source identity/revision/freshness and structural cash/P&L/quantity consistency; returns UNKNOWN or UNAVAILABLE on failure. Cash, gross/net/costs, open positions, report completeness, unsupported valuation and lifecycle status remain separate. Aggregate fee/slippage breakdowns are unavailable unless an accepted report reader supplies separately reviewed evidence; this implementation does not invent them. Accounting acknowledgement never means clean shutdown. Stale immutable history is not asserted to be a fresh current balance.

Tests prove byte-identical fixture files across GET, no invocation of extra provider/writer/close/start/clear callbacks, refusal of forged/foreign/stale/unavailable read payloads, and no default POST dispatch. **Arbitrary malicious Python code inside an injected `read_committed` or verifier cannot be sandboxed by a router.** The host must install independently accepted read-only capabilities; the API never accepts dependency objects from an HTTP caller. No claim of protection against malicious same-user/admin code.

## Exact validation

Final single combined run: **265 passed,0failed,0skipped**,17.01s. Counts are disjoint by collected test module:

| Module | Passed |
|---|---:|
| test_quality_dips_integration_v1 | 74 |
| test_quality_dips_selected_policy | 37 |
| test_fs1_financial_replay | 37 |
| test_paper_epoch_fixture | 24 |
| test_paper_strategy_fixture | 21 |
| test_q7_paper_portfolio | 18 |
| test_q8_runtime_boundary | 16 |
| test_q9_paper_application | 35 |
| test_r7e47cg_production_startup_lock | 3 |

Targeted Ruff passes for8 source/test files;8files compile in memory;checkpoint updater PowerShell parsing and diff checks pass before publication. Earlier29/48/249/256/258/259 runs and focused cases overlap and are not added. Legacy V1 golden reconstruction remains byte-identical in its tests. Existing untracked files and failure diagnostics remain local and excluded from Git publication.

Coverage: distinct stocks/ETFs; real existing board/V3 pure calculations; current/replaced/expired/revoked/future ranking; cohort/identity and source substitution; fractional support; source/rule revisions; manual cancellation/replay; position/cash/notional/precision controls; partial/full exits and overnight; concurrent duplicate dispatchers; invalidation-before-entry and exclusion-through-ack; missing projection/lost post-commit ack; fresh restart after UNKNOWN; and five abrupt subprocess boundaries(before intent,during record,after commit,after ack,after financial current-pin advance). Pending/incomplete/corrupt evidence refuses new effects; only fully acknowledged fills advance a usable projection.

Original failures retained: first integration assertion expected an extra trailing zero (`9.9200` versus existing correct`9.920`); corrected fixture expectation without financial arithmetic changes. Then the fresh-price-above-frozen-level adversarial test failed DID NOT RAISE; code repaired before final run. No failures are suppressed or reclassified as passing.

## Native and trust boundary — not executed/accepted

To obey the prohibition on creating protected native storage, the integration harness imports the unchanged FS2/FS3 function/class code through a controlled loader, replacing only module-level native-loader assignments with explicit ordinary-file primitives. Native handle/ACL/mutex/identity operations and constructor enrollment are not executed. The actual FS2 record/receipt/replay/audit and FS3 projection methods execute over disposable files with file fsync and explicit fixture custody. Coordination in these tests is cooperative, not native ownership proof.

These tests demonstrate protocol integration and process-crash refusal, not Windows handle-bound security, parent-junction/symlink resistance, independently protected pin custody, complete namespace exclusion or power-loss durability. Native tests executed this milestone:0;native operational acceptance:BLOCKED, not pytest PASS. Prior true-symlink NOT EXECUTED and coherent rollback/issuer/clock/backup/recovery limitations remain unchanged. No privileged enrollment, real account, provider, private financial history or Genesis access occurred.

## Exact continuation toward the frontend

Next bounded source task: connect a selected-account panel in existing `backend/app/static/quality_dips.html` to this read-only contract using disposable app tests. It must not poll the old mutating research GET while claiming a financial read-only mode. Display candidate selection/rejection reasons, exact account/source revision, acknowledged cash/positions, unavailable valuation, report completeness and UNKNOWN. Do not redesign or create another dashboard. Operational router registration, actual capability installation and worker/startup changes require separate explicit authorization after their prerequisites are independently accepted; no such permission is inferred here.

Still required:B1V3 independent capital/exclusions/risk/instrument scope review;C1 actual writer/resource roster, ownership/exclusion/drain;D1 protected storage,enrolled issuer,current-pin/high-water,clock,rollback/recovery;E1 provider rights/real quote rules,backup+isolated restore,native lifecycle and supervised release. Injected fixtures do not satisfy them. The accepted instrument registry remains immutable; adding/updating real instrument rules needs a reviewed enrollment/version-continuity process, not a caller mutation.

Seven phases:1core reliability/Windows PAPER incomplete;2EvidenceEngine/AFI HOLD,AFI1–10PENDING/0accepted;3historical/prediction expansion BLOCKED(optional15-minutecrypto deferred);4Cross-Market pending;5SaaS pending/deferred;6institutional pending;7commercial pending. Original definitions,history and21decisions are preserved. No operational readiness promotion.


## Quality Dips frontend V1 offline acceptance — 2026-10-24

P-QD-FRONTEND-V1-OFFLINE completed. Existing screen selected-account mode reads only the unregistered selectedGET;no trade controls,legacy fallback,provider or startup calls. Exact decimal cash/positions,optional verified inception,reason/status/cutoff displays.271Pythonpassed/0failed/0skipped(includes5newapplicationcases+1retainedUIwrapper);25separateJSunitpassed. DOM/fetch fixtures only;no realbrowser/server/native acceptance. See QUALITY_DIPS_FRONTEND_V1_ACCEPTANCE_2026-10-24.md. ZeroACTIVE;BLOCKED_WAIT for independentB1/C1/D1/E1 and separately approved accepted read-capability binding/router registration/supervised acceptance. All21decisions and7phases preserved;PAPERstartupNO;productionNO-GO. No more standalone dashboard is required.
