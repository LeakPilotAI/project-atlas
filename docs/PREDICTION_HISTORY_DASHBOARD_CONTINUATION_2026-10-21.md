# Historical evidence dashboard — 2026-10-21

Implemented existing Prediction PAPER dashboard selected-evidence summary using existing APIhistory fields. Shows usable/supplied counts,excluded context,explicit requestedUTCwindow,and eventtimechecked/refused/unknown. Always distinguishes eventtimeorder from freshness and states receipt/publication availability is not established by this view. Legacy missingevidence remainsUnknown;boolean/noninteger counts are not coerced. Arbitrary statuses are not echoed;summary uses textContent alongside existing escapedtable and textContentJSON.

Selecting candidate updates summary;successfulrefresh clears oldselecteddetail and summary so priorselection cannot remain presented as current. Failedrefresh clears history with otherexistingstatedata. No eligibility/API/authority/threshold changes.

Files:backend/app/static/prediction_paper.html;new tests/test_prediction_history_dashboard.cjs. Initial5newtests failedbeforeimplementation. Firstcombinedrun exposed editor defaultcp1252 decoding changed emdash bytes;correctedUTF8,originalfailure preserved. Final6Node tests passed100.5039ms,0fail/skip,including existing18accountingassertions and5newhistory/unknown/refusal/refreshcases. VM/fakeDOM only,notnativebrowserlayout/accessibility/CSPacceptance. Sourceunicodechecked;diffcheckPASS. Prior259guardedPython results retained,notrerun forHTMLonlychange.

All21gates/startuplock unchanged;productionNO-GO;nativebrowserNOT_ESTABLISHED. No services/providers/Genesis/protectedstate/trading/Discord/Git operations,freshruntimecensus orsourceauthenticityclaim.

Next add provider-shaped evaluator-to-dashboard handoff fixture testing using actual isolated evaluator output:valid/refused historywindow,missinglegacy andeventtimeavailability limitations. Reuse existing dashboard;avoid duplicateviewer. Then continueAFI/marketofflineintegration;sevenphases andAFI1-10PENDING/externalgates retained.
