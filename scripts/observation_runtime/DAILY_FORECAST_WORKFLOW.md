# Offline daily-source forecast workflow

This command is for explicitly supplied **synthetic fixtures in a disposable,
caller-owned directory**. It does not fetch data, connect a provider, start Atlas,
admit a research session, create orders, clear recovery state or send messages.
Production remains NO-GO. Never point it at production state or database volumes.

1. Retain each raw chart fixture under its exact lowercase SHA-256 plus `.json`.
   Use `daily_afi_export` with an explicit request to reconstruct its dataset.
   Preserve original receipt timestamps and earlier snapshots when adding labels.
2. Create a `ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1` JSON with `asof` and a
   `forecasts` array. Each item requires `daily_export`,
   `expected_daily_export_sha256`, `asset_id`, `issued_at`, `method`, `lookback`,
   `horizon`, `interval` and `probability_method`. There are no implicit model or
   permission defaults. `interval` and `probability_method` may explicitly be null.
3. Invoke `scripts.observation_runtime.daily_forecast_batch` using the existing
   development Python environment with the repository and `backend` on its module
   path, passing `--bundle-root`, `--request` and `--output-root`. Both roots must
   identify the same existing isolated bundle. Maximum 32 forecasts and eight
   distinct daily export bindings. All models preflight before publication.
4. Retain the returned `daily_receipt` filename and its SHA-256 independently of
   the mutable request filename. This caller commitment detects disagreement with
   that supplied receipt; it is not an independent history witness.
5. To verify without publishing, use `--bundle-root`, `--verify-receipt` and
   `--expected-receipt-sha256`. Do **not** supply an output root. Verification
   reconstructs daily inputs, the plan, fitted forecast envelopes, the index and
   exact dashboard bytes. It does not repair, sync or acknowledge durability.
6. Later labels use the existing explicit `AFI_BATCH_ACCOUNTABILITY_REQUEST_V1`,
   `prepare_batch_accountability` and `run_bundle` interfaces. Supply every history
   link and retained head. Later cumulative dataset versions must preserve all
   previously committed records and receipts. Corrections append new revisions;
   never rewrite original forecasts or calibration artifacts.

Publication uses the existing checked content-addressed publisher. A failed step
must leave partial evidence intact and return failure. The underlying batch
preserves per-forecast failure evidence. A receipt does not establish an atomic
multi-file transaction, hardware crash immunity, independent source truth,
historical completeness or protection against hostile same-account writers.
Identical retries revalidate existing evidence; conflicting partial files refuse.

The strict read-only verifier can also be called as
`verify_daily_forecast_receipt(bundle_root=..., receipt_name=...,
expected_receipt_sha256=...)`. It reuses the same forecast reconstruction that
supports batch accountability, with an additional exact-renderer dashboard check.
Local code/renderer revisions can cause reconstruction refusal; matching supplied
bytes is not attestation that those modules actually executed historically.

`tests/test_daily_forecast_batch.py`, `test_daily_forecast_verifier.py`,
`test_daily_batch_accountability.py`, `test_daily_interval_workflow.py` and
`test_daily_export_packaging.py` contain executable synthetic examples. The clean
extraction tests use the current interpreter and installed timezone data; they do
not establish clean-machine installation or native browser rendering.

Daily close inputs remain unadjusted, regular-session-only, calendar bounded and
receipt-available. Known unmapped corporate actions refuse. Premarket/after-hours
research uses the separate existing intraday contracts; this daily workflow does
not relabel extended-hours prices as cash closes. Provider rights, entitlements,
live freshness and operational acceptance remain separate blocked gates.


## Separate daily price/forecast visual companion

`scripts.observation_runtime.daily_forecast_visual` accepts `--bundle-root`,
`--receipt`, `--expected-receipt-sha256` and `--output-root`, with an optional
plain-text `--title`. It verifies the receipt before constructing a scriptless
HTML companion and checks source commitments again before checked publication.
It never opens a browser. The same explicit isolated bundle must retain inputs
and output. Existing dashboards and forecasts are not replaced.

