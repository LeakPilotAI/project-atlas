# Atlas offline forecast accountability viewer

This is an isolated local-file viewer. It starts no server and has no production route, provider connection, storage, trading action or recovery authority. Only explicitly synthetic reports are accepted. Production remains NO-GO.

## Research Memory prior-case context

The existing viewer can select one forecast as a query and display earlier cases from its exact asset, horizon, model configuration, dataset/version and source-provenance cohort. The query's UTC issue time is the cutoff. A prior outcome is shown only when its target, recorded publication time and last reconciliation time are all no later than that cutoff. A later correction masks the current value rather than inventing an earlier historical value. Missing and pending outcomes remain distinct, and replacement or rejected imports clear the prior context.

This is chronological context, not a similarity ranking, verified historical availability, calibrated forecasting skill or a trading signal. The supplied report can be internally consistent without independent publication authentication. Native browser acceptance remains separate from the mounted offline tests.

## Build and use

1. Run `node frontend/offline/forecast-accountability/build.cjs <existing-directory>/viewer.html` with an explicit new output file. The builder refuses a different existing file. Exact retries retain bytes.
2. Open the resulting HTML locally in a browser, then select the `browser_export` JSON returned by the offline `app.backtest.forecast_report` bundle command. No upload occurs.
3. Filter by asset and outcome state or change sorting. Clear removes the in-memory report. No local storage is used.

The browser must support BigInt, TextEncoder and WebCrypto for local files. Missing cryptographic support refuses rather than bypassing verification. Opening/rendering in a real browser remains an independent acceptance task; Node acceptance does not establish native visual behavior.

## Produce inputs without a service

Use the existing Python environment with `backend` on the module path. Neither command starts Atlas:

```
python -m app.backtest.forecast_source --source-root <explicit-backend-source-root> --output-root <existing-output-root> --release-id <offline-identity> --include app/backtest/forecast_outcomes.py --include app/backtest/forecast_report.py
python -m app.backtest.forecast_report --bundle-root <existing-synthetic-bundle-root> --bundle bundle.json --output-root <existing-output-root>
```

Add `--evidence-states` to the bundle command for an opt-in V2 observation-state companion JSON and scriptless HTML. The command still publishes the original V1 report, dashboard and browser export with unchanged bytes; the returned `evidence_states` field names the separate companion files. The companion distinguishes 1D/5D source-window `COMPLETE`, `IMMATURE`, `PARTIAL`, `MISSING`, `CONTRADICTORY` and `UNVERIFIED` states from the recorded outcome state. A structurally complete synthetic price window may still have no recorded outcome and never establishes authoritative performance. The existing browser viewer continues to import only the V1 browser export; V2 HTML is a separate offline view. Native browser acceptance remains unverified.

All input paths in a bundle are portable relative paths under its root. Absolute, escaping and linked paths refuse. V1 binds source using `source_manifest` and `source_root`; V2 replaces those two fields with `source_archive` (a packaged source JSON path, or null for explicitly unbound legacy evidence). Mixing schemas refuses. The other fields are unchanged:

```
{"schema":"AFI_ACCOUNTABILITY_BUNDLE_V2","asof":"2026-10-19T23:00:00+00:00","forecasts":[{"artifact":"forecasts/<sha256>.json","dataset_manifest":"dataset-manifest.json","dataset_records":"dataset-records.json","source_archive":"source/<archive-sha256>.json","history":[],"expected_head":null,"append":null}]}
```

History entries have `artifact`, `dataset_manifest`, `dataset_records`, `source_archive`. An optional append entry has the dataset/source fields plus `outcome_asof`. Supply the expected last outcome hash when a history exists. Reconcile corrections using the complete supplied chain, retaining every original forecast, dataset vintage and source archive. No discovery of directories or silent history reconstruction occurs.

The report command validates all inputs before output publication, then returns the immutable report, scriptless dashboard, browser export and updated heads. Publication failures retain partial evidence and are not success. Do not overwrite or delete retained artifacts to force a retry.

## Evidence meaning

