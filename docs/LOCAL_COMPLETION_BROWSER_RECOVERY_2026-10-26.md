# Local completion checkpoint — research recovery and browser acceptance

Date: 2026-10-26 America/Chicago. Base verified HEAD e58258055d86c8dfa0b723c436c70c94925cfaf2; this already included the prior read-connection milestone. Newer uncommitted hub/Quality Dips changes were preserved and reviewed, not replaced with the older49faf30e checkpoint.

Overall result: PARTIALLY COMPLETE / operational BLOCKED_WAIT. This is an engineering checkpoint, not independent acceptance. No account inception, current provider connection, protected directory access, service installation or financial activation occurred. Genesis, original alien frontend, seven phases, all21 decisions and strict/manual contracts remain unchanged.

## Demonstrated defects repaired
1. Real atlasFetch throws on HTTP503 before a caller can inspect response.ok. The newer QD unavailable branch only handled returned503 objects, making it unreachable through the actual shared transport. Added the HTTP status to the thrown error and handled it in observation mode.
2. On503, original QD research now clears snapshot, selected symbol, candidate/quote/evidence metrics, progress, source health, state legend, pipeline/forward diagnostics and rows. Display navigation cannot turn that refusal into an apparent empty/current account. Later valid research restores the existing components. Ordinary network failure retains only explicitly stale research. Selected financial isolation and its no-research-fallback behavior remain.
3. Original hub health now identifies OBSERVATION HOST ONLINE rather than implying the complete API/scanner is running. Accepted research source/revision/observation timestamp are visible in the QD snapshot card.
4. ATLAS-STOP.bat previously printed success even when Atlas-Stop.ps1 refused. It now exits with failure and explicitly says shutdown was not confirmed. The protected PowerShell refusal is unchanged. This batch feedback path was source-reviewed; no actual operational Stop was executed.
5. Operator guide now identifies the actual Control Center/observation flow, dynamic loopback URL, owned close, missing-source states, financial refusal and obsolete port8000/Docker instructions. Complete former guide bytes retained under an explicit historical/non-current section.

## Tests and retained failures
Final Python selection:237passed,0failed,0skipped (shared frontend transport,read adapters/HTTP,QD autonomous accounting,perp financial accounting,PAPER-only release policy). Final JavaScript selection:60passed,0failed,0skipped (selected financial view,observation recovery,unavailable-state presentation,exit history). They are separate runtimes; no combined total is implied.
Baseline reproduction against e5825805 original QD HTML with unchanged recovery assertions:2failed,1passed. Retained logs/diagnostics/qd-recovery-baseline-failures.txt. Corrected source passed. The diagnostic wrapper initially hit Windows console encoding while printing the already-retained failure output; it did not alter source/test outcomes.
Changed-source Ruff passed; inline JavaScript/Python compilation passed; static PAPER audit599source files0issues,startup_authorized false. Earlier236Python/57JS milestone retained separately; earlier209native financial cases not rerun or counted as new evidence here.

## Actual installed Chrome acceptance
Used installed Google Chrome in headless mode with separate test-owned profiles under D: diagnostics. No user profile or extensions, provider/scanner/financial runtime. Native interactive Chrome control was attempted through the computer-use skill but its approval timed out; no interactive test counted as passed. Headless Chrome is a real rendered browser test, not a DOM mock.
Three scenarios passed:
- Desktop viewport: valid synthetic MSFT publication -> actual503 -> display navigation -> valid synthetic SPY recovery. Prior metrics/symbol clear, restored rows contain only SPY; captured page-error list empty.
- Narrow viewport: same four-stage sequence. Actual viewport784x905;body width769, no horizontal body overflow. HTTP log200,200,503,200;zero legacy mutating QD research GETs;Chrome exit0. Desktop viewport1424x905;body width1409. These are real distinct viewport checks, not physical interactive window dragging.
- Original hub: actual iframe navigation through Perp,Quality Dips,Investment,Archive,Command Center,Prediction. All six correct routes/titles and original component structures mounted. Tables/panels remained present with unavailable or explicitly synthetic evidence. Parent harness failures0. This does not prove absence of every possible child-console error or connected-data chart defect.
Screenshots/results retained privately:
logs/diagnostics/qd-research-browser-026d2ef70dae437abdbfacd37e5606f7/chrome-desktop.png and chrome-desktop-result.json
logs/diagnostics/qd-research-browser-c3bb54a09a424a8c8bb9c778f3970fa6/chrome-800-*-result.json and matching.png
logs/diagnostics/qd-research-browser-ed45334232aa42cda8e702788bdbf350/chrome-hub-result.json and chrome-hub.png
No screenshots/runtime records are published to Git.

