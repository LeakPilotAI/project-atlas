# Base replay microseconds continuation — October20,2026

## Working correction

Base parseExport in frontend/offline/market-replay/view.cjs now checks exact microsecond timestamps rather than rounded milliseconds and2ms age slack. New internal microsecondTimestamp retains the existing ISO/date validation, adds fractional microseconds and refuses unsafe epoch/duration integers. Base replay event/receipt/asof order, exact derived age, minute duration/alignment and coverage windows use consistent microsecond units. Source schemas, raw return values and stored evidence are unchanged; no production page or authority path modified.

Seven original failures/10 passes preserved: future receipt1us within the same millisecond, forged age±1us, and unsafe epoch range could previously be accepted. Final24 new Node cases include valid sub-ms asof/receipts, unsafe duration, exact TTL and truthful stale states, plus forged fresh age1us beyond bar180s or quote30s. Other parser bodies were byte-preserved; only the base parser and shared helper insertion changed. Remaining quality/research parsers still using millisecond comparisons are not claimed repaired.

## Exact validation

605 expanded market/replay/research Python tests passed in39.74s (previous598 +7 new integration cases), zero failures/skips. These are NOT605 AFI tests; separate prior604 AFI acceptance preserved and not rerun. Actual Python normalizers → SQLite commit/reopen → in-process ASGI JSON → actual Node parser accept0/1/99/100/999/123456/999999us receipts/asof. Full offline Node suite386 passed (prior362 +24 new), zero failures/skips/cancellations. Focused18 and final24 Node cases passed in separate unique logs. Original failing log untouched.

Configured frontend ESLint passes for changed module/test; Node syntax, Python compilation and Git diff pass. Initial lint invocation used wrong repository-root cwd and reported missing config, not findings; noted in lint-invocation-note.txt. Correct frontend-config checks exited0 with no changes/waivers. Three inherited synchronous builder require-import findings remain unchanged. Existing diagnostic raw-log overwrite limitation remains disclosed in DUPLICATE_ACK_CONTINUATION and its provenance/reproduction; no additional logs overwritten.

## Safety/readiness

No provider/service/Atlas/Docker/Genesis, real data store/volume, protected configuration/state/ACL/shortcut, backup/restore, trading/PAPER/Discord activation or Git operation. Guarded synthetic fixtures and in-process ASGI only; no fresh runtime census. Full Atlas startup/live collection remain NO-GO pending provider-specific permissions/entitlements/session/history/storage/display rights, wire timing/delay/adjustments, budget acceptance and approved fixed observation-only admission/lifecycle. Offline viewer and three-session equity/ETF data paths are tested; real feed or native visual/runtime acceptance is not inferred.

All21 decisions/startup lock unchanged, production NO-GO; full seven-phase strategy and AFI1–10 PENDING retained. Gaming objective, normal PAPER cadence requirements, Atlas/Genesis isolation, E136 consent/recovery and Prediction Market Intelligence V2 safeguards unchanged. Synthetic tests establish no market skill/calibration/profitability or provider rights.

## Exact continuation

Latest pins/result under logs/diagnostics/replay-microseconds-20261020; verify before editing. Approved updater verifies backup, exact read-back and historical bytes outside managed section. Existing full Goal preserved; no duplicate/reset/completion/blocked claim. Previous explicit usageLimited observation is historical; current native continuation remains authorized. No external unattended mechanism.

Next selected offline task: quote-quality temporal consistency. parseQuoteQuality currently still uses timestamp() millisecond values and2ms tolerances for event_age_seconds/receipt_delay_seconds; receipt_time>asof can be missed within1ms. Reproduce deterministically from quote-quality.json, then reuse the already-tested microsecond helper for exact bounded order/age/delay comparisons, without changing schema/export bytes or claiming source authentication. Include actual Python quote_quality→API→browser microsecond integration, unavailable/pending/delayed/stale states and TTL boundary tests. Do not change other parser bodies without their own tests. Continue broader offline roadmap functionality after this; no services/provider/Git/protected-state operations, no production gate changes. All evidence paths must be fresh/exclusive.
