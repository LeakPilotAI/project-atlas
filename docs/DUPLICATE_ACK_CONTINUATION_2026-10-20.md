# Duplicate acknowledgement continuation — October20,2026

## Implemented working correction

ReplayStore._insert (called _ingest in earlier planning notes) now validates a semantically matching retained record with the same _decode contract used by readers before returning duplicate0. Dict equality alone admitted bool/int/float aliases, collapsed duplicate JSON keys and invalid receipt evidence. Eleven new tests: original9 failures/2 passes reproduced; all11 corrected cases pass. Malformed duplicates refuse without changing retained bytes; an earlier new row in the same transaction rolls back. Well-formed duplicates remain0 and retain their first receipt. Legacy conflicting representations preserve their existing conflict refusal.

## Expanded compatibility acceptance

Broadened to all rg-discovered market_replay/ReplayStore consumers plus offline equity/research contracts, under a fresh guarded backend snapshot. Fixture state resides inside its dedicated synthetic sandbox; production data/.env/external connection guard remains unchanged. This includes actual extracted market cases, archive/vintage/as-of/read-view/quality/export and mocked yfinance wire paths; no real provider request.

First expanded run:572 passed/3 failed. Two immutable browser export fixtures changed because the earlier OHLC correction converted already-numeric integers into floats. Corrected normalization now preserves existing numeric int/float representation while coercing accepted strings; six new type-preservation cases added. The third issue was chronology-refusal wording changed by early retained validation; original chronology message restored, without weakening refusal. Original fixture bytes were not edited. Final expanded run:581 passed in42.90s, zero failures/skips. Targeted Ruff, compilation and Git diff pass. Prior604 AFI/362 JavaScript and64 CLI/package acceptance preserved; unaffected full suites not repeated.

Diagnostic limitation: the first expanded raw failure log was inadvertently overwritten by the rerun driver. It is not claimed preserved byte-for-byte. Terminal outputs (chunks5527e1/877e74), pre-correction source snapshots and a new isolated pre-correction reproduction preserve the finding. That separately copied source run reproduces exactly the three failing test names in precompatibility-reproduction.txt (3 failed as expected for old source, not current-code failures). failure-log-provenance.json records the distinction. The local diagnostic runner now requires explicit new log/temp names and exclusive log creation. Original duplicate9-failure log remains intact. No published fixture, canonical evidence or production data was overwritten.

## Safety and readiness

All21 decisions and production startup lock remain unchanged; production NO-GO. Seven-phase strategy, AFI1–10 PENDING, permanent Gaming objective, Atlas/Genesis separation, E136 consent/recovery and Prediction Market Intelligence V2 safeguards preserved. No service/Atlas/Docker/Genesis/provider/Discord operation, trading/PAPER activation, protected configuration/state/ACL/shortcut/volume, backup/restore or Git staging/commit/push/reset/cleanup. No fresh runtime census.

Offline viewer/CLI and equity/ETF bar/quote paths remain tested across premarket, regular, after-hours, DST and early close. Full Atlas startup/live collection still requires provider-specific rights/entitlements/session/history/storage/display scope, exact wire timing/delay/adjustment semantics, bounded budgets and approved fixed-release observation-only admission/lifecycle acceptance. Do not infer subscription or key presence. Shortest safe path remains one documented provider scope then authorized observation-only runtime verification, not bypassing locks.

## Exact continuation at context boundary

Latest result/pins under logs/diagnostics/duplicate-ack-20261020; compare before editing. Existing Goal preserved; no duplicate/status reset, completion or blocking claim. Last earlier explicit Goal observation was usageLimited; automatic continuation now follows the persistent objective. Roadmap backup/read-back/outside-checkpoint bytes verified with approved updater; all21 decisions unchanged.

Next selected offline task: typed refusal for malformed retained duplicate JSON. _insert still parses prior JSON and assumes a mapping before its schema validator, so valid-hash array/null/truncated JSON may raise AttributeError/JSONDecodeError instead of ResearchInputRefused. Reproduce with temporary bar/quote rows, preserve exception causes and transaction rollback, minimally reject non-mapping/malformed retained values before semantic comparison, retain existing integrity/conflict/identity messages. Keep read/write refusal consistency and immutable evidence, then move to other feasible offline roadmap functionality. No broad storage rewrite, providers, services or production integration. Use exclusive fresh evidence paths; never overwrite earlier failure logs.
