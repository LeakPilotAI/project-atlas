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
