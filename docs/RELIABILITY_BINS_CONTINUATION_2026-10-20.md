# Visible probability reliability bins — October20,2026

Scoped offline synthetic acceptance. Production NO-GO. All21 canonical release decisions unchanged:5 scoped PASS,13 BLOCKED,3 NOT_TESTED. AFI-1–10 PENDING. Prior502-case checkpoint and8 intended hashes verified. Native autonomous Goal ACTIVE. No fresh runtime census.

## Integrated working functionality

Probability reliability is now visible in accountability HTML, the filtered local-file viewer and actual replay/frozen-holdout reports. Ten fixed bins use lower-inclusive/upper-exclusive boundaries, with probability1 included in the last bin. Each bin shows recorded count, distinct targets, mean probability, observed UP fraction and evidence status. Empty-bin means/fractions remain unavailable, never zero error. Cohorts show the actual probability denominator and weighted absolute bin gap, with separate resolved/pending, absent, unrecorded and no-probability counts where original rows are available.

The shared probability scoring helper is reused by the original score engine and new diagnostics without changing old metric values or serialized cohort formats. Reliability remains independent of unrelated price-error overflow. Original model, configuration, data/manifest/release and nominal-interval bindings stay separate. Duplicate forecast identities and equivalent UTC case aliases refuse. Malformed even-pending probability inputs refuse before later resolution could legitimize them.

Partial legacy inputs can show the explicitly recorded subset with its own denominator and PARTIAL_LEGACY_INPUTS label. Missing inputs are not inferred as zero. Distinct-target counts and OVERLAPPING_TARGET_EVIDENCE warnings apply per cohort and populated bin. Unique targets still do not establish statistical independence. Sparse bins, low weighted bin gaps and synthetic fixtures do not prove calibrated confidence, coverage, market skill or profitability. Authority flags remain false.

The viewer recomputes diagnostics from verified original filtered rows, uses textContent and clears stale results after failed input or empty selections. Six-significant-digit display does not alter original JSON precision. Replay/holdout HTML uses its freshly reconstructed score cohorts and exact forecast/outcome matches. All bins remain explicit. No new persisted report fields or historical evidence rewrites were needed. No browser storage/network, API route, runtime or execution controls introduced.

## Usable artifacts

logs/diagnostics/reliability-bins-20261020/viewer.html is the self-contained local viewer. Manually select sample-accountability.json in that directory for an actual immutable two-configuration synthetic probability report. sample-holdout.html is an actually published frozen-holdout report with reliability bins. sample-provenance.json records source and hashes. No native browser visual acceptance claimed; mounted DOM and parsed actual HTML acceptance are distinguished.

## Exact validation

Broader guarded native AFI suite519 passed,0 failed/skipped,46.56s. This run collected17 new cases;2 additional actual replay/holdout HTML table checks were then added. Final expanded focused suite19 passed,0 failed/skipped,1.30s. There are521 distinct AFI cases verified across these runs; do not misreport the broader run as521. Node viewer suite130 passed,0 failed/skipped/cancelled (8 added cases).

Tests cover probability0/1 and bin edges, weighted rather than unweighted denominator, empty bins, missing/partial inputs, repeated-target warnings, model/manifest/interval separation, duplicate and UTC-alias rejection, unrelated price-square overflow, backend/browser parity, immutable actual-report rendering, mounted actual probability bins/filter clearing and parsed replay/holdout HTML denominators. Existing frozen artifact, score, selection/protocol, interval, source and CLI regressions pass.

No test failures in this increment. Initial lint import organization and an imported-row shadowing in a newly added test were corrected narrowly; final targeted Ruff clean. Compilation, Node syntax and dependency consistency pass. No PowerShell source changed. Whole-repository lint remains a separate blocked gate; no waiver or broad cleanup. Final whitespace/guard checks recorded in closure.

## Next executable work

Implement an explicit bounded offline multi-market forecast batch workflow prioritizing U.S. equities, ETFs and crypto. Reuse existing reviewed datasets, per-asset calendars, fixed model/optional probability/interval publication, source bindings and comparison renderer. Preserve separate currency/price-error contexts and refuse ambiguous plans. Produce useful durable per-item artifacts and truthful partial-failure/no-false-success evidence; no provider discovery, scheduling, auto-trading, pooled price ranking or production integration. Continue other feasible seven-phase work afterward.

No Atlas/Docker/provider/Genesis operations, production/protected state/config/ACL/shortcut changes, real volumes/backups/restoration, PAPER/live/Discord activation or Git mutation. Independent datasets/rights, real calibration/skill, lifecycle/backup/restoration/Gaming/clean-machine, cash scope, lint and Discord/recovery gates remain blocked as documented.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

AFI-1 contracts; AFI-2 PIT datasets; AFI-3 baselines; AFI-4 walk-forward scoring; AFI-5 uncertainty/calibration; AFI-6 multi-market comparison; AFI-7 accountability; AFI-8 dashboard; AFI-9 scenarios through2050; AFI-10 independent acceptance: ALL PENDING. Preserve permanent Gaming objective, Atlas/Genesis separation and Prediction Market Intelligence V2 safeguards.
