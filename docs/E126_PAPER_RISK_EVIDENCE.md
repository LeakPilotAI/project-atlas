# E126 — PAPER risk boundaries and incomplete accounting evidence

Status: **E126 GREEN — source and isolated validation.** Runtime activation is unverified and separate.

## Scope and continuity

Branch: `chatgpt/atlas-rebuild-v1`. Initial HEAD: `06e640cba186c94163731ab4a0b3a89c51e08c98` (E125). The tracked tree was clean. Existing untracked artifacts were preserved. The latest user-delegated E126 instructions authorize source implementation, isolated tests, documentation, roadmap synchronization, commits, and push; they prohibit runtime restart and production evidence mutation.

Observation started 2026-10-14T04:59:19.391491Z (2026-10-13 23:59:19.391491 CDT, UTC−05:00). The previous E125 PID 35616 was absent. The documented Atlas health endpoint `http://127.0.0.1:8000/health` was unavailable, including an unrestricted read-only retry. This is not evidence of an E126 regression: no E126 source was activated, no server was launched, and no service was stopped or restarted. Current runtime health and activation cannot be certified.

## Verified policy — ten audit answers

1. **Loss stop:** `paper_risk.py` explicitly describes auto-mirrored Perp setups. `perp_setup_paper_mirror.py` and `/api/perps/paper-risk` are the production consumers. The −3R UTC-day measurement aggregates eligible PAPER closes across strategies, but its admission enforcement applies to the Perp resting-limit mirror. A portfolio-wide enforcement contract is not established.
2. **Concurrency:** the mirror guard counts all current PAPER positions, including other strategies and recovered opens, when deciding whether the mirror may add exposure. Its three-position cap is not imposed on RSI or equity entries by E126. The $25 risk ceiling and $1 mirror request remain unchanged.
3. **Kill switch:** current enforcement is mirror-specific. Historical roadmap language (“blocks new PAPER risk immediately”) is broader than the implemented wiring. Whether the operator intends every automatic strategy to stop remains an unresolved policy decision. E126 does not silently broaden it.
4. **Try-symbol:** `paper_try_symbol.instrumented_try_symbol` is installed as `PerpMicroCoach._try_symbol` by `paper_pipeline_hooks.py`. It is an automated implementation hook, not a separately exposed manual admission API in the inspected source. Its scheduler retains upstream controls. Direct internal invocation is not granted new authority.
5. **RSI controls:** `_cycle` checks PAPER enabled, liquid universe, `effective_max_open`, daily triggers and cooldown. `perp_micro_max_open=0` means up to the existing safety ceiling of 80; positive limits are capped at 80. Daily trigger default is 999. None changed. Equity mirror remains a separate simulation path with journal collision protection; no shared mirror risk call existed there.
6. **Recovery:** `PaperJournal._load_open_from_disk` reconstructs opens by trade ID, folds mark/adaptive fields, excludes TEST records, and removes IDs with closes. The guard uses the resulting `list_open()` without changing recovery or forcing any exits. Regression tests preserve those rows and bytes.
7. **Incomplete evidence:** the previous tolerant iterator exposes malformed sentinels, but the old risk window ignored them and treated missing files as zero. E126 explicitly distinguishes reliable evidence from unreadable, missing, malformed, unterminated, unknown-event/type, ambiguous duplicate, conflicting duplicate, or otherwise incomplete evidence. No ledger repair occurs.
8. **Legacy closes:** absent trade type defaults to PAPER; naive timestamps mean UTC; `timestamp` may substitute for absent `exit_timestamp`; missing/null `net_pnl_r` may use finite `R_multiple`; explicit zero remains authoritative. Valid id-less closes remain accepted. Identical id-less duplicates cannot establish distinct fills and block reliability. Same-ID equivalent closes count once; conflicting closes fail closed. TEST and administrative closes are excluded before checking their accounting fields. Known prior-day closes with invalid R do not contaminate today's total; unknown close dates cannot be safely assigned to another day and block.
9. **Stale controls:** stored session P&L can no longer substitute for a failed journal snapshot. The API and mirror use the same reliability checks. Unreadable/corrupt existing operator-control files are marked unreliable; the established absent-control-file startup default remains available. An explicit successful operator save can restore a valid control record. This does not initialize a missing journal.
10. **Race:** earlier code captured opens and kill state before yielding to the journal worker. E126 serializes mirror fills, checks pending identity/freshness again, then reads current opens and controls. Journal size/identity/mtime and UTC date are checked after the worker and before admission. The real `PaperJournal.open_trade` and installed V4 observer perform persistence before any suspension. This addresses the single-runtime event-loop race; it is not a distributed transaction or support for multiple independent journal writers.

## Changes

