# Retained schema continuation — October20,2026

## New working functionality

ReplayStore read paths now distinguish byte-integrity from valid normalized observations. _decode checks exact bar/quote source schemas, synthetic provenance and non-executable price-kind labels, equity/ETF/USD identity, canonical UTC timestamps, event/receipt order and session classification, finite numeric prices, bar OHLC consistency, minute duration, exact safe-integer shares, and bounded explicitly unverified quote-delay metadata. Duplicate JSON fields refuse. Snapshot/history/coverage and quote reads share these checks. Quote selection supplies its explicit table; historical callers retain the default bar contract.

Malformed retained data is never normalized, rewritten or deleted. Valid-hash legacy string OHLC/unsafe shares cannot become FRESH HTTP200; existing sanitized API/HTML503 DATA_UNAVAILABLE behavior receives typed refusals, with original exception causes retained internally and no raw values exposed. Well-formed historical integer OHLC remains readable and unchanged. Query-key substitution preserves the original identity-refusal message. Matching hashes do not establish source authenticity or a license.

## Exact validation

34 new retained-record cases; original non-API red run28 failures/2 passes/2 deselected preserved. New checks initially introduced one identity-message compatibility failure (295 passed/1 failed); corrected without weakening refusal and preserved in regression-tests.txt. Final guarded suite296 passed in7.57s, zero failures/skips. Separately10 actual extracted equity/ETF three-session/DST/early-close bar+quote cases passed in16.84s. Focused initial30 passed/2 deselected before adding duplicate-key tests. Targeted Ruff, Python compilation and Git diff pass.

Prior corrected volume suite248 and OHLC suite262 are superseded by the expanded296 affected-research suite, not added together. Prior604 AFI/362 JavaScript and64 native CLI/archive acceptance logs/hashes remain preserved; unaffected full suites not repeated. Existing3 frontend builder lint findings unchanged, no policy waiver. All original sandbox failures, metadata compatibility failures and exact synthetic-test cancellation proof remain in prior directories.

No Atlas/backend server, Docker, provider, Discord or Genesis lifecycle/connection was performed. In-process ASGI objects and temporary fixtures only. No production records/configuration/ACL/shortcut/volumes, backups/restoration, trading/PAPER authority, recovery fence or registry changed. No Git staging/commit/push/reset/cleanup. No fresh runtime census.

## Readiness

Standalone offline viewer/build, explicit read-only candidate-verification CLI, and normalized/persisted/API/browser market fixture paths work. Premarket, regular, after-hours, DST and early-close paths are fixture-tested within existing bounded2026–2028 calendar. Full Atlas startup and actual live collection remain NO-GO: selected provider rights/entitlements/session coverage/history/storage/display permissions, authenticated wire timestamp/delay/adjustment semantics, request budgets and operator-approved fixed-release observation-only admission/lifecycle acceptance remain mandatory. No API key or subscription is assumed. Shortest path remains provider-specific authorization → bounded observation-only runtime acceptance → real freshness/budget verification → read-only dashboard. PAPER/live/Discord remain denied.

All21 release decisions/startup lock unchanged; production NO-GO. Seven original phases, permanent Gaming objective, Genesis isolation, E136 consent/recovery and Prediction Market Intelligence V2 safeguards preserved. AFI1–10 PENDING; synthetic tests establish no profitability/calibration/market skill.

## Exact continuation at forced context boundary

Latest pins/result: logs/diagnostics/retained-schema-20261020/intended-file-hashes.json and result.json. Approved roadmap updater verifies exact backup, managed read-back and historical bytes outside checkpoint. Existing native Goal preserved; no duplicate/reset/status update or unattended mechanism. Last explicitly observed Goal status was usageLimited before this automatic continuation; do not infer completion or blocking from that historical observation.

Next selected task: duplicate-ingestion acknowledgement consistency. ReplayStore._ingest presently checks hash then json.loads equality for an existing record, potentially returning duplicate0 for a valid-hash duplicate-key body or boolean/numeric alias rejected by _decode. Reproduce using synthetic bar/quote fixtures and exact before/after body/digest checks. Reuse the existing _decode validation after semantic-conflict checks so legacy string-price conflicts keep their existing refusal; no new framework, migration or evidence rewrite. Test duplicate success only for well-formed retained records, refused malformed duplicates, transaction batch rollback and API read compatibility. Then continue other feasible authorized offline roadmap work. No live services/provider requests or production integration.
