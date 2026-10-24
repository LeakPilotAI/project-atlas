# Quality Dips frontend integration V1 — offline acceptance and continuation

Authorization **P-QD-FRONTEND-V1-OFFLINE**. Base `dc13cf81368468395ba058c25d92b9925a989e20`, branch `chatgpt/atlas-rebuild-v1`. Source-only selected-account presentation IMPLEMENTED / DISPOSABLE VERIFIED. Operational endpoints NOT REGISTERED. B1/C1/D1/E1 BLOCKED;all21decisions unchanged;PAPER startupNO;productionNO-GO.

## Exact implementation

| File | Change |
|---|---|
| `backend/app/static/quality_dips.html` | Existing screen gains a clearly labelled Selected PAPER Account mode/section. Original research design, views and ranking display remain. The common10s poll routes according to mode; research calls and late callbacks are guarded. Direct selected-mode query is initialized before polling. No trade-entry/exit controls. Responsive facts/table styles and accessible status/navigation. |
| `backend/app/static/quality_dips_selected_paper.js` | Isolated read-only presentation controller: fixed selected GET, serial request guard, bounded abort, mode-generation cancellation, scope pinning, monotonic source revision/conflict refusal, exact string formatting, escaping and explicit missing/stale/UNKNOWN states. It has no polling interval of its own. |
| `backend/app/api/quality_dips_selected_paper.py` | Backward-compatible optional read metadata: verified scoped `inception` and `projection_revision`. No operational registration or financial dispatch change. Missing fields stay null; incorrect account/epoch/policy/currency/Decimal capital or projection revision refuses. The existing payload verifier binds the entire supplied read response. |
| `tests/quality_dips_selected_frontend.test.cjs` | 25 deterministic shipped-script DOM/fetch contract tests. |
| `tests/quality_dips_selected_application.cjs` | Shipped HTML/external/inline scripts consume actual disposable Python financial responses; no browser/server. |
| `tests/test_quality_dips_frontend_application.py` | Five tests for disposable ledger/projection/report/API/page flow and exact optional read metadata scope. |

No Next application files, dependencies, startup locks, Windows launchers, actual strategy engines, native storage or financial transition code changed. No real financial records were read or written. Existing untracked work is preserved and excluded from publication.

## Financial read display

The panel displays response-supplied account/epoch, selected policy/schema/digest, source/projection revision, original hypothetical cash, verified cash at snapshot, exact remaining/original shares and position identities, realized gross/net/total costs, supported aggregate or separately labelled report fees/slippage, candidate statuses and reasons, source-observation time, report completeness and exclusive/effective reporting cutoffs with the report timezone. Decision explanations are explicitly NOT trade authorization. Frozen entry-decision explanations are labelled as historical decision evidence, not current instrument eligibility.

Missing fields render UNAVAILABLE. There is no hardcoded$1000 balance, fabricated cost allocation, total-equity estimate or$0 valuation. Financial decimal strings are preserved, including zero and exact fractional quantities; the research view's floating-point price formatter is not reused. Cash and realized results are not summed with any legacy account. Legitimate overnight positions remain visible; only an acknowledged response with no positions displays that this selected projection has no open positions.

INCOMPLETE reporting is distinct from acknowledged financial records. UNKNOWN/INCOMPLETE/UNAVAILABLE top-level reads clear previous current amounts. Network failure may retain only an explicitly labelled STALE last acknowledged snapshot, never a current balance. Stale/future response sources cannot become fresh displays; scope changes, revision rollback/conflicts and malformed evidence refuse. Visibility return and refresh check source age without creating a new polling loop. Lifecycle acceptance remains NOT_EVALUATED; no completion or liquidation is implied by a report or render.

## Selected mode versus research

The existing page's source query `?mode=selected-paper` selects the financial read-only mode **before** the common poll starts. This is a future authorized-host navigation mode, not an instruction to launch Atlas now. The selected button also switches mode visibly; research buttons explicitly switch back. In selected mode, `load()` returns through the selected read controller before the legacy research URL can be invoked. Missing selected script or endpoint produces UNAVAILABLE; it never falls back to research, archive balances, providers or services.

The selected controller issues only GET `/api/investments/quality-dips/selected-paper`, cache:no-store, same-origin, with an abort signal. It never calls `/commands` or the legacy research GET. One existing common poll plus one active-request guard prevents duplicate selected polling; manual read refresh is similarly serialized. Mode changes invalidate old tickets and abort a pending selected read; late selected/research responses cannot overwrite the active mode. A timeout response cannot be accepted even if the injected test transport ignores cancellation.