The SHA-256 envelope verifies exact report-string bytes, not source authenticity, dataset truth, whole-history completeness, executing-memory identity or forecast skill. Source packages pin supplied code bytes, not a Python/environment attestation. Caller-supplied expected heads protect a subset, not an independent rollback witness or global writer exclusion. Correction records revise outcomes; they never become additional forecast samples. Pending outcomes never become zero-error successes. No trading P&L, real calibration or live freshness is established by synthetic tests.

## Isolated validation

`node --test frontend/offline/forecast-accountability/view.test.cjs` covers malformed/contradictory evidence, asynchronous load races, limits, output collisions and publication faults. Python `tests/test_afi_portable_acceptance.py` runs the actual supplied source -> forecast -> resolution/correction -> backend export -> Node verifier and builds a local viewer. Fixtures are synthetic only; preserved session outputs are under `logs/diagnostics/full-roadmap-20261019`.

## Interval accountability continuation

The forecast CLI accepts optional --interval <frozen-calibration.json>. Supply the exact selected method, lookback, horizon and compatible source binding; invalid or mismatched calibration refuses before publication. It never fits or retunes calibration automatically. Published original intervals then flow through outcome history and the accountability bundle into the static/local viewer.

Coverage boundaries are inclusive. Pending targets/publications are not misses, missing interval values are not invented, and fewer than20 resolved outcomes is insufficient evidence. Model versions, lookbacks, assets, horizons and nominal levels remain separate. A model source/version identity is not an executing-memory attestation. Synthetic counts never establish calibration or trading edge.

The interval table follows visible filters. It shows the original level, coverage, width, interval score and sample status. Older reports that did not record intervals remain readable and are labeled unknown; they do not become zero-width forecasts. Mounted synthetic DOM tests are not native browser visual acceptance.


## Dataset and release partitions

New reports declare diagnostic_partition=DATASET_RELEASE_V1. Directional and interval counts separate explicit forecast dataset and release-source commitments as well as asset/model/lookback/horizon/level. A missing release commitment is UNBOUND, not verified provenance. Present malformed commitments refuse. Legacy stored aggregate bytes remain verifiable under their original contract; displayed interval cohorts are safely rederived from the original rows without rewriting evidence. These hashes establish supplied-byte consistency only. The frozen pre-partition synthetic report has SHA-256 0fa3fdab1837b3dea8ea8efaab44c22007f658d9aa2635e2886ce54db1f80672; original source SHA-256 455b0b96f0de0a28002bdde8e67c75cc3b975cb0768e7c1d3f79665d525e547a. No acceptance or real performance claim.

Directional evidence is also visible in the local viewer: exact three-state matrix counts, UP precision/recall and false/missed UP counts. Filtered tables rederive counts from verified rows; zero denominators remain unavailable. Rehashed contradictory directional summaries, fractional matrix counts and absent new-contract diagnostics refuse. Invalid replacement files clear both tables. DOM fixtures are not native browser visual acceptance.

New rows additionally retain the exact dataset manifest, dataset ID/version and model implementation commitment. Equal payload bytes do not imply equal manifest scope or model implementation; these remain separate diagnostic cohorts. Manifest/version metadata is all-or-none and validated. Missing historical metadata is explicitly legacy/unbound, never reconstructed from guesses.


## Row-bound score consistency

New reports declare score_rows_contract=ROW_BOUND_SCORE_V1 and retain the exact original scoring cohort and probability input for each row. Backend and viewer reconstruct counts, errors, probability bins, interval metrics and sample status from those rows. Contradictory metrics, unsupported nested acceptance claims, duplicate declared cases (including equivalent UTC timestamps) and removal of the contract while retaining its inputs refuse. Hash checks are consistency checks, not authenticity.

Legacy byte formats remain readable with explicit incomplete-input messaging. The backend checks totals and available unambiguous cohort metrics; missing historical probability/interval inputs and ambiguous legacy assignments are not inferred. The browser retains legacy count/directional/interval checks but cannot claim a complete reconstruction of absent scalar inputs. Old imported scalar metrics are not displayed as independently verified results. Synthetic repeated targets do not establish independent calibration, even at a descriptive sample threshold.


## Model parameter identity

