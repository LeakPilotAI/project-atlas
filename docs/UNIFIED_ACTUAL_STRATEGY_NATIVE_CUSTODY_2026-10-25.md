# Actual two-strategy native custody increment

Base: `79a53cab9509c27d3675bb49e613a2a67bc50d0f`. This is source/disposable
evidence, not an independently accepted operational deployment. The sole task
UNIFIED_PERP_FINANCIAL_COMPLETENESS remains ACTIVE. No protected account,
credential, provider, operational service or Genesis resource was accessed.

## Implemented

| Files | Actual responsibility |
|---|---|
| `backend/app/services/perp_source_planner.py` | Reuses existing shortlist, candle analysis, ranking, research ladder, setup lifecycle, board and static exit classification. Requires authenticated current source, executable book, instrument/fee policy, lifecycle and separate maker queue/trade evidence. Funding uses parsed history plus authenticated historical settlement oracle; marks become source-versioned native commands. No provider refresh. |
| `backend/app/services/perp_resting_order.py`, `perp_resting_writer.py` | Immutable original order; fractional precision/risk/expiry; durable ARM/FILL_PENDING/ACK/CANCEL. Actual original canonical writer executes once. Partial maker execution explicitly cancels the remainder. A mark touch, resting/manual label or order acknowledgement never establishes a fill. UNKNOWN blocks replay and cancellation. |
| `scripts/volume_inspector/resting_order_store.py`, `unified_portfolio_store.py` | Existing FS2 creation-handle identity, exact native namespace/ACL reader, writer mutex/latch and immutable predecessor protocol reused for bounded control records. External authenticated durable current-pin CAS required; distinct test/operational schemas. No operational provisioner, issuer or recovery/adoption path. |
| `backend/app/services/quality_dips_publication_reader.py` | Existing-only authenticated ranking/monitor publication reader, bounded current source revision, rollback/conflict refusal, original V5 candidate ordering. Never refreshes scanner or adopts legacy balances. |
| `backend/app/services/unified_portfolio_custody.py` | Both actual source identities and original native receipts bound to durable global SESSION/CLOSE/RESERVE/ACK/FINAL control. One native cross-process reservation mutex; accepted risk/ownership/clock ports mandatory. Pending exposure participates in existing portfolio risk validation. No USD/USDC conversion default. New grants cannot adopt open positions, resting exposure, pending effects or an unfinalized prior session. |
| `backend/app/services/unified_paper_runtime.py`, `unified_native_writer.py`, `paper_financial_replay.py` | Existing continuous supervisor routes admitted orders, actual canonical fills/funding/marks, reducing cancellation and both original shutdown coordinators. Durable financial uncertainty closes global admission instead of masquerading as scanner unavailability. Final native report cuts and global drain must acknowledge before financial STOPPED. |
| `scripts/observation_runtime/quality_dips_read_service.py` | Existing loopback host can accept the existing Stop bridge only with separate authenticated control-composition acceptance, before listening and again when building the app. Default remains GET-only. No production route or startup registration. Financial POSTs stay refused. |
| `backend/app/static/quality_dips_selected_paper.js` | Additive separate USD/USDC native-cut presentation using original styling. Exact quantities, funding, costs and source cuts; unavailable valuation and unknown spendable cash for reserved orders. No combined account balance/equity or financial controls. |

The QD path uses actual IEX parsing, candidate validation, the existing V5
preview/expected-command guard, SQL coordination and original native writer.
It does not dispatch a parallel QD financial writer. The perp path uses the
existing canonical financial transition, replay, independent audit and FS3
report service. No second financial engine was introduced. Existing strict,
manual and disposable financial record formats are unchanged.

## Evidence and limitations

The new tests use both actual strategies, not a synthetic counterpart lane.
Market observations, session/issuer/ownership acceptance and pin custody remain
explicitly synthetic. Real native file handles, immutable records, Windows
cross-process mutexes, abrupt self-exiting children, HTTP and PowerShell run.

The complete cycle includes QD entry, partial/full exit, perp resting admission
without a fill, authenticated partial maker entry, separately sourced funding,
mark, exit, separate account replay/audit/cash reconciliation, both shutdown
coordinators, immutable session reports and a durable global final outcome.
Global and order custody races produce one durable effect. Children exit before
publication, between publication/current pin, after pin and after native fill
ACK before order/global ACK. Uncertainty is retained, not blindly replayed.
Source rollback/conflict/missing monitor and new-grant adoption are refused.

Genuine loopback tests exercise the shipped `Invoke-AtlasPaperStop` action,
not an interactive WinForms click. GET hashes are unchanged, financial command
POST/legacy research GET/foreign Host refuse, foreign owned-host close refuses,
and the exact listener closes gracefully and releases its port. This does not
prove a complete real operational process roster has exited.

A genuine in-app browser opened the original selected-account HTML against a
bounded disposable host. It showed both native account cuts, QD's acknowledged
position and a perp RESERVED order explicitly marked "not a fill". Fixture
timestamps are future-dated relative to the real workstation clock: the UI
correctly showed STALE/CLOCK UNCERTAIN, not fake fresh market activity. Pending
order available cash and unrealized equity were UNAVAILABLE. Screenshot and AX
evidence are in the execution transcript; the local fixture result records
unchanged native evidence and reconciled shutdown. No complete browser network
capture, interactive WinForms acceptance or operational market session is claimed.