A research request initiated *before* a mode change cannot have its already-started server work undone by client code. This milestone suppresses all new research requests in selected mode and ignores its late response; the zero-legacy-request bootstrap is the direct selected-mode query. Existing research refresh behavior is unchanged and remains explicitly separate. The shared research freshness chip is hidden in selected mode so it cannot mislabel financial freshness.

## Application and browser-oriented evidence

Final Python combined run: **271 passed,0failed,0skipped**,17.98s. This includes the previous265-case integration/compatibility/startup selection, five new frontend application/metadata cases and one retained research visual-contract wrapper. The old265 run is not added again.

Separate JavaScript unit selection: **25 passed,0failed,0skipped**,Node built-in test runner. These are distinct Node test IDs; the application-bridge and retained research-script assertions invoked inside Python are counted within their Python cases, not added again as JavaScript tests.

The disposable application test executes the actual FS2/FS3 protocol classes with the previously documented ordinary-file/native-primitive injection, performs an explicit manual ETF entry, an overnight partial exit, final exit and pure FS3 report generation, obtains the unregistered read function's verified responses, then feeds them to the actual shipped page scripts. It verifies cash900.0→943.968→1009.920, original1000 inception, remaining2.5→1.5→none, original candidate decision reasons, daily fees/cutoff/INCOMPLETE reporting, then a missing-read refusal. Report generation happens only in explicit fixture setup, NEVER inside GET. Before/after file fingerprints prove reads do not mutate the fixture sources.

JavaScript cases cover multiple supplied ranked stocks/ETFs, selected/rejected/research-only reasons, precise fractions, zero/missing values, scoped report costs, stale/future data, network/HTTP refusal, HTML escaping, account replacement, source rollback/conflict, malformed input, overnight positions, duplicate polls, cancellation/timeouts, missing-script fail-closed behavior, selected bootstrap, explicit research return, late research-response suppression, responsive CSS structure and accessible live status announcements.

Tests record every mocked request: selected bootstrap/polls use only the selected GET and GET method. A pending research request is shown to have started only while research mode was active. The Node application bridge forbids the legacy request outright across all four response frames. There are no client provider/writer/start capabilities or working trade controls. Endpoint registration and production lock regressions remain passing; main.py and locks remain unchanged.

Ruff passes for the2changed Python files;both compile in memory. ESLint recommended checks pass for4JavaScript surfaces(new controller,two Node tests,actual inline page script),using existing installed tooling. Syntax checks pass;checkpoint updater PowerShell parses and diff checks pass before publication. Initial lint-only findings(unused research catch binding,test global name collision,explicit subprocess check argument) were corrected without changing safeguards. No runtime test failures remain or were suppressed.

**Limits:** no real browser, rendered screenshot, CSS layout engine, accessibility assistive technology, running HTTP/ASGI server or actual network request was tested. VM DOM/fetch assertions and static responsive/accessibility checks are browser-oriented fixtures only. No native protected storage, handle/ACL/ownership tests or operational financial services were activated. No Next build is needed/claimed for unchanged Next sources; this is a static HTML/JS surface with syntax/lint/runtime fixture checks. These results do not grant operational or native security acceptance.

## Exact next operational requirements

The frontend source integration is complete for this scope. Next is separately authorized binding of accepted **read-only** projection/report/inception capabilities to the existing router factory, followed by explicit operational route registration in an accepted bootstrap and genuine supervised browser/HTTP acceptance. Do not infer registration permission from this report. Readers must verify actual resource identity,current high-water/source completeness,account/epoch/policy and fresh clock without publishing financial records/reports, refreshing providers or triggering recovery writes. Real inception/candidate/cost metadata remains unavailable until those accepted readers supply it.

Before any operational PAPER session:B1 independent V3 account/capital/legacy exclusion/risk/instrument scope acceptance;C1 exact native writer/resource/ownership/exclusion/drain acceptance;D1 protected enrollment,issuer/manual authority,current pins,clock,rollback/recovery acceptance;E1 provider rights and execution-price rules,backup+isolated restore,native lifecycle and supervised release. Startup stays locked. Trade commands remain a later separately authorized boundary. No legacy reconciliation assumption or live-money authority is introduced.

Roadmap/state/queue updated through the established updater with backup equality,exact read-back and byte-identical outside-managed history checks. All7phases remain:1core/PAPER incomplete;2EvidenceEngine/AFI HOLD(AFI1–10PENDING,0accepted);3historical/prediction expansion BLOCKED(optional15-minutecrypto deferred);4Cross-Market pending;5SaaS pending/deferred;6institutional pending;7commercial pending. Original phase definitions and21decisions remain authoritative.
