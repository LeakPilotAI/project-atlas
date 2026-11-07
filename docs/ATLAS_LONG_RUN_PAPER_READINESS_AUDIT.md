# ATLAS LONG-RUN PAPER PRODUCTION READINESS AUDIT
Audit date: 2026-11-07
Status: NO-GO / NOT ACCEPTED
Scope: local Windows 11, autonomous PAPER only. Never authorize live trading.
Evidence: git HEAD 4df296e7, tracked desktop launch/stop scripts, startup guard, unified stop bridge, stop receipt ledger, canonical roadmap.
This is a gap inventory, not an operational certification. Items marked unverified require independent proof.

## P0 - blockers before even a supervised commissioning run
- [ ] Native desktop Start: ATLAS.bat calls scripts/windows/Atlas-Launch.ps1, which explicitly refuses legacy startup. Establish independently accepted PAPER startup, owned session identity, single-instance lock, provider grants, and evidence-backed readiness. Do not bypass guard.
- [ ] Native desktop Stop: ATLAS-STOP.bat calls scripts/windows/Atlas-Stop.ps1, which explicitly refuses legacy shutdown. Bind authenticated local stop to exactly the accepted owned session; block new entries, drain, flatten PAPER positions, reconcile, persist receipts, verify owned exits. Never kill Genesis or Docker Desktop.
- [ ] Confirm B1/C1/D1/E1 readiness decisions from independent evidence: archive completeness or approved epoch, owner/drain, trusted storage/authority/clock, provider rights and supervised session. No automatic promotion.
- [ ] Ensure every intended Robinhood-market strategy and Hyperliquid-only perpetuals lane has explicit PAPER account/provider mapping, symbol universe completeness, unsupported-symbol disposition, market-session and order constraints, cost model, and accepted source rights.
- [ ] Validate stop safety across normal close, emergency, restart during stop, process crash, stale ownership, corrupted receipts, incomplete flatten, and network loss. All uncertainty must fail closed.

## P1 - required before leaving Atlas unattended for months
- [ ] Execute supervised end-to-end PAPER commissioning with actual configured providers and no live order capability; prove multi-market discovery, selection, entries, exits, reconciliation, and audit trail.
- [ ] Prove restart-safe PAPER accounting: idempotency, no duplicate orders, persistent positions/cash, daily rollovers, corporate actions/splits, symbol delistings, market holidays, overnight/weekend gaps, and session renewal.
- [ ] Validate provider rate limits, timeouts, reconnect/backoff, stale feeds, delayed or missing quotes, clock drift, API contract changes, and provider outages without false trades.
- [ ] Validate durable logging and retention: bounded disk usage, backups, restore drills, log rotation, privacy of tokens, credential expiry and permission changes.
- [ ] Prove resource and operational stability: extended soak runs, memory/CPU/disk trend, sleep/resume and Windows updates, clean manual stop, dashboard health and Discord alert delivery failures.
- [ ] Define operator-visible NO-GO/DEGRADED/READY states and recovery playbooks, with explicit proof required to graduate from supervised to unattended PAPER.

## P2 - acceptance and launch retrospective
- [ ] Run staged duration acceptance (short supervised session, full session, multi-day, multi-week) before claiming months-ready. A months-long soak cannot be substituted by unit tests.
- [ ] Produce audited coverage matrix of all strategies, providers, markets, and risk controls against runtime behavior; avoid inferring coverage from demo fixtures.
- [ ] On actual launch acceptance, compile master-roadmap and Git-history retrospective with verified milestone timeline, evidence, test history, capabilities, limitations and screenshots. Generate shareable PDF for friends/family. No fabricated claims or premature ready announcement.

## Current proof / limitations
- Repo inspection: 2,763 tracked files; 2,398 Git log entries at audit time; not a count of completed features.
- ATLAS.bat and ATLAS-STOP.bat are present but invoke protected scripts that refuse native lifecycle actions.
- Opt-in unified stop bridge and SQLite stop receipt ledger exist; this does not prove shortcut enrollment or provider-backed PAPER operations.
- The latest focused stop suite reported 79 passed, 1 Windows symlink skip. That is component regression evidence, not end-to-end unattended acceptance.
- Genesis is separate and must remain untouched. VPS is not a dependency. Live trading is explicitly out of scope.

