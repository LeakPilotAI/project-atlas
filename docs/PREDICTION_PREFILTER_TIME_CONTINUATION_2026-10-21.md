# Integrated cheap timing refusal — 2026-10-21

Four failing fakeprovider scan reproductions:malformed timingstring/list,naive occurrence,andminimumdate flatwindow overflow. Extracted _research_event_window from accepted evaluator parsing and reused it for scanner cheapfilter and cheapcandidate summaries. Invalidtiming now produces2durable YES/NOrefusal candidates with nulloccurrence/deadline,zero book/candlecalls andno PAPERposition. Legacy journalparser untouched;valid thresholds/budgets unchanged.

Files:backend/app/prediction/paper_engine.py;backend/app/prediction/prediction_paper_automation.py;new tests/test_prediction_prefilter_time.py. Final259guardedPython passed10.03s,2inheritedwarnings,0fail/skip. Original4fail preserved. NewtestRuff passed;modulecomparison,no newfindings;compilation/diffvalidated. Priorresearch-clock UTC alias correction retained. Tests use mockedproviders,temporaryjournals,inmemoryAPI;no server/lifecycle/provideractivation.

21decisions/startuplock unchanged;productionNO-GO;nativebrowserNOT_ESTABLISHED;no freshhealthcensus orprotectedstate/Genesis/trading/Discord/Gitoperations. Sevenphases andAFI1-10PENDING retained.

Next implement user-visible historical evidence diagnostics in existing Prediction research dashboard,if not already surfaced:usable/supplied bars,explicit eventtimeonly versus receiptavailabilityunknown,requestedwindow/context exclusion,and refusal reasons. Reuse current API fields/rendering and tests;do not buildduplicateviewer or imply realdata/productionreadiness. Continue broaderAFI/marketofflinefunctionality afterintegrated presentation;external provider/operational/browsergates stayblocked.