Each panel shows the last128 cash-session closes actually known at its own issue
time, an equivalent receipt/revision table, the forecast target and any explicitly
fitted interval. Later corrections and later target observations are excluded
from the historical chart. Horizontal spacing is in cash sessions; a5D forecast
is drawn five cash sessions beyond its reference, rather than one. Nominal
intervals do not establish coverage, and no source truth, live freshness or
trading/recovery permission is inferred. Native browser acceptance remains
NOT_ESTABLISHED.


## Caller-receipt availability diagnostics

`scripts.observation_runtime.daily_availability` requires `--bundle-root`,
`--binding`, `--expected-binding-sha256`, `--asof`,
`--max-first-receipt-age-seconds` and `--output-root`. It reconstructs an existing
synthetic daily export, keeps first-known closes separate from later price
revisions and repeated confirmations, and publishes checked JSON/scriptless HTML.
A partial publication is not a completed export; retain every partial artifact.

Ages are calendar elapsed seconds between the actual cash close and the caller's
recorded receipt, including nights/weekends. A bulk download cannot establish
historical availability, and a recent confirmation does not refresh the original
close. The caller's age budget is only a diagnostic threshold, never a provider
entitlement, feed-health or operational decision. Provider freshness always stays
NOT_ESTABLISHED. All records contribute to summary denominators; only the most
recent128 observations are displayed.

The visual companion accepts an optional `--availability-budget-seconds` to show
this chronology at the report cutoff, separately from issue-time price history.
Omitting the option preserves the existing visual bytes. Source commitments and
caller clocks are checked, but hostile concurrent writers, independent archive
truth and authenticated vendor latency are not established.


## Source-bound probability replay

`scripts.observation_runtime.daily_probability_replay` requires `--bundle-root`,
`--request` and `--output-root`, all explicitly selected isolated resources. The
request schema is ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_REQUEST_V1 with
`daily_export`, `expected_daily_export_sha256`, `issues`, `expected_issues_sha256`,
`asof`, `outcome_asof`, `method`, `lookback`, `horizon`, `probability_method`.
Source and issue-list names must be exact SHA256.json. Supply1–128 chronological
aware issue timestamps; controls must explicitly select a supported baseline and
next-close probability method. Unsupported controls refuse globally instead of
pretending to be data-availability cases.

The adapter reuses the existing AFI replay/fitter/scorer/scriptless renderer. It
preserves the exact request bytes as a checked snapshot, retains refused/pending/
missing outcomes in the requested denominator, checks the published replay
against source-bound preflight, and publishes a companion only after source and
issue commitments still match. Partial failures retain all evidence and return
failure; identical retries never replace records. No original file is repaired.

Bulk downloaded prices do not establish earlier availability: requested issues
before the supplied first receipt cannot acquire fabricated training history.
These are synthetic retrospective diagnostics, not independent holdouts, actual
market performance, authenticated receipt times or permission to forecast using
unauthorized live datasets. Source completeness and vendor truth remain unproven.


The source-bound replay command also supports read-only `--verify-companion`
with `--expected-companion-sha256` and `--bundle-root`; no output root is allowed.
It loads the exact immutable request snapshot, reconstructs the daily graph and
requested cases with the existing engine, and compares exact report/dashboard
bytes, counters and denial flags. It does not publish, repair or re-sync files,
acknowledge durability, attest historical execution or prove independent history.
The mutable original request filename is not required once its checked snapshot
and all committed source dependencies have been retained.

## Frozen daily probability protocol verification

The explicit `--freeze-protocol` and `--evaluate-holdout` modes bind selection
and evaluation to one exact immutable daily archive and plan. They provide
retrospective algorithmic partitioning, not independent unseen custody or a
prospective growing archive. Later source versions cannot silently replace the
committed source. Training and selection labels must respect the freeze cutoff.

