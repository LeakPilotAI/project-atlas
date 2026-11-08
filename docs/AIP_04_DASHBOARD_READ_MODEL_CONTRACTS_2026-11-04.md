# AIP-04-DASHBOARD-READ-MODEL-CONTRACTS

**AIP-04 COMPLETE — SOURCE-ONLY/DISPOSABLE. PAPER:NO. Production:NO-GO.**

November4,2026 (America/Chicago). Base `8170c46be5f7a8d99d61ce7ac8e0b91cc96dce5e`, branch `chatgpt/atlas-rebuild-v1`.

## Canonical scope and existing inventory

The canonical18-milestone audit defines AIP-04 as original six-tab API mapping and controls, depending on AIP-01 and the HL slice of AIP-02. DONE means source/ASGI contract coverage, honest unsupported surfaces and preserved SOON labels; genuine browser acceptance remains pending. It requires source/freshness/account/revision accuracy, UNKNOWN/UNAVAILABLE rather than zero, GET purity, hidden-frame polling safety and Stop only through an accepted owned session. AIP-01/02/03 remain complete at their existing source/disposable scopes.

The existing original shell is `backend/app/static/dashboard_hub.html`; it embeds Perp Day Trade, Quality Dips, Investment, Archive, Command Center and Prediction Markets, with Analytics/Portfolio retained as SOON. Original perps/investment/prediction pages call legacy API graphs. `desktop_observation.py` already supplies the original shell/assets with observation-only fallback; this task neither starts nor changes that host. `quality_dips_read_service.py` and `quality_dips_selected_paper.py` provide separately accepted selected-QD reads; `SelectedReadCapability` replays/audits acknowledged financial projections. `UnifiedMarketReadCapability` and portfolio custody provide the existing two-account wire shape. `runtime_poll.js` already stops hidden-frame requests and serializes polling. `quality_dips_selected_paper.js` already renders separate account cuts and clears unavailable data.

Missing was an explicit current AIP-01/AIP-02 -> dashboard read-model connection and a safe source-only six-tab contract composition that does not invoke the legacy financial GET graph or claim an installed financial capability. No backend `app.main` startup, legacy scanner/book initialization, account file or operational financial runtime was used.

## Implementation and wire contracts

All four implementation/test files are new; no existing strategy, financial, runtime, shell, polling or renderer file is modified.

| File | Responsibility |
| --- | --- |
| `backend/app/services/dashboard_read_models.py` | `DashboardReadModels`: exact current `UnifiedResearchSources` pair plus optional narrow account-reader port; versioned `ATLAS_DASHBOARD_READ_MODEL_V1`, bounded source reads, source identity/revision/time/digest/account/epoch, coherent final reread, deterministic content identity, explicit absence and failure states. |
| Same module, `DashboardAccountRead` | Read/verify-only adapter preserving `ATLAS_UNIFIED_ACCOUNT_CUTS_V1`; explicit account scope/domain/clock/authority, both original accounts, exact decimals, accounting/position/currency checks, current readback, original revision continuity and structured owner proof. No financial runtime construction or writer port. |
| `scripts/observation_runtime/dashboard_read_contracts.py` | Unregistered ASGI factory only, no listener/CLI/startup hook. Original six-tab shell and URL mapping, read-only contract panes, explicit API boundary, immutable static bytes and default command refusal. |
| `backend/app/static/dashboard_read_contract.js` | Escaped read-only rendering through existing `atlasPoll`/`atlasFetch`; aged or failed observations clear values. No command/provider calls, browser ACK or financial authority. |
| `tests/test_dashboard_read_models.py` |51 in-memory producer/account/ASGI/Node consumer cases. Uses actual AIP-01/AIP-02 source producers over their existing native-memory double, never operational records. |

The new optional ASGI factory serves the **original navigation shell byte-for-byte** at `/dashboard`. Its original iframe URLs map to safe read-only contract panes, avoiding legacy pane scripts whose GET paths can have side effects. Those contract panes are a source-level presentation integration, **not an assertion that every old pane feature or installed UI is accepted**. Existing full legacy HTML/JS files remain untouched. This is neither a replacement active installation nor a modification to the frozen payload/launcher. Any future installed integration needs immutable packaging, source-origin/resource acceptance and separately authorized deployment.

| Original pane URL | Implemented read contract |
| --- | --- |
| `/dashboard/perps?embed=1` | Accepted current HL research, original discovery/setup board, source provenance and independently proven USDC account summary if supplied. No manual/execution command. |
| `/api/investments/quality-dips/view` | Accepted QD bundles/monitors and their original rankings/provenance; independently proven USD account summary if supplied. Research rows never become positions. |
| `/dashboard/investment` | Explicit unavailable: no accepted independent investment read capability or funded lane inferred from QD research. |
| `/dashboard/archive` | Explicit unavailable: no archive/history capability is implicitly enrolled or scanned. |
| `/dashboard/command-center` | Runtime connection, Stop and continuation unavailable without their separate accepted capabilities. PAPER startup blocked; no command buttons or routes. |
| `/dashboard/prediction-paper` | Explicit unavailable: no prediction model/account/settlement capability supplied. |

