# Source-bound chart price-basis diagnostic — October 20, 2026

Third automatically selected offline increment; full Goal remains active/incomplete. Production NO-GO.

## Usable functionality

New scripts/observation_runtime/chart_provenance.py accepts bounded explicit synthetic chart bytes, an exact caller SHA-256, observation clock and equity/ETF class. It reuses strict duplicate/nonfinite JSON parsing and existing chart/session normalization. It reports chart closes separately from optional provider-shaped adjusted closes, binds to exact bytes (including whitespace), and preserves an unknown adjustment basis and unknown delay units. Fresh timestamps or zero reported delay never become a live-data claim. The chart quote close is explicitly NOT_VERIFIED_UNADJUSTED. Provider fields are not treated as authenticated facts or licensing.

Optional adjusted-close arrays must be a single aligned series with valid positive finite prices; malformed, missing/null/nonfinite/negative/boolean values refuse. A source timestamp map preserves adjusted-value identity when normalizer sorts out-of-order bars. Optional delay values must be bounded integers; absence stays null, never zero. No original source or normalized legacy representation changes.

export_chart_provenance reuses the existing immutable publisher for JSON, scriptless readable HTML table and provenance sidecar containing report/HTML hashes, followed by readback. Exact retries preserve existing bytes. It has no network/default path/startup hooks. This is a callable offline exporter, not a new API route, fetch client or production dashboard. Multi-file publication is not a transaction: partial failure evidence is preserved by the existing publisher and cannot be claimed as completed export. No privileged filesystem/rollback or hardware-loss guarantee.

## Exact acceptance

32 new chart diagnostic cases are included in the final broader isolated run:468 passed, zero failures/skips,18.23 seconds. Includes40 new request-tier/deadline and20 metadata-consistency cases from earlier increments, plus prior market/storage/provider/shutdown/PAPER tests. Counts are successive selections, not additive.271 unchanged Node dashboard tests pass from the retained current-directory run; no frontend source changed. Targeted Ruff and compilation pass. Updater PowerShell parsing and Git whitespace checks verified; no global Ruff baseline waiver/full canonical suite claim.

The first20 focused cases passed, then7 malformed/sorting cases and5 session/calendar cases were added. Narrow test import formatting and dict-construction Ruff findings corrected; earlier outputs retained. Original metadata10-failure reproducer remains evidence, not an unresolved failure. Five calendar fixtures cover premarket, regular, after-hours, early close and DST. Existing market pipeline tests preserve real in-process ASGI -> Node consumer behavior.

Readable artifact comes from logs/diagnostics/wire-budget-20261020/provenance-broad-temp/test_export_is_immutable_idemp0; its content-addressed .html is a synthetic diagnostic, not live quotes. Exact result/manifest and checkpoint evidence are retained in the diagnostic root.

## Readiness

Local inert ASGI factory/offline dashboard and new diagnostic exporter are technically testable. The complete Atlas application is NOT cleared to start under existing controls. Startup denial is preserved; no fresh runtime/Docker census, real server/browser readiness or lifecycle acceptance occurred. Premarket/regular/after-hours fixture paths are implemented and tested, not live exchange-session acceptance.

Shortest safe live session path remains: establish provider-specific U.S. equity/ETF automated-use/session, delay, historical/storage/display rights and entitlements; safely validate required credentials without output; accept actual transport budgets/deadlines, timestamp/adjustment/provider semantics; explicitly approve and integrate fixed observation-only runtime paths and admission; then bounded read-only startup/data/shutdown acceptance with all PAPER/prediction/live/Discord actions denied. Do not run the repaired launcher as if it already enforces this profile. No subscription/API key is presumed present or absent. Full production release remains NO-GO and all21 gate decisions untouched.

## Exact next automatic execution

Inspect existing source-bound dataset/receipt bridges before adding anything. Highest-value next offline task: a bounded source-archive receipt/export companion for this chart diagnostic that commits original bytes and observation clock, verifies complete re-read/reproduction, and refuses unreviewed source/path or changed payload rather than treating a diagnostic hash alone as a retained archive. Reuse BundleReader and existing immutable publisher; do not duplicate forecast storage or claim independent custody, licensed datasets, live timestamps or rollback resistance. Keep original payload immutable; metadata-only diagnostic must not expose unrequested fields. Test partial publication failure, exact retries, changed source and exported-bundle replay. Then continue AFI/evidence accountability and remaining seven-phase independent work. Never activate providers/startup to resolve a fixture gap.

All seven phases and21 decisions preserved in the master: core ops/provider/cash/lint/package/backup/restoration/Gaming; Evidence Engine; bounded crypto PAPER; cross-market intelligence; SaaS; institutional governance/security; commercial validation. AFI-1–10 PENDING, E136 consent/no-backfill/recovery, prediction exactly-once/predeadline/autoflat and Prediction Market Intelligence V2 safeguards retained. PAPER_ONLY/MANUAL_ONLY. No services/Docker/Genesis, volumes/backups/restores, protected state/config/ACL/shortcuts, trading/Discord, Git staging/commit/push/reset/cleanup or external scheduler.