Verify a retained protocol before holdout evaluation with `--verify-protocol
<SHA256.json> --expected-companion-sha256 <SHA256> --bundle-root <directory>`.
Do not supply an output root. This reconstructs the source, immutable request,
selection plan and exact protocol bytes without publishing or evaluating holdout.
The outer file SHA and inner logical protocol digest are distinct commitments.
Missing or altered members refuse; no repair, authority or recovery is granted.

Corporate-action visual context is rendered only when action records are supplied.
It shows at most128 same-asset actions known by each forecast issue, with separate
effective/receipt times, units and exact source hashes. Future-effective announced
actions are distinguished from already-effective actions. Later receipts are not
shown. Empty rows do not attest complete action coverage. Source prices remain
unadjusted; dividends are excluded from price returns and no total-return or
reinvestment result is implied. This adds no economic adjustment or authority.

Legacy no-action V1 export verification reconstructs the exact historical
serialization when the current serialization does not match the retained pin.
Only requests without any action_snapshots field qualify. It regenerates the old
revision preimages and newline-preserved records/manifest/audit from verified raw
sources, then requires exact pinned bytes for every member. No current publisher
uses this profile; current source hashes/action evidence remain intact. This
proves reproducibility of supplied historical bytes, not historical execution or
independent custody. A caller could serialize the same synthetic data in the old
format today; verification never authenticates its age or grants authority.

Read-only holdout coverage: `--diagnose-holdout <SHA256.json>` with
`--expected-companion-sha256` and `--bundle-root` prints a reconstructed diagnostic
JSON without an output root. It reconciles requested/issued/refused/resolved and
unscored denominators, lists exact per-case source reasons, and groups refusals.
Pending target, pending publication and absent supplied outcome are distinct;
none is silently scored as an error or evidence of a missed market event.
Existing report formats and scoring remain unchanged. Diagnostic source graphs
are verified before and after construction; concurrent hostile writers are not
excluded and no provider truth, calibration or independent custody is attested.

For a human-readable coverage companion, run the explicit module
`scripts.observation_runtime.daily_holdout_visual` with `--bundle-root`,
`--companion`, `--expected-companion-sha256` and the same `--output-root`.
It reuses verified holdout diagnostics and checked content-addressed HTML
publication. The scriptless page explains states, denominators and grouped
refusal causes; original holdout reports retain per-case scores. No browser,
service, provider or trading action is started. Native browser acceptance remains
NOT_ESTABLISHED. Partial failures preserve source evidence and report failure.

## Holdout to the existing offline workspace

Explicit module `scripts.observation_runtime.daily_holdout_accountability` accepts
`--bundle-root`, `--companion`, `--expected-companion-sha256` and the same
`--output-root`. It verifies the holdout, reconstructs the exact issued forecasts
through the existing daily batch engine, and uses existing outcome/accountability
engines to publish `AFI_BROWSER_REPORT_V1`. Select that browser_export JSON in the
existing workspace forecast page; keep its bridge companion beside the evidence.
No workspace/viewer rebuild or schema change is required.

The browser report contains issued forecasts only. The final bridge companion
preserves the full requested counts and exact refused cases; never present the
browser forecast count as the requested holdout denominator.1–32 issued forecasts
are required; all-refused or larger runs refuse rather than invent or truncate.
This is synthetic reconstruction, not proof of prospective publication/history.
Failed multi-file publication preserves partial evidence and grants no success.
Independent standalone bridge reconstruction verification remains a follow-up.

Verify a retained holdout workspace bridge read-only using the same module with
`--verify-bridge <SHA256.json> --expected-companion-sha256 <SHA256>` and
`--bundle-root`. Do not pass `--output-root`. The verifier reconstructs the daily
batch, exact holdout forecasts, initial outcome records, accountability report,
HTML and browser envelope without any publisher or append operation. It compares
full bridge bytes including all refusal counts/claims. Missing evidence refuses;
verification neither repairs files nor establishes independent history or custody.

