# Retained point-in-time descriptive research

Production NO-GO. Previous/current goal turns made implementation progress; the
full seven-phase objective remains unfinished. All21 release decisions and startup
denial are unchanged. No services, provider requests, Docker, Genesis, protected
state/configuration, trading, Discord or Git mutations. No runtime census claim.

## Working integration

`retained_research.py` connects receipt-vintage-filtered ReplayStore history to the
existing `analyze_market` function. A strict dated/currency/asset/symbol-matched
synthetic previous-session close and explicit availability are required. Reference
availability must follow that session's regular close and not exceed the decision
clock. The existing calendar validates the immediately preceding session. Prices,
source identity and asset-class labels are caller assertions, not authenticated
market/security-master evidence. Corporate actions are explicitly unreconciled.

Retained history is validated through the existing quality/candle contracts;
duplicate timestamps refuse. Future event/receipt data cannot affect current
analysis; late historical-baseline receipts are excluded before RVOL. Analysis
keeps the original bar-start180s freshness and RVOL window excluding the latest bar.
It does not loosen scanner/C1–C4 or change source calculations. Missing historical
baselines retain null RVOL. Current-day session volumes are explicitly observed
sums; no observations yield null volume, distinct from measured zero. Nonfinite
derived values and sums beyond portable integer precision refuse.

The inert factory optionally accepts a copied explicit reference map; there is no
provider/default-file lookup. GET-only/no-store `/api/market-data/research` and
escaped `/research` expose descriptive evidence. Missing references/history and
invalid evidence have explicit non-authorizing states. Existing overview links
to the view. No server or production route was started/mounted. Copying this map
does not establish whole-runtime development isolation.

Actual API JSON feeds `parseRetainedResearch` and `createResearchController`.
They reject authority/adjustment claims, unknown fields, incomplete/stale/future
bars/references, inconsistent observed-change arithmetic, unsupported RVOL and
fabricated zero unobserved volume. Failed imports/rendering clear the retained
model; both display errors remain available. No fetch, storage or Next production
mount exists. This is not native browser or independent calendar/source validation.

## Immutable export

An explicit mutually exclusive `--retained-research` mode accepts
`ATLAS_RETAINED_RESEARCH_REQUEST_V1`: now, history/reference relative paths and
separate expected hashes. The existing reviewed reader/publisher writes immutable
JSON/HTML/provenance and verifies exact readback. Later publication failures retain
earlier outputs without success. It introduces no multi-file transaction, crash
recovery, source authority or power-loss guarantee. Default bar and explicit quote
modes remain compatible; retained previous actual exports reproduced identical
JSON/HTML/provenance bytes and names in fresh output directories.

Actual storage→analysis→immutable export→frontend passed. Reports are synthetic
descriptive calculations, not forecasts, performance, alpha, orders or fills.
All startup/recovery/network/trading permissions remain false.

## Validation and remaining scope

Focused research tests22 passed, including five complete comparable-history sessions,
unknown/late baselines, future receipt/reference refusal, duplicate records, stale
bars, premarket/after-hours, DST/UTC-midnight and holiday/early-close date references,
reference-map copying, source/refusal, finite derived values and portable volumes.
Empty history does not bypass reference availability validation. Observed zero
volume is separate from an unobserved session, and optional premarket-gap evidence
is exposed only when premarket bars exist. The actual premarket result passes the
frontend consumer; the existing regular-session fixture remains byte-identical.
Ten new export cases joined prior modes in48 passing focused cases. The broader
run318 passed, followed by32 current focused cases with three additional boundary
cases:321 distinct selected Python cases, not350. Node208 passed. No remaining
test failures/skips. Targeted Ruff, frontend ESLint and compilation pass; overlapping
runs are never added. No full canonical suite claim.
Initial targeted lint findings were corrected narrowly; no product test failed.
Existing global lint/operational/license gates are not waived.

Real market-data collection still needs applicable provider/exchange/session/use/
display/storage rights, verified wire budgets and separately approved isolated
runtime acceptance. Main Atlas startup remains denied. No live coverage, actual
provider connection, backup/restore or production readiness is inferred from fixtures.

Evidence: `logs/diagnostics/retained-research-20261020`. The approved updater preserves
backup equality, managed readback and historical bytes outside the checkpoint.
All seven phases, AFI PENDING, Gaming objective and Prediction Market Intelligence
V2 safeguards remain intact.

Next selected task: bounded point-in-time replay of descriptive research over an
explicit sequence of decision clocks and reference vintages. Report observed,
unavailable and refused decision denominators without inventing labels, fills or
P&L. Prove future-data perturbation invariance and preserve immutable per-decision
evidence; reuse existing analysis/export rather than another storage framework.
Then continue independent Evidence Engine/AFI roadmap work.