New baseline forecasts carry model_configuration_sha256, a stable commitment to method, lookback, horizon and implementation conventions. It does not change on each training date. Current reports use ROW_BOUND_SCORE_V2 and retain this original identity in scalar, directional and interval cohorts; V1 remains readable with explicit unbound configuration. A configuration hash is not independent model approval or a proof of market skill. Duplicate configured cases and ambiguous legacy/configured versions of the same case refuse. New artifacts verify the commitment against reconstructed model parameters; historical artifacts and frozen selection serialization retain their original bytes.


## Visible model errors

The local viewer recalculates visible error cohorts from the filtered original rows using the same metric implementation as score verification. Asset, horizon, model/configuration, lookback, dataset/version and release commitments remain separate. Mean absolute error, flat-price baseline error, their ratio, root mean square error and Brier score retain their own resolved denominators. A zero baseline has an unavailable ratio. Pending cases never become zero-error results.

Legacy recorded prices remain useful; absent probability/interval inputs are explicitly missing, not invented. Recorded probability counts include resolved cases only. Unsupported numeric ranges show unavailable diagnostics while preserving the original rows. Failed replacement files or unsupported filters clear previous tables. Values are rounded to six significant digits for display; loaded evidence is never changed. These are synthetic diagnostics, not profitability, market skill, independent samples or production acceptance. Native browser visual acceptance remains separate from mounted DOM tests.

## Matched-case comparisons

Select model A and B or use bounded automatic comparisons. Only shared exact UTC issue/target cases with compatible data/reference and identical outcome provenance are scored. Unmatched, pending, conflicting and missing-evidence cases remain counted. Different interval levels alone are not distinct point models. More than 64 automatic pairs requires explicit selection. Negative A-minus-B absolute error means lower observed A error on those cases, not a winner or profitability. Repeated targets are not independent samples. Canonical context identifiers are not authenticated model approval. Corrections never create additional samples. No execution or network authority is granted.

## Matched interval comparisons

The interval table follows the same A/B selection and filters. Only point-paired outcomes with both original intervals at exactly the same nominal level contribute. Inclusive coverage, widths and interval scores share the interval-paired denominator. Missing intervals and level mismatches remain counted, never become coverage misses. Pending, unmatched and contradictory outcomes remain visible above. Repeated targets do not establish independent coverage. Legacy absent intervals remain unknown; new summaries declare MATCHED_INTERVAL_V1 and are recomputed from original rows before display. No calibration guarantee or model winner is established.

## Matched probability comparisons

The probability table uses the same A/B selectors and filters. It scores only recorded probabilities for price strictly above the shared reference against the same exact resolved outcomes. Flat is not UP. P(UP)=0 is a valid input; absent or explicitly missing inputs remain unscored and separately counted. Brier errors share the probability-paired denominator and the uninformative P(UP)=0.5 baseline has error0.25. Outcome corrections must agree before scoring; they never add samples. Lower observed Brier errors do not establish calibration, market skill, independent samples or a winner. Existing baseline artifacts without probability forecasts remain unavailable. New MATCHED_PROBABILITY_V1 summaries are rederived from original rows.

## Probability reliability bins

The reliability table follows filters and keeps model/data/configuration/nominal-interval contexts separate. All ten fixed bins are shown: lower inclusive, upper exclusive except the final bin includes probability1. Empty-bin means and observed fractions remain unavailable. Weighted bin gap uses only recorded resolved probabilities, with recorded, absent, unrecorded and pending counts shown separately. Partial legacy subsets are labeled explicitly; missing inputs are never zero probability. Distinct targets are counted per cohort and bin; repeated targets never establish independence. Descriptive bins and small weighted errors do not prove calibrated confidence or market skill. Display rounds to six significant digits, retaining original JSON precision.

## Unambiguous JSON imports

Both outer envelopes and decoded report/diagnostic JSON refuse duplicate object
keys, including identical values and escaped spellings of the same key. A correct
byte digest does not resolve contradictory JSON meanings. The native parser still
checks JSON syntax; a bounded token pass detects repeated decoded keys before
safety, row or score validation. Formatting, quoted string contents and repeated
keys in separate sibling objects remain supported. Invalid replacement imports
clear the prior loader model. Forecast values, denominators and scores are unchanged.

## Forecast horizon view