Prepare a portable no-append seed with `--prepare-continuation <bridgeSHA.json>`,
`--expected-companion-sha256`, `--bundle-root` and the same `--output-root`.
It verifies the original bridge, preserves original forecast paths and initial
outcome histories/expected heads, then publishes an existing V2 accountability
bundle plus a companion retaining original counts/refusals. No forecast or outcome
is created by preparation. Verify the seed using `--verify-continuation` and its
retained companion pin without an output root.

Later explicit synthetic label updates can use the existing forecast_report
run_bundle interface with that seed, caller-specified outcome archive/cutoff,
and a validated relative output mapping. Retain the seed companion with all later
bundles: its original_counts are the original holdout snapshot, not an updated
pending/resolved count. Original forecasts stay fixed; corrections add history,
not independent forecasts. Missing committed history or rewritten source records
must refuse. This is not authorization for real collection or historical custody.

## Explicit source-bound label updates

Use `scripts.observation_runtime.daily_holdout_update --bundle-root <root>
--request <SHA256.json>`. Request schema ATLAS_SYNTHETIC_HOLDOUT_UPDATE_REQUEST_V1
requires seed/expected_seed_sha256, continuation/expected_continuation_sha256,
daily_export/expected_daily_export_sha256, asof, outcome_asof and output_prefix.
The output directory must already exist inside the bundle. No directory or source
is selected automatically. Preparation verifies the seed, exact continuation,
initial history prefix, fixed forecast population and full proposed outcome chain
before publication. Current issued states and original holdout counts are distinct.

Successful output includes a portable continuation and existing browser export;
refused original requests remain refused and never become new forecasts. Identical
explicit retries are idempotent. This is not an independent latest-head registry:
valid historical continuations can form retrospective branches. Keep the exact
caller-retained head and prior companions; no global anti-rollback or writer
exclusion is claimed. Failures preserve partial evidence, with no silent repair.

Verify a label-update companion read-only with
`daily_holdout_update --bundle-root <root> --verify <relative/SHA256.json>
--expected-companion-sha256 <SHA256>`. This reconstructs the selected branch's
outcome records, portable continuation, report, HTML and browser export with no
publisher calls. It rechecks the source graph after construction. Missing or
altered evidence refuses; it does not repair or establish a global latest head.

Successive browser exports can be compared with the existing
frontend/offline/forecast-accountability/vintage-export.mjs exporter. Keep its
source pins and the matching generated packet page together. An older immutable
workspace may correctly refuse a newer packet when comparator pins differ; do not
rewrite its manifest or weaken checks. Use a separately generated matching page.
Source-bound Python verification and packet consistency do not establish native
browser acceptance, independent source truth or historical runtime ancestry.


## Prepare a request from explicit source groups

Use `--prepare-selection <selection.json>` instead of `--request`, with the same
explicit `--bundle-root` and `--output-root`. Both roots must be the same existing
isolated synthetic bundle. This only publishes a checked request; it does not
publish forecasts, run a service, select a best model or authorize any session.

The selection schema is `ATLAS_SYNTHETIC_DAILY_FORECAST_SELECTION_V1`, with exactly
`schema`, `asof` and `groups`. Each group has `daily_export`,
`expected_daily_export_sha256`, `asset_id` and `forecasts`. A group's explicit
forecast choices each contain `issued_at`, `method`, `lookback`, `horizon`,
`interval` and `probability_method`, using the same values/contracts as step2.
There are no implicit model, clock, probability, interval or universe defaults.
Up to8 groups expand to at most32 forecasts. Every binding and model preflights
through the existing batch engine before the request is published.

