# Bounded request accounting and disposable browser completion — 2026-10-26

## Disposition
VERIFIED source and disposable acceptance only. The earlier ten-directory result remains PARTIAL_ACCEPTANCE_CLOSED_VERIFIED, with its one-run authorization consumed. No retained journals or readiness manifests were read or changed during this work; no retained-history host was restarted. The original six-directory membership remains UNRECONSTRUCTABLE.

## Defect and correction
The historical inline harness checked `count >= 96` before incrementing. Its limit-triggering rejection was never counted. It also needed an extra request to trigger closure. This prevents any retrospective claim of an exact total for that run.

The reusable observation host now has an explicitly opted-in bounded transport. It serializes request handling, charges an accepted connection before parsing HTTP, records the response outcome in a finally block, and closes the listener immediately after the configured last attempt. It does not wait for an N+1 request. Refusals, malformed input and abandoned connections consume budget. At completion, total_attempted = admitted + rejected; pending = 0. Admitted means completed HTTP 2xx/3xx, not financial or operational admission. Failed delivery is rejected. A connection with no HTTP request is conservatively charged. HTTP/1.0 closes connections after one request. Clients trying to connect after closure receive a connection failure, not an uncounted HTTP refusal. Arbitrary client-side TCP attempts outside the listener cannot be bounded or measured by an HTTP server; they are not represented as received requests.

The bounded mode validates 1–96 attempts and a maximum 180-second observation window, binds loopback with Windows exclusive-address use, limits socket read waits, and retains existing unbounded behavior for callers that have not selected a request ceiling. This does not enroll any service or authorize another historical run.

## Browser sequencing and polling
The previous manual browser sequence reached the financial screen after 176.953 seconds and cap closure. Its 53 status polls and hidden workspaces consumed request capacity; this was not evidence that financial HTTP itself needed 180 seconds. The preceding visibility fix is preserved. A single in-flight status read now prevents slow responses from accumulating overlapping polls, while retaining the single timer and hidden-pane refusal.

The synthetic browser driver now performs the final Selected PAPER read within the same automated sequence as valid MSFT research, HTTP503 clearing, refusal-preserving navigation and SPY recovery. It checks the actual rendered financial UNAVAILABLE state, explicit null cash/positions, startup false and a still-live health response before Chrome exits. No accepted financial account or balances are fabricated. The read controller's existing timeout and stale-response protections are unchanged. No production assets, style, financial dispatch or startup paths were redesigned.

## Actual validation
- Final combined Python selection: 41 passed, 0 failed, 0 skipped (9 bounded transport cases plus 32 original observation-host cases), 30.20 seconds. Includes all-refused 96-request ceiling, no boundary request needed, listener refusal after closure, concurrent rejections, malformed/abandoned connections and invalid ceilings.
- Final JavaScript selection: 48 passed, 0 failed, 0 skipped (visibility/poll overlap, research recovery and selected-account frontend). Existing selected-account coverage includes UNKNOWN/INCOMPLETE, stale/missing evidence, no fallback, concurrent reads and late-response refusal.
- Installed Google Chrome headless, original Quality Dips page: 2 final scenarios passed, 0 failed, 0 skipped, five phases each; no captured page runtime errors or legacy mutating research GETs. Desktop actual viewport 1424x905, narrow 784x905; no horizontal overflow. Separate browser windows at two sizes were executed, not physical window dragging or interactive native UI automation.
- Final desktop host: 17 total attempted = 15 admitted + 2 rejected, pending 0; 5.718 seconds including launch/browser/cleanup.
- Final narrow host: 17 total attempted = 15 admitted + 2 rejected, pending 0; 5.485 seconds. Every health, asset, phase-control, polling and financial HTTP request is included.
- Both host PIDs matched the retained child process, native creation time and executable identity. Graceful retained-stdin closure, process exit and released loopback port independently checked after each run. No process-name/port-based termination.
- An earlier synthetic Chrome pair also passed: desktop17/15/2, narrow19/15/4. Counts vary with Chrome's auxiliary requests and are retained, not normalized away. Four synthetic browser hosts in total were started during this task; none used retained history.
- Initial polling-lock implementation failed two JavaScript tests because its finally release was missing. Corrected the implementation; original assertions preserved. That output remains in the execution transcript. No failing financial evidence was replayed.
- Python compilation passed. PAPER static audit:600 source files,0 issues; startup false, no operational acceptance. CR-at-EOL-aware diff checks are used for the existing mixed Windows line endings.

## Local evidence
Final desktop evidence: `logs/diagnostics/qd-research-browser-74a5fecdab664936a0fc80722456527b/`.
Final narrow evidence: `logs/diagnostics/qd-research-browser-99cf1ed777fe4d718df4523fab74a461/`.
Each contains Chrome screenshot, dumped DOM, page result, HTTP response log, closed receipt and bounded-result.json. Synthetic observations use separately created session-test directories and never load retained history. Local browser profiles/logs/session data are excluded from Git. Desktop screenshot was visually inspected; original selected-account styling and explicit unavailable fields are intact.

## Remaining dependencies
This fixes and verifies the two harness gaps in synthetic scope only. It does NOT upgrade the historical partial result, authenticate current market/research sources, attribute the earlier in-app MutationObserver error, grant operational authority or demonstrate financial account operation. Any retained-history rerun requires separate explicit bounded authorization. Current authenticated sources/provider rights, custody and clock dependencies and B1/C1/D1/E1 acceptance remain blocked. No independent acceptance, financial inception, provider connection, Genesis access or protected-account mutation occurred. All21 decisions/seven phases unchanged. Financial PAPER unauthorized; production NO-GO.
