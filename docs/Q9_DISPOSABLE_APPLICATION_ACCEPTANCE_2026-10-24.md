# Q9 — disposable PAPER application acceptance

Base `de27e47c382d05f53ce35c8d5270cf06478a3972`; branch `chatgpt/atlas-rebuild-v1`.
**PAPER startup NO. Production NO-GO. All 21 governance decisions unchanged. B1/C1/D1/E1 BLOCKED. Phase 2 HOLD; Phase 3 BLOCKED; AFI-1–10 PENDING.**

## Scope and repository recovery

Read the complete master roadmap, its permanent operating/recovery/reporting/cleanup instructions, Q7/Q8 reports, autonomous state/queue/recovery and strategy matrix. Base and branch matched; tracked working tree was clean. Existing untracked path inventory was retained locally and not staged wholesale. Root/ancestor and applicable backend/test AGENTS instructions were checked; no such files found. Frontend instructions remain applicable only if frontend code changes; none changed here. No private N2 records or inventories were opened. No operational financial stores, providers, services, Docker, Genesis or unrelated processes were accessed.

## Working application demonstration

`backend/app/services/paper_dashboard_demo.py` supplies an unregistered WSGI callable. There is **no server runner, route registration, listener, default source, store constructor, provider import or startup integration**. Tests invoke it in-process using standard request/response dictionaries. Its only demonstration resources are GET `/` and GET `/summary.json`; every other verb/path/query refuses before a read dependency runs. These are resources on the inert object, not new Atlas operational endpoints.

The page reuses Q8's version-2 escaped table and Q7's unchanged versioned summary JSON. It displays strategy/epoch, explicit simulated opening cash, audited current cash, realized gross P&L, combined trading costs, realized net P&L, remaining quantities, source revision and financial-event freshness. Costs combine fees and slippage under the existing fixture policy; the summary does not support separately evidenced allocations, so the page explicitly calls those unavailable. It never invents equity, unrealized P&L or account totals. UNKNOWN and INCOMPLETE remain visible, with source reason codes. Labels, table structure and account-navigation conventions follow the existing simple Atlas read-only surfaces without duplicating the operational frontend or calling its mutable GET APIs.

A self-contained local example was rendered to ignored `logs/diagnostics/q9/dashboard-demo.html` from new disposable Quality Dips and actual native-interface Hyperliquid fixtures. It shows open/partial positions and INCOMPLETE truthfully. No browser, HTTP host or operational dashboard acceptance was performed. The JSON navigation link is usable when the callable is hosted by a separately approved test harness; opening the saved static HTML alone does not start that harness or provide JSON navigation.

## Verified read bridge and trust limits

Construction is inert until both the Q8 read boundary and a separate verifier are injected. The boundary validates exact strategy/epoch bindings, schema/authority/freshness/source evidence and observed revision continuity. Before rendering, the application requires the verifier to return the SHA256 commitment of the exact canonical JSON bytes. In tests the verifier independently re-reads original disposable events and native projections through Q7's separate arithmetic audit, compares the complete snapshot, then returns its commitment. A valid-shaped forged balance therefore fails rather than becoming dashboard truth. A boolean approval is rejected. Changed sources between reads refuse instead of yielding a mixed snapshot. Rendering uses the same verified snapshot, not a second source read.

This dependency-injection seam is **not cryptographic authenticity or an accepted production trust anchor**. A malicious caller can inject a dishonest verifier; callers cannot use this prototype as operational authority. The default refuses, no runtime selects a verifier, and B1/D1 remain mandatory. UNKNOWN can be accurately shown when independently derived from unavailable/corrupt fixture evidence; verification never clears the underlying pending operation. Expected read/validation/storage failures produce 503 UNKNOWN, no cached success and no private exception detail in responses. The original exception is retained only in the local object's diagnostic field, not serialized or persisted as a durable audit receipt. Unexpected interpreter errors propagate as failures, never successful responses.