Retain stdout's `request` and `request_sha256`, then explicitly pass that request
filename to the normal `--request` command when ready for offline publication.
`forecasts_published:false` means exactly that: request preparation is not a
forecast result. `selection_sha256` binds the supplied bytes, not an independently
authenticated source. Exact retries retain the same content-addressed request.
A failed publication may leave partial evidence; preserve it. Ordinary input
changes are rechecked, but hostile same-account writer exclusion is not claimed.
The normal receipt verifier and all provider/production restrictions remain.


## Preview label updates without writing

Use `daily_holdout_update --bundle-root <root> --preview <content-addressed-update-request.json>`
to inspect an existing explicit update request before calling its publication mode.
No output files, outcome appends or heads are changed. The request's explicit output
prefix must already be an existing isolated directory under the normal contract;
preview does not create it. Do not pass a verification companion pin to preview.

Stdout reports original holdout counts/refusals, current and proposed issued-state
counts, and each original forecast's current/proposed state, target, previous head,
proposed head, recorded outcome event and `would_append` flag. A recorded correction
is not necessarily a new correction: interpret the event together with `would_append`.
All proposed changes are relative to the explicitly supplied continuation, which
is not independently attested to be the latest. No new forecast samples are created.

The existing no-write outcome evaluator validates all history and expected heads.
Ordinary source-graph changes are rechecked before returning the preview. This is
not writer exclusion, an independent latest-head witness, publication authorization
or a durability acknowledgement. Publication remains a separate explicit `--request`
operation that revalidates its inputs. Invalid preview inputs refuse without writes.


Preview's `proposed_append_events` counts only cases with `would_append:true`.
An already-current head may retain a historical `recorded_event:CORRECTION`, but
its proposed-append event summary is empty. Label corrections and reobservations
never create additional forecast samples. Counts are relative to the supplied
continuation, not proof of an independently latest history.


## Read reported label changes in the existing forecast viewer

Keep both the earlier and updated `browser_export` JSON files. In a newly built
offline forecast page, select the later export as the main report and the earlier
export as the prior report. The existing reported-outcome comparison includes a
signed-error table. For each same original forecast, error is point minus actual;
change is earlier actual minus later actual. No new forecast is created by a
correction, and a changed error does not establish improved forecasting skill.
Pending, missing original bindings and conflicting histories remain unavailable.
Clear or a refused replacement removes earlier comparison rows. Old immutable
pages retain their original features; matching source pins still apply to packets.
Native browser acceptance remains unestablished. These files are supplied synthetic
evidence, not an authorized live feed or proof of independent latest history.


The no-write update preview now also includes `signed_error_impact` for each original
forecast: current/proposed actual, current/proposed signed error, and the proposed
minus current change. `CURRENT_UNRESOLVED` means there is no current error/delta;
a finite proposed error may still be shown when resolution is available. These
are descriptive label effects, not a new fitted forecast or permission to publish.
For already-current heads the proposed change is zero even if the retained event
is a historical correction. The explicit status and `would_append` fields remain
necessary. Preview does not alter any history, files or heads.

## Interrupted update publication

The update command exits with code 2 and a refusal/incomplete message when a
required operation fails. No successful JSON receipt is printed in that case.
Keep the exact request, original sources and any partial output; the absence of
a final receipt does not mean that no files were written. Do not delete partial
files, modify their hashes or replace them to force a retry.

A separate explicit retry of the identical request revalidates its source graph
and existing content-addressed artifacts. A completed artifact with identical
bytes can be reused; conflicting or incomplete artifact bytes must refuse. An
interruption before the final companion can therefore finish without duplicating
outcome history, provided all preceding artifacts remain valid. This is not
automatic recovery or permission to clear any runtime uncertainty fence.

Preview is not a reservation: changed request, continuation or source bytes are
checked again by publication. Preserve a refused request and its evidence; create
a separately reviewed request only when its new inputs are justified. After a
successful publication, verify the exact companion and pin using `--verify` before
using its browser export. Neither replay nor verification establishes that the
selected branch is independently the latest.