Choose All horizons,1 day or5 days to inspect the currently supported recorded
horizons. The choice intersects asset and outcome-state filters. History rows,
interval/directional/error/reliability tables, visible log loss and interactive
model comparisons use the same selected rows. No rows means unavailable evidence,
not zero error. The headline counts remain totals for the imported report.

For an explicit V2 companion, asset/horizon choices only hide or show complete
imported pair summaries. They never rescore the fixed pair plan or discard its
pending/conflicting cases. Outcome-state/model selectors do not alter that plan.
Changing the plan requires a new explicit export. This control does not implement
additional forecast horizons or certify prediction accuracy.

## Outcome changes between supplied report vintages

Load the current accountability export in the main picker, then an earlier report
in the optional prior-vintage picker. Log-loss companions are accepted through
the existing verifier; their source reports are compared. The table always shows
the full forecast-identity union, independent of display filters. Added and absent
forecasts stay right-only/left-only. An invalid prior import clears the comparison
without discarding the independently verified main report. Clear removes both.

Original fields and commitments must match for per-forecast impact. History/count
or publication regressions, replaced heads at the same count and identity conflicts
refuse metrics. Legacy records without original artifact/dataset/code commitments
remain unbound. Source revisions and provenance changes are explicit; matching
heads/counts do not independently prove chain ancestry, non-forking or authenticity.
Use the original Python history verifier with the source archives for those checks.

Right-minus-left absolute error is a per-forecast reported-price diagnostic, not
P&L or a cross-asset average. Same-side algebra avoids cancellation between huge
rounded errors; unstable opposite-side near-zero differences remain unavailable.
Updates never create extra forecast samples. No winner or calibrated skill follows.

## Interval and probability correction impact

The vintage comparison also shows original nominal interval level, inclusive
coverage and interval-score changes, plus recorded-probability Brier and natural
log-loss changes. Each row remains one exact forecast with its original uncertainty
inputs fixed. These are reported outcome effects, not revised forecasts, trading
results or calibrated coverage. No cross-asset or mixed-denominator mean is shown.

Unrecorded inputs, no fitted interval/probability, pending outcomes, refused
identity/history and unavailable numeric ranges remain distinct. Zero probability
is recorded input. One-sided impossible events have signed infinite change states;
two infinite losses have an undefined difference, never zero. Near-cancelled changes
and underflowed Brier values remain unavailable. Stable same-side interval penalty
and binary Brier differences avoid unnecessary subtraction of rounded large scores.

Publisher fixtures use Atlas's existing Laplace-smoothed probability method. The
separately labelled extreme-probability import fixtures are declared synthetic
boundary packets, not immutable publisher histories or market performance evidence.

## Reproducible offline comparison packet

With the installed Node runtime and matching source files, export two explicitly
supplied browser envelopes to an explicit new JSON file:

`node frontend/offline/forecast-accountability/vintage-export.mjs --export <prior-browser.json> <current-browser.json> <new-comparison.json>`

Verify without opening a browser or starting a service:

`node frontend/offline/forecast-accountability/vintage-export.mjs --verify <comparison.json>`

The packet embeds both original UTF-8 browser-envelope strings and their SHA-256
hashes, the comparison and its hash, and exact comparator/exporter/publication-helper
source hashes. It accepts accountability envelopes and existing log-loss companions.
Verification reproduces every result with the matching code. Keep the matching
three source files/archive; changed source refuses instead of rewriting old evidence.
Do not pretty-print or manually edit the canonical packet. No credentials/config
lookup, provider connection, startup or trading action is performed.

This CLI packet is not yet an accepted main-viewer import type. Its embedded source
envelopes can still be inspected separately through the existing two-file workflow.
One-file packet viewing remains a distinct next integration task.

Sources are limited to1MB each; the complete packet is capped at2MB. Malformed
UTF-8/BOM input is refused rather than silently normalized. Linked paths, changed
inputs/source files and existing outputs refuse. Partial publications are retained;
use a new output path after investigating. The shared publisher flushes, reads back
and checks file identity. It does not certify directory-entry persistence, hardware
power-loss durability, external-writer exclusion or full environment reproducibility.
A failed export may leave a byte-consistent file; `--verify` only checks supplied
bytes and does not retroactively grant durable-publication or production acceptance.