- `backend/app/services/paper_risk.py`: reject invalid, boolean, NaN/infinite session R and requested risk; explicit accounting/control reliability blockers. Invalid session R is null, never invented zero.
- `backend/app/services/paper_risk_window.py`: reusable read-only evidence contract (`reliable`, `issues`, `net_r`, UTC date, journal version); deterministic boundaries, legacy formats, exclusions, duplicate handling, finite sum, and freshness validation. Reliable empty existing journals produce zero; missing journals block.
- `backend/app/services/paper_risk_controls.py`: expose loaded-control reliability without changing risk parameters or writing during reads.
- `backend/app/services/perp_setup_paper_mirror.py`: serialized admission, post-read state checks, no stale P&L fallback, existing `PAPER_RISK_BLOCK` cancellation/audit path retained. Rejected attempts create no journal opens.
- `backend/app/api/perp_manual.py`: expose unavailable accounting as null with reliability metadata; blocked standard mirror probe on missing/stale evidence or corrupt controls.
- `backend/app/static/command_center_risk.html` and `dashboard_shell.html`: preserve unknown R instead of coercing null to zero; no fabricated loss headroom. No visual rebuild, polling redesign, or strategy UI changes.
- `tests/test_e126_paper_risk_evidence.py`: new accounting, numeric, recovery, race, API and executed Node rendering regressions.
- Existing mirror test fixtures explicitly supply trusted isolated evidence. E125's risk-window test now observes a close after its timestamp instead of an hour before it: `test_paper_risk_session_derivation.py`, `test_perp_setup_paper_mirror_v4.py`, `test_e125_paper_accounting.py`.

## Validation

Final focused: **131 passed, zero failed/skipped**, 4.84 seconds. Final full suite: **1754 passed, zero failed/skipped**, 39.34 seconds, two dependency warnings. Full Ruff passed for the rewritten risk-window module and new regression tests; critical E9/F63/F7/F82 checks passed for all modified Python; `git diff --check` passed. Canonical command: Python pytest `-q tests backend/tests`, with a unique temporary directory and cache disabled. Focused selection includes E126, existing risk/window/control/API/mirror/E125 tests and dashboard contracts.

Tests run in `.e126-sandbox`, a tracked-source copy excluding real `.env` and production data. A Python audit hook blocks production evidence/credential access and live service connections, allowing only Python's internal Windows socketpair. No duplicate API server was started. Test-created records are isolated fixtures, never performance evidence. Existing Node checks cover static script compilation; added Node tests execute unknown/zero accounting rendering. No Next.js source or dependencies changed, so a separate Next.js build/typecheck is not applicable.

Intermediate validation: 114 focused / 1744 full, then 122 focused / 1752 full; added UI checks passed 130 focused / 1753 full. Final validation includes a further Perp null formatter test. Two existing dependency deprecation warnings concern `audioop` and Starlette/httpx. Initial new-file lint findings were corrected; no test failures were waived.

## Historical integrity and E29 evidence

Journal baseline and final check at 2026-10-14T05:11:02.695791Z (00:11:02.695791 CDT): **6,734,055 bytes**, entire file unchanged, SHA256 `55985866cb1c69e5e19a378fb40e44c5fd97636bff9f3109024bc5333f09a3bf`. All 1286 open records and 1286 close records remain intact; this count includes administrative events and is not a performance cohort. Latest recorded close: 2026-10-13T12:20:31.522780Z (07:20:31.522780 CDT). No claim of continuous collection after that timestamp.

E29 was recomputed read-only at 2026-10-14T05:10:09.122750Z (00:10:09.122750 CDT), using only `build_scorecard(rows, existing_memberships)` in the isolated source copy. Neither the synchronizing service nor its API was called. 52 frozen membership records; membership SHA256 `330a3a947df79f91b2295cd04771969e7b60c9f990f026dcd67e3d4aec723165`.

| Recorded E29 cohort | Closed | Recorded net R | Symbols | Forward days |
|---|---:|---:|---:|---:|
| Baseline | 51 | -2.9476 | 7 | 6 |
| Challenger | 10 | +2.3160 | 4 | 5 |

E29 remains **NOT_READY**, promotion false; all minimum evidence gates are false. These are recorded historical results, not retrospectively repaired cost results or profitability certification. Evidence accumulation and alpha/cadence/corroboration research remain active goals, but current runtime collection is unverified.

## Limits and next execution

- Source hardening can be GREEN while runtime availability is unresolved. Activate only through a separately authorized Atlas-only recovery/start or restart; then verify health, risk endpoint, real accounting reliability and continued evidence collection. E125 also still needs verified activation.
- Agree an explicit portfolio-wide kill-switch/loss-stop policy before changing RSI/equity behavior. Keep mirror concurrency and micro frequency distinct.
- An ambiguous historical record may conservatively block the mirror across days. Do not rewrite evidence to unblock it; investigate provenance and establish a separately reviewed migration/override contract if needed.
- Any concurrent journal append, including a mark, can invalidate an in-flight snapshot. This intentionally favors safety and may cancel a fill opportunity through the existing terminal risk-block path. Observe frequency after authorized activation before relaxing or adding retries.
- File metadata freshness is designed for one trusted local writer/event loop, not adversarial file replacement, distributed locking, or multi-process admission. Full journal parsing is O(file size), currently about 6.7 MB.
- New missing-journal startup blocks mirror admission until valid evidence exists; an explicitly existing empty journal is accepted. E126 does not create or truncate an empty ledger.
- Genesis, Docker Desktop, containers, Postgres/Redis, trading thresholds, live-money authority, and gated Discord producers were not modified. VPS/hosted deployment is out of scope. Windows-local release readiness remains active.