Failures retained: initial two-lane fixture lacked its actual global reservation
binding; HTTP fixture initially used the wrong enrollment nesting; a raw Node
invocation omitted required generated application-frame arguments; the first
browser hash check included its own explicit finish marker. These fixture issues
were corrected without relaxing financial assertions. Native read-service tests
initially skipped twenty cases with a missing confinement variable; the correctly
confined rerun executed all 26. No skipped case was counted as a pass.

Native control capacity is deliberately 128 transitions with hard refusal and
no rollover. Long-running operation beyond that bound is not established.
Source revision continuity across restart depends on accepted external current
custody. Local synthetic CAS files do not establish independent anti-rollback.
Late/missing historical funding settlement requires separately accepted recovery;
it is never zero-filled. Abandoned writers/unpinned tails refuse recovery. No
power-loss, same-user/admin hostile-code immunity or operational custody claim.

## Remaining source and acceptance work

1. Bind installed QD ranking/monitor publications and Hyperliquid raw market,
   candle, executable trade/queue, metadata and historical settlement-oracle
   producers to these exact current-source ports. Existing legacy manual/mark
   mirror state must never become execution or source authority. Provider
   activation is not authorized by this increment.
2. Complete the actual workstation writer/resource/process roster and its
   accepted ownership/drain adapter. Bind final financial Stop to the existing
   retained owned-process closure capability, with process-exit and port-release
   outcomes distinct from financial flatten. The current global FINAL certifies
   financial/report drain only; it is not process shutdown authority.
3. Independently resolve native control capacity/continuation policy and restart
   custody for continuous operation. Do not silently roll journals or reset pins.
4. Execute the resulting full retained-child two-lane lifecycle and interactive
   Control Center acceptance with all actual source ports. Current real HTTP,
   browser and child-crash evidence does not replace that remaining acceptance.

B1: scoped independent acceptance of both new epochs, hypothetical opening
capital, legacy exclusions, eligible instruments and risk/accounting policy.
C1: complete actual writer exclusion, ownership and final process/drain evidence.
D1: accepted personal-profile issuer, clock continuity, current/high-water
custody, resources and recovery; acknowledged reduced assurance is not provisioned
authority. E1: provider rights, executable market/session/halts/lot evidence,
backup/recovery and supervised release acceptance. All remain BLOCKED.

After those source/acceptance conditions, separately authorize dependency
installation, account inception and a bounded supervised launch. Only then may
the seven-day autonomous PAPER trial begin, with daily financial/data/lifecycle
evidence. It has not started. All seven phases and 21 historical decisions are
preserved. D:-only, existing account, original alien UI and startup refusal remain.
PAPER startup NO; production NO-GO.

## Final validation

- 622 passed / 0 failed / 1 skipped: broad financial, native FS1–FS3, perpetual discovery/execution/recovery/reporting, unified risk, startup refusal and roadmap archival tests.
- 155 passed: QD source/V5/unified shutdown/native/runtime/retained-child HTTP selection.
- 32 passed: operational QD codec/factory. 30 passed: operational perp codec.
- 30 passed: final new native order/source/global custody/race/crash/two-real-lane/HTTP/Windows Stop selection (one combined run).
- 26 passed: native read-only service compatibility; 5 passed: disposable frontend application frames.
- These final selections overlap by 47 cases: **853 distinct Python passes, 0 final failures, 1 true-symlink privilege skip (1314)**. Not a single 853-case combined run.
- 42 JavaScript presentation cases passed, including separate currencies, pending order labels, unavailable metrics, stale/conflicting evidence, escaping and no legacy mutating GET. Generated-frame Node scripts were executed via their Python wrappers, not raw Node test mode.
- Ruff on changed/new Python sources and tests, compilation, PAPER static policy audit and archival preservation checks passed. Browser observation is additional manual evidence, not added to automated test counts. No power-loss or operational acceptance.

Final supervisor/archive repeat:39 existing cases passed in the permitted native environment after a restricted repeat stalled at the known Windows async boundary and was interrupted through its exact tool session. These39 overlap the selections above and are not added again. Three shipped PowerShell files parsed; original main/startup lock/HTML/Windows controls/golden bytes verified unchanged.


## Retained owned-close continuation — 2026-10-25

Continued beyond the first published increment30170410:existing UnifiedControlStopBridge now reuses close_verified plus independently verified exit after actual financial FINAL and global drain. Exact ATLAS_UNIFIED_OWNED_ROSTER_V1 binds session, native PID/creation/image roster, accepted writer-roster digest and separate account digest. Accepted portfolio ownership lease/native global mutex stays held through close. No process discovery,kill,force or name/port termination. Genuine loopback test gracefully exits two exact retained fixture children;foreign roster/account/refused authority or missing exit ACK stays INCOMPLETE,without falsely changing a proven FLAT financial state to POSITION_OPEN. Default no owned-close remains NOT_REQUESTED,not process-exit acceptance.

Final42case combined native-child/HTTP/supervisor selection passed0fail0skip;37overlap prior853,5new=858distinctPythonpasses/0finalfail/1true-symlink NOTEXECUTED.42JS retained;not a single858case run. Earlier69case overlapping selection also passed;not added. Initial HTTPConnection fixture cleanup error retained and fixed with contextlib.closing;no financial assertions weakened. No actual operational process roster accepted. Sole ACTIVE task remains UNIFIED_PERP_FINANCIAL_COMPLETENESS. Next authenticated actual source producers,independently accepted complete roster/custody and bounded capacity/continuous/interactive acceptance. Existing financial/Stop/owned-close source ports are now done;do not repeat them. All21decisions/sevenphases/B1C1D1E1BLOCKED unchanged;PAPERNO;productionNO-GO.
