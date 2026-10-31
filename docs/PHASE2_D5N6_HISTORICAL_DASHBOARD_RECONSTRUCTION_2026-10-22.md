# Phase 2D.5N.6 — retained dashboard reconstruction

Status: scoped offline GREEN; Phase 2 acceptance HOLD; production NO-GO.

The retained 2026-10-21 stock/ETF batch dashboard remained hash-valid but no longer matched the current renderer. The renderer had subsequently added absolute-error columns and changed its price and percentage display from two decimals to full precision. Neither the retained source artifacts nor their identities changed. The isolated original test reproduced `ForecastEvidenceRefused: Batch dashboard differs from reconstructed forecast evidence` before repair.

`forecast_dashboard.render_dashboard` now has an explicit historical-layout mode that recreates the earlier columns, caption and numeric formatting. Normal new publications retain the current full-precision layout. Batch verification first checks the caller-pinned index and dashboard hashes and the exact forecast artifacts, then accepts only byte-exact reconstruction by the current or historical renderer. It still refuses arbitrary or edited dashboard bytes. No evidence, retained export, trading permission or production state was changed.

Validation: original failure now passes. The combined daily batch, AFI batch, legacy export and display-precision regression selection passed **40/40**, no failures or skips, in 9.10 seconds. Targeted Ruff passed; `git diff --check` passed with inherited line-ending warnings. The separate synthetic PAPER mirror suite was interrupted after one result because it stalled in the current sandbox; its result is not counted as acceptance. Phase 2D.5N.7 remains pending. The earlier N.5 neighboring result is preserved as 56/56 passed in `ATLAS-PHASE-2D5N5-NEIGHBOR-VALIDATION.txt`; a dedicated N.5 managed checkpoint remains unverified.

The retained byte test alone does not authenticate external historical publication or prove market skill. Phase 2 final acceptance and Phase 3 entry remain blocked. All 21 release decisions, the startup lock, AFI PENDING states and production NO-GO remain unchanged.
