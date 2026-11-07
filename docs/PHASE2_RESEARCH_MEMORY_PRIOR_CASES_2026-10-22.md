# Phase 2 Research Memory — earlier-case context

Status: scoped offline implementation verified; Phase 2 acceptance HOLD; production NO-GO.

The existing Forecast Accountability Viewer now offers a query forecast and earlier cases from the exact asset, horizon, model, dataset/version and source-provenance cohort. UTC issue time is the cutoff. A resolved outcome is visible only when its target, publication and last reconciliation precede that cutoff. Later corrections mask the current value rather than fabricating a prior vintage. Missing, pending and unavailable outcomes remain separate. Failed/replaced imports clear the query and table. The original report evidence and forecast histories remain unchanged.

The implementation is in `frontend/offline/forecast-accountability/view.cjs` and `build.cjs`; contract tests are in `prior-cases.test.mjs` and `tests/test_afi_prior_case_workspace.py`. The README records the operator-facing meaning. The Python integration case produced actual synthetic forecast/outcome artifacts and verified original source bytes remained immutable.

Latest independent validation evidence: complete offline JavaScript discovery **747 passed, 0 failed, 0 skipped** (`logs/diagnostics/workspace-market-20261022/memory-all-js.txt`); combined market-pipeline, packaging and prior-case Python selection **5 passed, 0 failed** in 2.93 seconds. Targeted Python Ruff, JavaScript syntax and ESLint checks passed. A first ESLint invocation from the repository root failed to find the frontend config; rerunning from `frontend` succeeded. This is synthetic/static acceptance, not native browser acceptance.

The table is chronological context, not historical-similarity ranking or independently authenticated point-in-time publication. It establishes no calibrated forecast skill, live feed readiness, PAPER outcome, profitability or trading authority. AFI-1 through AFI-10 remain officially PENDING, and all 21 release gates remain unchanged. Independent historical availability and out-of-sample acceptance are still required before Phase 2 GREEN.