Original in-app-browser MutationObserver error did not appear in controlled Chrome QD recovery; no MutationObserver call exists in served Atlas source. Script-free probes from the prior milestone did not reproduce it. Exact originating injected/in-app script remains unattributed because no stack/source URL was available. No error suppression or speculative production patch. Physical interactive window resizing remains NOT EXECUTED; real desktop/narrow Chrome viewport rendering is now VERIFIED.

## Functional readiness and remaining scope
| Area | Evidence-backed disposition |
|---|---|
| Original frontend | Original styling/navigation/components preserved;read failure/recovery verified;not all operational data connected |
| Observation backend | Confined loopback/read adapters and refusal boundaries verified;real source installation not accepted |
| Stocks/ETFs | Existing QD research/scoring code and fixture read/recovery work;accepted current source/clock/publication missing |
| Hyperliquid | Retained three-market capture read verified previously;always historical/non-executable;current accepted live source/fill/funding evidence absent |
| Account/P&L | Separate USD/USDC;canonical accounting tested;no initialized real PAPER balances or accepted financial dashboard |
| Risk/PAPER runtime | Existing disposable engine/native milestones retained;financial operational gates remain blocked |
| Recovery | Research HTTP failure/navigation/recovery verified;prior financial UNKNOWN/no-blind-replay evidence preserved;operational recovery custody unaccepted |
| Windows lifecycle | Original Control Center observation flow documented;three owned test hosts closed and final port released;financial Start/Stop not authorized |
| Trial | Seven-session and30–60-session operational trials NOT STARTED |

## Exact blockers and shortest legitimate next actions
B1: independent acceptance of isolated new-account scope,opening-cash proposal,legacy exclusions and unresolved historical obligations. Proposed1000USD QD and1000simulatedUSDC remain distinct,uninitialized accounts.
C1: independently accepted actual writer/resource/process roster,exclusive admission,full drain and owned lifecycle;fixture ownership alone is insufficient.
D1: accepted profile-scoped issuer/session authorization,current/high-water custody,clock continuity,resource identity and recovery disposition. Same-user/D:-only risks are acknowledged but do not self-accept strict gates. No credential or custody installation performed.
E1: provider-specific rights and bounded current source authorization,accepted instrument/session/corporate-action evidence,executable-price/fill/funding producers and supervised release acceptance. Credentials or retained quotes are not permission/current evidence.
Next real-data step: supply/install only a separately accepted nonmutating current QD publication authority/source/clock and accepted provider observation scope. The existing read port already refuses without them. No need to build another accounting engine or generic bridge.
Next financial step: independently review gates/profile,then explicitly authorize bounded dependency enrollment and once-only inception/native writer installation,then read-only acceptance and a separately authorized supervised trial. No gate promotion in this task.
An automatic approval review in the preceding read-connection work rejected non-disposable observation-host startup due to real session-root access/creation. Only session-test hosts were used here. Real retained-history host acceptance remains unexecuted unless separately approved with a bounded nonfinancial scope.

## Reproduction and cleanup
For each Chrome sequence use a FRESH confined host: backend\.venv\Scripts\python.exe tests/qd_research_recovery_host.py. It prints the new test root and URL. In another terminal run backend\.venv\Scripts\python.exe tests/run_qd_research_chrome.py <printed-test-root> --width 1440 (or --width 800 with a fresh host). Stop only that retained host by closing its stdin/pressing Enter in its owning console. Test-only phase routes exist only in this test helper, not the operational host.
Three test hosts closed successfully;port60791 released;Chrome commands exited0.616owned diagnostic/profile files retained,39,325,390bytes;0files deleted/0bytes recovered. Profiles are disposable future cleanup candidates, but screenshots/results/failure evidence must be retained. No unknown/untracked/financial data deleted.

Current supported operator instructions: docs/ATLAS_OPERATOR_GUIDE.md. Canonical roadmap remains PROJECT_ATLAS_MASTER_ROADMAP.txt; no competing master roadmap. PAPER startup NO. Production NO-GO.