Responses are bounded by the existing summary validation plus a 256 KiB encoded-summary cap, use `no-store`, `nosniff` and a restrictive no-script/no-resource CSP. There are no browser scripts, refresh-provider selectors, write forms or backend links. This is not a general resource-exhaustion guarantee: an injected callback must independently meet bounded-read requirements and the adapter does not terminate blocked callbacks or change lifecycle deadlines.

## Inert selected-lane write expectations

`backend/app/services/paper_write_request_contract.py` defines `PAPER_WRITE_REQUEST_INERT_V1` for Quality Dips and manual Hyperliquid. It validates exact fields, explicit epoch/strategy, epoch-scoped operation identity, ENTRY/PARTIAL_EXIT/FULL_EXIT intent, position binding for exits, expected source revision/head and `PAPER_RECEIPT_FIXTURE_V1` expectation. Extra approval flags, foreign bindings, boolean revisions, missing heads and unversioned receipts refuse.

**Every syntactically valid request also refuses EXECUTION_DISABLED.** No writer, callback, financial payload router, accepted-epoch issuer or success switch exists. Syntax does not establish that an epoch is independently accepted; no accepted epoch was supplied here. Price/quantity/risk execution remains with already-tested fixture adapters, not an incomplete alternate financial engine. Production entry/exit callers, native writers, storage, startup and dispatch remain byte-unchanged. Successful runtime routing still requires separately accepted interfaces and explicit file-level implementation approval.

## Writer, shutdown and restart evidence

The new scenarios reuse `paper_writer_fixture` admission/drain and actual Q7 native projection interfaces; no second coordination framework was created.

- Admission closes durably before drain; a new operation after closure refuses.
- Pending callbacks yield INCOMPLETE/TIMED_OUT; missing owner, changed incarnation and unexpected competing writers refuse the exact roster.
- A projection interruption after canonical financial commit retains UNKNOWN. Writer retry does not invoke the uncertain callback again; drain remains incomplete; daily report publication and restart/new-write attempts refuse. The single committed event remains retained.
- Native projection receipts deliberately removed in a disposable fixture cause dashboard UNKNOWN. Repeated reads neither acknowledge them nor modify any fixture file.
- Complete durable final exits can generate RECONCILED_FIXTURE_ONLY reports, but neither report nor presentation grants startup/shutdown authority.
- Repeated dashboard HTML/JSON reads leave every disposable source file byte-identical. Both source accounts retain independently reconciled cash, quantities and revisions.

No native ownership/external-writer exclusion, protected namespace guarantee, operational shutdown, process termination, power-loss durability or real-session acceptance is inferred. Existing native journal/manual competing writers and Q8 shutdown ordering/report gaps remain unresolved. No deadline changed.

## Full strategy coverage continuation

Existing source inventory and Q7/Q8 statuses remain in force. No strategy receives runtime or operational promotion in Q9.

