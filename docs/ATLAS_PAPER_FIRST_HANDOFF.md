# PROJECT ATLAS — PAPER-FIRST CANONICAL HANDOFF
Updated 2026-11-07. Read this first when resuming in a new ChatGPT conversation, Desktop Commander session, or coding-agent session.

## Single immediate objective
FINISH BUILDING and operate a stable LOCAL WINDOWS autonomous PAPER-only trading bot for months of forward profitability evaluation. The milestone is not more commits, test counts, or enterprise readiness. It is a correctly authorized supervised PAPER start followed by reliable autonomous scanning, simulated trading, journaling, reporting, and long-term forward observation.

## Permanent scope freeze
- NO real-money trades or brokerage order execution. Real-money trading remains disabled until months of convincing forward PAPER profitability evidence and a separate explicit operator decision and authorization. Do not silently prepare live activation.
- NO VPS, enterprise hardening, extra strategies, Genesis work, unrelated architecture, or production-only enhancements.
- Robinhood-eligible broad market research for stocks/ETFs and other actually supported instruments; Hyperliquid is the exclusive perpetuals market. Do not assume Robinhood entitlement or tradability from a symbol list.
- No per-trade manual confirmations during an approved PAPER session; automatic scan, simulated entry, risk-managed exit, reconciliation, Discord alerts, dashboard and daily performance reports.
- Local Windows 11; do not enable automatic startup after reboot without authorization.
- Preserve financial correctness, provider rights, and existing B1/C1/D1/E1/AIP-06 gates. A proposed narrower PAPER-only acceptance policy requires independent review; never reclassify or bypass gates unilaterally.

## Definition of DONE BUILDING (PAPER)
1. Legitimate authorized fresh public observations for eligible markets, bounded/rate-limited, with clear missing-data behavior.
2. Continuous autonomous strategy decision -> simulated entry -> management -> exit, including risk stops and no real-order path.
3. Durable isolated simulated cash/positions, fees, slippage, P&L, reconciliation, and restart/stop correctness.
4. Working read-only dashboard, Discord PAPER alerts, daily reports, and provenance for performance metrics.
5. End-to-end integrated disposable tests and required guarded acceptance, explicit supervised PAPER startup approval, then monitored forward PAPER running. No claim of profitability until sustained forward evidence.

## Verified checkpoint and remaining gap
Branch chatgpt/atlas-rebuild-v1. Before this handoff latest HEAD be362aaa (Batch 2 offline regression evidence). 330 selected offline tests passed; this is NOT operational acceptance. On 2026-11-07 Desktop Commander also verified 20/20 targeted disposable transaction/journal lifecycle tests passed. Existing QD and Hyperliquid proposal engines, accounting, dashboard and alert modules exist. Their continuous integrated operation with fresh public data is NOT verified.
POST_V2_PAPER_ACCEPTANCE_MATRIX_2026-10-26.json remains 18/18 BLOCKED; no operational startup authority, no provider rights evidence, F11 guarded native scenario not accepted. Do not pretend these are finished.
The shortest technical next task: map the actual full pipeline from observer to PAPER trade to accounting to dashboard/alert, identify the FIRST missing connection, implement it and prove an integrated disposable scenario. Do not rerun unrelated large suites as a substitute.
After integration, isolate exactly which current gates apply to supervised PAPER, who must independently approve them, and what data rights are required. Do not start operational services before those are resolved.

## Operating instructions for future conversations
At the beginning of every new Atlas chat, use Desktop Commander to read THIS FILE, the canonical roadmap, docs/ATLAS_AUTONOMOUS_STATE.json, current git HEAD, and the acceptance matrix. Resume the next unfinished milestone. Do not re-plan from scratch or restart completed tasks. Prefer one multi-milestone execution batch; commit and push verified changes. Never touch Project Genesis. Update this handoff when priorities, verified progress, or blockers change. Report concrete functionality, not just test counts. If blocked, do the next independent necessary task rather than expanding scope.

## Status
BUILD NOT DONE; PAPER OPERATION NOT AUTHORIZED; REAL MONEY DISABLED.
## 2026-11-07 Commander pipeline inspection — first concrete integration gap
- Verified 20/20 targeted disposable journal transaction and lifecycle tests with Python -B and PYTHONDONTWRITEBYTECODE=1. These include fixture quote -> entry -> mark -> exit -> disk replay, but the fixture explicitly calls open_lot/close_lot; it is NOT a running autonomous decision-to-fill pipeline.
- backend/app/services/personal_paper_strategy_signal.py: evaluate_iex_quality_dips_signal and inspect_leased_iex_v3_candidate produce research/quote decisions, explicitly return paper_fill_authorized=False. Research attestation is separate.
- backend/app/services/quality_dips_autonomous_runtime.py: a bounded runtime accepts observation frames and calls engine.step(), but its operational start requires preexisting grants/admission.
- backend/app/services/personal_paper_fixture_executor.py: disposable quote-to-journal executor expressly rejects FORWARD_COLLECTION accounts, so it must never be reused as a forward execution bridge.
- tests/test_personal_paper_transaction_lifecycle.py: test_full_disposable_producer_operator_iex_candidate_entry_exit_restart explicitly invokes open_lot/close_lot after inspection; therefore this is the FIRST unverified connection: authenticated/provenanced observation + strategy decision -> risk-admitted automatic simulated fill through an authorized PAPER-only writer, then report/alert publication. Do not solve it by flipping paper_fill_authorized or treating fixtures as real provider authority.
- Next source milestone: inspect existing QD unified native planner/writer and source publication ports to determine whether they already provide that exact authorized connection; add a disposable integrated test that exercises the actual automatic decision and writer without manual open_lot/close_lot calls, preserving native guards. If no authorized port exists, implement a narrowly scoped PAPER-only adapter under existing gates; never use real broker order paths.