## Standalone one-packet comparison page

Build a new page with the installed Node runtime:

`node frontend/offline/forecast-accountability/packet-build.mjs <new-comparison-viewer.html>`

Generate the comparison packet using the matching current exporter/source archive,
then select it in that page. The page accepts up to2MB and displays the full union,
point-error changes, original interval impact and recorded-probability impact.
The existing main accountability picker remains unchanged at1MB; this is a
separate offline page, not a production route or live dashboard.

The builder embeds the three expected raw source hashes. The imported packet cannot
supply its own trust pins. Shared pure construction/verification is reused by the
CLI and page; the Node adapter separately checks filesystem source/input stability
and publication. Raw File ArrayBuffers are strictly decoded, so malformed UTF-8 or
BOM normalization cannot silently change the imported bytes. Missing WebCrypto,
wrong-source packets, forged results and failed replacements clear prior evidence.
Clear/replacement guards prevent late file reads or digest results restoring it.

Changed code refuses older packets. Retain the original matching source/archive;
the older demonstrated packet still verifies with its preserved CLI. No automatic
upgrade, evidence rewrite or authority follows. Browser API support is required
(File.arrayBuffer, TextDecoder, TextEncoder, BigInt, structuredClone, WebCrypto).
Native browser visual/CSP enforcement acceptance remains unestablished; Node
crypto/File/VM/DOM tests are not a substitute. No policy workaround was attempted.


## Signed price errors

The derived signed-error table uses forecast point minus the recorded actual price.
Positive means overprediction; negative means underprediction. It shows resolved,
pending, over/under/exact counts and the mean within the existing asset/model/data
provenance cohorts. Pending outcomes are excluded from the mean. These are price
units, not directional accuracy, PAPER P&L, a ranking or a new forecast sample.

Opposite errors can cancel: inspect counts alongside the mean and absolute-error
tables. Small or repeated samples do not establish independent skill or statistical
significance. Unsupported numeric ranges display unavailable, including a nonzero
sum whose mean cannot be represented. A missing resolved sample is unavailable,
not zero bias. Original report bytes/scores stay unchanged; this is a derived view.
The interactive table follows display filters; the scriptless report covers its
supplied rows. Existing immutable viewer builds are not rewritten; build a new
explicit artifact for this table. Native browser acceptance remains separate.


## Signed outcome-correction impact

When comparing two explicitly supplied accountability reports, the new signed-error
table holds each original forecast fixed. Signed error is forecast minus actual;
positive means overprediction, negative underprediction. Its change is computed as
earlier actual minus later actual, avoiding cancellation between rounded large
errors. A changed label is not a new forecast or evidence of model improvement.
Unmatched, pending, unbound and conflicting histories have unavailable metrics.
An absolute-error difference can be unavailable while the independently computed
signed difference remains finite. No cross-asset aggregate, independent ancestry,
source authenticity, skill or trading authority follows. Comparison packet models
are unchanged; immutable older pages retain their original UI and source pins.
Use an explicitly new build to obtain this table. Native browser acceptance remains
NOT_ESTABLISHED; automated mounted tests are not a substitute.

## Discrete forecast-case visualization

A new explicit build includes an optional plot inside this viewer. Choose one exact recorded cohort after importing verified synthetic evidence. Original forecast circles, observed outcome squares and nominal interval whiskers share a value axis; rows are cases sorted by target and identity, not a market-price trajectory. Pending outcomes have no observed marker. Complete model/dataset/code provenance is required to plot; unsupported legacy rows remain in the existing tables and are counted as unbound. Optional source receipts and interval levels remain separate. No automatic best cohort, inferred interval or missing outcome.

The plot follows asset/state/horizon filters and clears during replacement/refusal. Its exact-value table preserves chart order and full case/outcome identities. Recorded hashes prove supplied consistency, not source authenticity. Synthetic examples, corrections, repeated targets and nominal intervals establish no forecasting accuracy, calibration or independence. Existing archives are immutable: build a new explicit HTML path. Native browser visual acceptance remains NOT_ESTABLISHED.