`GET /api/dashboard/read-model` is the common versioned snapshot. `GET /health` reports only that this read app responds; scanner/financial writers/tracker are false and provider state is UNAVAILABLE. `GET /api/investments/quality-dips/selected-paper` preserves the existing **unavailable** wire shape: this factory has no accepted selected-financial reader and cannot reinterpret a research view or account summary as one. Other legacy API paths return503 unavailable, not generated prices, paper orders, balances or zero statistics. Unknown non-API paths return404.

## Evidence, identity and failure behavior

- Research requires the exact AIP-01/AIP-02 unified producer interface and common injected clock. QD readback preserves its original30-second limit and HL its original5-second limit; neither input nor publication counters are repurposed as financial revisions. HL board generation reuses the existing `research()` and strategy helpers. QD bundles remain original research evidence; no entry/exit/ranking rule changes.
- Each lane retains its currency, source ID, source revision, packet digest, original timestamp, scope account/epoch and age bound. Completeness says `ACCEPTED_SOURCE_CUT_NOT_FULL_MARKET_COVERAGE`; a valid bounded cut is not a claim to cover the whole market. Connection remains UNAVAILABLE because current accepted research does not prove a live provider/session.
- Missing research is UNAVAILABLE. Invalid/revoked/conflicting evidence is UNKNOWN with no data. Previously accepted but expired source identity can be retained as a **historical reference** marked STALE; its data is removed and its timestamp is never renewed. Joint-cut failure conservatively clears both research datasets. There is no stale-response promotion.
- Financial reads require both accounts in the original unified wire schema, original account/epoch bindings, USD/USDC exactly, fresh observations<=5seconds, nonnegative cash/costs, exact gross-minus-costs==net, valid position quantities, null unavailable valuation and reservation-aware cash. Financial arithmetic uses fixed28-digit verification with inexact refusal, independent of ambient precision. Optional monetary fields cannot contain nonfinite or negative trading costs.
- A separately injected evidence owner must return `ATLAS_DASHBOARD_ACCOUNTS_VERIFIED_V1` binding the entire cut, account scope and execution domain. Boolean True, wrong domain, mutation, changed readback or replaced ports refuses. This adapter does not supply current native custody, enrollment, source rights or a cryptographic issuer. OPERATIONAL is only an explicit interface label for future accepted ports; no operational port is created or exercised here.
- Same-revision financial changes and rollback refuse. This in-process high-water is only presentation defense; cold-start authority still belongs to the enrolled read owner. Model construction cannot establish a durable/current financial cut. Independent financial and research reads are rechecked before return; this is not a new globally atomic custody protocol.
- Research and financial channels stay separate. A valid account read need not invent current research; absent financial authority leaves `accounts:null`, cash/positions/P&L unavailable. Account scope is explicit outside the retained wire schema. No USD/USDC conversion or combined cash/equity/return is computed. No balances or deposits are seeded.
- `snapshot_id` is a canonical SHA-256 of the complete model excluding that ID. It is integrity/serialization identity, not authorization. Model timestamps do not grant clock clearance. Failure during final cut checking returns503 UNKNOWN; the browser renderer clears prior values on transport/error/invalid data.

## Read-only controls and browser boundary

This factory receives no financial runtime/dispatcher and exposes **no POST/Stop/start/order route**. All non-GET verbs refuse403 before read callbacks; host/origin/cross-site mismatches refuse403, undeclared query scope refuses404, secret/unlisted routes are not served. Responses are no-store with bounded route/static allowlists, escaping and restrictive same-origin CSP. Framework docs/OpenAPI are disabled.

The read model's Stop and continuation fields are UNAVAILABLE, not synthetic STOPPED/READY/complete evidence. Separately accepted Stop remains the existing `PaperStopBridge` / `register_stop_routes` and personal composition path, with exact runtime/session/retained-owned-close, current action and transport checks. Existing memory/ASGI regressions prove default refusal, separate sealed control composition, foreign/revoked permissions and incomplete-outcome preservation. No new command adapter bypasses those checks.

The new renderer reuses actual `runtime_poll.js`. Node VM checks show no fetch while document or iframe is hidden, no hidden expiry authority, expiry clears old balances, and transport failure removes prior values. Only local view expiry is refreshed; no market observation is renewed. All text is escaped, including untrusted source labels. Existing public `renderUnified` consumes the unchanged account wire shape, with currencies retained.

No actual Chrome navigation, screenshot, browser acknowledgement, listener or installed application was used. DOM/Node/ASGI success is not layout, real browser, READY/image, socket/Job, eight-second Stop or installed restart acceptance. V6's three-reader active-listener/State0 and trusted-browser prerequisites and all consumed grants remain unchanged. No alternative acceptance contract was introduced.

## Exact validation

**770 Python tests passed;0 failed;0 errors;0 skipped;31 modules;55.93 seconds console (JUnit55.885 seconds).**51 new cases, all667 AIP-02 identities (including all396 AIP-01 cases), all52 AIP-03 routing cases. Unchanged older98 continuation/bridge/cut/capacity cases remain retained evidence rather than unnecessarily rerun here.