| Existing family | Q9 bridge reuse | Remaining strategy-specific requirement |
|---|---|---|
| Quality Dips legacy/V2/V3 | Disposable audited account/demo verified | Accepted native partial/cost/cash routing, patient holding/terminal policy, ownership and source scope |
| Hyperliquid manual BTC/ETH/SOL | Disposable native projections and audited account/demo verified | Accepted canonical routing, receipt authority, all-writer ownership, venue/cost scope and native lifecycle |
| Hyperliquid automatic setup/adaptive mirror | Presentation shell reusable; current adapter not activated | Separate automatic scope, pending/cancel/partial/risk/cash semantics; excluded from manual first session |
| Crypto micro coach, major/alt/meme/junk tiers | Presentation shell only after separate account schema | Frozen tier/risk/source/cash contract; not a newly discovered spot wallet engine |
| Long-term stock/ETF investment book | Presentation shell; current two-strategy schema refuses direct reuse | Sell/partial/corporate actions, accepted cash/cost basis, long-term calendar and holdings |
| Equity day-trading mirror | Presentation shell after accepted summary adapter | Pending/cancel durability, exchange session/calendar, separate funded account and writers |
| Stock/BTC accumulation alerts and investment board ladder | Evidence-health concepts only | Research/manual-buy alerts, not independently funded PAPER accounts |
| A+ balanced/mean-reversion/momentum/breakout | Signal provenance only | Accepted downstream account consumer; do not create four ledgers |
| ATR/Keltner/squeeze/anomaly/funding/whale/context | Research evidence only | Provenance/rights/freshness; indicators do not establish fills |
| V4 deterministic/shadow PAPER | Shell after separate shadow account semantics | Separate authority, cash/receipt/drain and replay contracts; no balance pooling |
| V5/V6/E28/E29 challenger/rejection research | Research diagnostics only | Independent licensed evidence; not autonomous financial accounts |
| Prediction pre-event PAPER | Shell after separate contract schema | Contract units/depth/fees/cutoff, expired-unclosed handling and cash; excluded from this scope |
| Crypto Quality Dips research | Research evidence only | No approved valuation/fill/position/cost engine; no invented financial state |
| Portfolio/ETF/benchmark/manual research/morning brief | Read-only evidence concepts only | Accepted holdings/source/cash provenance; no broker/rebalance authority |
| AFI/replay/holdout/prospective research | Evidence presentation concepts only | Witnessed licensed acceptance; forecast output is not execution authority |
| Extended-hours observation | Evidence freshness concepts only | Provider rights/budgets and authorized observation runtime; no financial positions |

Reuse means versioned interfaces and presentation components, **not accepting additional strategies into the unchanged Q7 two-lane schema**. Different currencies, instrument units, calendars, costs, risk and cash semantics require explicit accepted adapters. No unreconciled account consolidation.

## Exact validation and original failures

Final combined selection: **224 passed, 0 failed, 0 skipped in 29.09s**, including **35 new Q9 cases**. It includes the prior Q8 182-case selection and seven existing all-writer cases. Earlier focused 33/35-case runs overlap and are not added. Prior 412 Python/763 JavaScript results were not rerun or added. No frontend source changed; no JavaScript build/browser acceptance claim.

Original focused run: **1 failed** because the new fixture assertion omitted allocated committed costs (`927.50` expected versus correct `927.48`). Original log retained at ignored `logs/diagnostics/q9/focused.txt`; test expectation corrected after independent source inspection, accounting logic unchanged. Two initial Ruff findings (broad exception handling and import formatting) were corrected without suppressions. Final targeted Ruff, Python compilation, three PowerShell parses and CRLF-aware diff checks pass. Full combined log: `logs/diagnostics/q9/combined.txt`.

Tests cover two-account integration, untrusted summaries, versions/source heads/authority/consolidation, stale evidence, prohibited request paths, verifier failure and no cached success, immutable source reads, UNKNOWN retention, inert entry/partial/full refusals, invalid receipt expectations, exact writer rosters, pending drain and final report refusal/acceptance without authority. Tests use disposable stores and retained native interfaces only; no operational endpoints/services.

## Remaining approvals and exact next action

1. **B1:** independent archive/source/epoch-scope disposition and accepted inception/risk/cost evidence. Synthetic opening cash and local arithmetic are not those artifacts.
2. **C1:** actual writer/resource/process ownership, entry closure and complete drain/quiescence evidence, including competing native/metadata/API/standalone writers or independently proven exclusion.
3. **D1:** accepted protected identity-before-access storage, trusted issuer/operator/clock and rollback/recovery authority; separate provisioning permission.
4. **E1:** provider/account/purpose rights and budgets, separately authorized continuity, backup/isolated restore/native lifecycle acceptance, independent governance review and explicit supervised session permission.

Next engineering action after evidence adjudication: separately approve the accepted selected-lane canonical storage/receipt/all-writer interfaces and a narrow native caller integration plan, then disposable route/UI/shutdown acceptance before any operational window. This demo supplies no approval or bypass. All authorized Q9 offline tasks are complete; further protected routing, provisioning or real-session execution crosses a genuine authorization/evidence boundary. No new task is invented to avoid that boundary.