Launch decision rule: READY only after every P0 and P1 item has independently accepted evidence and staged P2 duration acceptance meets operator-defined criteria. Until then: NO-GO.
2026-11-07 follow-up: added read-only scripts/windows/atlas_paper_readiness_check.py for machine-readable desktop lifecycle blocker evidence. CLI exit 2 and NO_GO until independently accepted session and stop transport exist; it never grants startup even if guard is removed. 85 combined focused tests passed, 1 skipped. No operational startup.
2026-11-07 next milestone: added offline Atlas-Paper-Stop-Handoff.psm1 strict handoff shape and 13 PowerShell refusal assertions. Even a correctly shaped self-asserted handoff is rejected until independent session ownership authority exists. No desktop wiring, socket, stop dispatch or PAPER authorization was enabled.
2026-11-07 follow-up: offline in-process accepted PAPER handoff dispatcher now verifies exact session_id and verify_session() from supplied session object, refuses malformed requests and incomplete shutdown, and returns success only with FINISHED/FLATTENED/FLAT/VERIFIED_EXIT. Six fake-session assertions passed. This is NOT a desktop transport or independently authenticated owner session; remains NO-GO.
2026-11-07 follow-up: offline accepted PAPER Stop handoff now checks session identity before verification and again after dispatch, refusing owner changes; three new mutation/mode-spoof assertions passed. This does not establish independent authority or an operational desktop Stop transport.
2026-11-07: offline accepted-session Stop handoff now fails closed on dispatch exception without automatic retry and requires dictionary-shaped lane evidence for any success acknowledgment. Two new fake-session assertions. Still not connected to real desktop shortcuts or authenticated PAPER owner.
2026-11-07: Control Center module now exposes Invoke-AtlasPaperStopWithHandoff for in-process accepted owner sessions, using strict handoff validator. Three integration assertions and 82 Python focused tests passed, 1 skipped; existing 12 Control Center and 24 handoff assertions also passed. No desktop batch wiring or independently authenticated owner enrollment yet.
2026-11-07: opt-in accepted PAPER handoff is now wired into the existing Control Center GUI normal Stop, emergency Stop and FormClosing paths, with strict expected shutdown mode for each. Default remains no enrollment; legacy guarded desktop shortcuts unchanged. 85 focused Python tests passed, 1 skipped, plus PowerShell fake-session integration. This is GUI code-path wiring only, not authenticated runtime commissioning.
2026-11-07: closed GUI lifecycle loophole: the Close GUI - Keep Atlas Running action cannot bypass FormClosing verified flatten when an accepted PAPER session is enrolled; observation-only host can still close normally. 86 Python focused tests passed/1 skipped, PowerShell Control Center contracts green. No real desktop shortcut enrollment or live runtime startup.
2026-11-07: strengthened GUI FormClosing itself: enrolled PAPER session always requires verified shutdown even if KeepAtlasRunning flag was previously set by another code path; canceled close on failure. 87 Python focused tests passed/1 skipped; 15 Control Center PowerShell assertions green. This remains static wiring plus fake-session evidence, not live desktop launch.
2026-11-07: FormClosing explicitly clears KeepAtlasRunning before attempting any enrolled financial PAPER shutdown; failed stop continues to cancel GUI close. 88 focused Python passed, 1 skipped; 12 PowerShell lifecycle assertions passed. This is not authenticated runtime enrollment.
2026-11-07: UnifiedControlStopBridge now exposes read-only session_id derived strictly from installed runtime grant, not caller handoff. Invalid/missing grant session IDs fail handoff identity comparison. Existing authenticated local stop transport remains compatible; 80 focused Python tests passed, 1 skipped. This is a bridge prerequisite, not independently authenticated desktop session enrollment.
2026-11-07: added opt-in authenticated loopback POST /_atlas/control/stop-session requiring exact session_id + mode, same loopback origin/host/token, and runtime bridge identity check before dispatch. Disposable runtime fixture has no accepted session_id, so even valid token fails closed (409). Existing /stop remains backward compatible. 81 focused Python passed/1 skipped. No default route registration, no real accepted enrollment or shortcut wiring.
2026-11-07: opt-in require_session=True local control transport policy now disables legacy mode-only /_atlas/control/stop, preventing identity-check bypass in future session-bound installations. Existing callers retain backward-compatible default False; no default registration or production activation. 82 Python focused passed, 1 skipped.