**42 existing Node selected-dashboard tests passed;0 failed/skipped/cancelled**, plus the existing standalone polling-contract harness passed (separately reported, not counted as another test suite or added to770). The new Node rendering/polling checks are two cases within the51 Python integration cases, not additional browser or test totals.

New coverage: both current research models; deterministic snapshot hashing; accepted separate financial wire/identity; absent source/account authority; stale/future/wrong currency/epoch/revision/missing lane/invalid money/positions/reservation state; current-read conflicts and callback mutation; wrong/boolean proof; ambient Decimal precision; retained source expiry; six original route mappings; existing shell/SOON/static compatibility; default selected-financial unavailability; host/origin/query/verb/secret refusal; repeated GET byte purity; existing renderer interoperability; escaped labels; hidden-frame polling and expired/failed-value clearing. Existing sealed owned Stop/financial replay/risk/partial-fill/funding/continuation source protections pass in the selected regressions.

First focused run retained46 passes/1 failure: a new compatibility test called private `renderAccounts`, which the existing renderer does not export. The test was corrected to use its **unchanged public `renderUnified` API**, not by exporting private code or changing expectations. The next focused50 passed; one added hidden-frame case gives final51. No financial assertion was relaxed. Initial style findings were corrected. No-cache Ruff and formatting passed all three Python files; Node syntax check passed the new script. One preexisting warning remains: Starlette/httpx TestClient deprecation. No dependency installation was attempted.

Private evidence: `logs/diagnostics/aip-04-dashboard-contracts-20261104/{acceptance.xml,acceptance.txt,test-selection.json,source-validation-proof.json,focused.xml,focused.txt,focused2.xml,focused2.txt,existing-selected-frontend.txt,existing-poll-contract.txt}`. Test temporary paths and outputs stay in that diagnostic workspace. Tests use ordinary process permissions, not Windows administrator/service changes. No Windows native publication or retained financial store was needed. Original working-file CRLF formatting is preserved; repository-normalized old assets remain unchanged.

JUnit SHA-256: `6e257d2811c6d55f07b08ade89e07f8aa785e01418c0999c68d1b500fb1b3c9f`.

| Tested new file | Raw SHA-256 |
| --- | --- |
| `backend/app/services/dashboard_read_models.py` | `47d538b70c2c440533b0aec33931bb84ca3b98a965f4a2e2f06b72caab67108f` |
| `scripts/observation_runtime/dashboard_read_contracts.py` | `5c4ab9cc52613b16dba65912c3f62fc82a7168dc7510df56cd89360fa17b294d` |
| `backend/app/static/dashboard_read_contract.js` | `1141ef46b8690f4c3503e8e367fa431f0d309ac142e3a952428c6a7ba2b99b0f` |
| `tests/test_dashboard_read_models.py` | `ce56c0a434dc1872b8965a934ca7a8d88a5caa98cf5f8e270c1544c65cd917c5` |

The unrelated preexisting `tests/test_free_research_pipeline.py` edit remains unchanged at SHA-256 `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb`. Its tests participate unchanged in regression; the file is excluded from this commit. AIP-01/02/03 implementation pins, personal policy and all21 historical decisions are unchanged.

## Completion, remaining prerequisites and next milestone

Completed audited milestones: **4 of18 at source/disposable scope: AIP-01, AIP-02, AIP-03, AIP-04.** No installed/operational acceptance or financial commissioning gate advances. The historical audit and every previous result remain retained.

Remaining installed-dashboard dependencies: exact immutable package/runtime identities containing reviewed integration, separately accepted read capabilities/native custody/account scope, actual Control Center host composition and source origins, real provider-disabled browser rendering, owned Stop/restart/cleanup and V6 original evidence prerequisites. The optional factory and source assets are not installed or connected by this milestone. Existing retained selected-QD capabilities are not self-enrolled as a shortcut.

Missing genuine evidence remains actual permitted/current SEC/Alpaca and HL data, maker-window and historical-funding proof, current source publication/native ACKs, account inception/custody and risk conversion, fresh clock<=1000ms/age<=120s, accepted financial resources, full financial Stop/report/ACK/drain/readback/restart and explicit sole-operator bounded activation/session approval. Fixture cash999.125 is test data, not an operational balance; no actual balances or provider entitlements were read or claimed.

B1/C1/D1/E1 and all21 historical decisions, Genesis isolation and PAPER:NO remain unchanged. Personal sole-operator authority is preserved; no external reviewer committee is added. Future actual installation, financial connection, enrollment/provider access, browser acceptance and PAPER session remain separately scoped and unauthorized here.

**Next canonical milestone: AIP-05-DISCORD-COMMITTED-EVENT-RECOVERY**, isolated lifecycle outbox/consent recovery with fake sender only under its requested source scope. It is not started. Stop after AIP-04 report/roadmap/recovery, validated commit, non-force push and remote SHA verification. No automatic follow-on milestone, installed launch or financial activation.
