# Chart delay refusal and diagnostic retention — October 20, 2026

Second automatically selected scoped increment this turn. Production NO-GO; full existing Goal active/incomplete.

## Measured defect and correction

Original21-case reproduction failed: explicit nonzero and malformed exchangeDataDelayedBy chart metadata was ignored by normalizer, ReplayStore and BarVintageStore. A recent synthetic event could therefore enter current-price/research storage while contradicting its reported delay metadata. This was fixture evidence, not an observed live provider incident.

normalize_chart now rejects malformed delay metadata and nonzero unknown-unit delay by default. Missing/zero metadata preserves the original normalized bytes; it is still not proof of real-time data, rights or actual provider freshness. Exact boolean diagnostic_only=True is a separate deliberate read-only normalization path used by chart_provenance. Diagnostic retention still validates metadata and shows nonzero delay with UNVERIFIED units and NOT_ESTABLISHED live status; it grants no ingestion permission or authority. Both public stores and source-backed replay use ordinary default ingestion and cannot receive that override through their public methods.

No change to quote delay policy, scanner behavior, production adapters, schema, risk settings or startup. No migration or deletion. Old normalized records that discarded original metadata cannot be retroactively certified by this fix; replay/source licensing and actual vendor semantics remain mandatory external gates. The diagnostic parameter is a cooperative application contract, not exclusion of arbitrary direct database writers or privileged code.

## Exact acceptance

21 original failing cases retained. Final focused selection87 passed (27 new delay cases plus32 diagnostic and28 archive cases); final broader isolated559 Python passed,0 failed/skipped,35.08s.304 Node passed,0 failed/skipped/cancelled,449ms; actual checked-in delayed diagnostic archive and Python-to-frontend fixtures remain accepted. Targeted Ruff/compile, updater PowerShell parser and Git diff checks recorded. A narrow new test import-ordering finding corrected, no waiver or full canonical suite claim.

Seven delay values were checked across direct normalization/current store/vintage store:1,15,boolean,missing-value/null,string,negative,out-of-range. Every failure precedes retained-row insertion. Missing/zero values preserve the original101 fixture value and representation. Explicit delayed source still archives and renders as unknown-unit diagnostics, but cannot bypass source-backed replay preflight or publish outputs. Invalid diagnostic mode values refuse. All17 previous descriptive/vintage export artifacts independently compare byte-identical after repair. Original rounding/reference-lifetime failures from preceding source-replay increment remain preserved and resolved.

## Actual readiness

Usable offline components now cover explicit source archival, reference correction preservation, source-backed receipt/replay, scriptless reports and local-file cryptographic viewer. Full Atlas/dashboard startup remains locked and NOT authorized; no fresh process/Docker/server health census or runtime browser acceptance. Premarket/regular/after-hours, early-close and DST fixture paths pass; actual provider/session coverage remains unverified.

Live prerequisites remain provider/exchange automated-use/session/history/storage/display rights, credential/entitlement checks without exposure, actual transport budgets/deadlines and timestamp/delay/adjustment semantics, then explicit observation-only fixed runtime/admission integration and bounded lifecycle/data acceptance. No subscription/key is presumed present or absent. The normal launcher is not already an accepted observation-only profile.

All21 canonical decisions and startup lock unchanged; production NO-GO. No services/provider/Atlas/Docker/Genesis activation, production integration or state/config/ACL/shortcut changes, real volumes/backups/restores, PAPER/live/Discord or Git staging/commit/push/reset/cleanup. All seven phases remain verbatim in master; AFI-1–10 PENDING, E136 consent/recovery/no-backfill, prediction exactly-once/predeadline/autoflat, PM-V2 safeguards and permanent Gaming objective/normal PAPER cadence retained.

## Exact next automatic execution

Advance forecasting accountability across the broader roadmap. Current forecast/reliability modules and offline viewer contain no log-loss/logarithmic-loss/cross-entropy implementation in the inspected source. Add an opt-in diagnostic companion for recorded probability forecasts: stable binary logarithmic loss and a fixed0.5 baseline, explicit impossible-event/infinite-loss counts (never silent epsilon clipping), proper flat-is-not-up semantics, resolved/pending/no-probability denominators and existing exact asset/model/horizon/dataset/code/interval cohort boundaries. Do not alter legacy forecast/outcome formats or frozen browser fixture bytes. Bind metrics to original recorded probabilities and exact outcomes, preserve small/overlapping-target refusal and no-calibration/no-skill authority. Reuse existing accountability validators and expose useful immutable JSON/HTML/frontend evidence with deterministic boundary/correction cases. First confirm no existing equivalent beyond the inspected modules; no provider or trading activation. Continue full authorized seven-phase work afterward.
