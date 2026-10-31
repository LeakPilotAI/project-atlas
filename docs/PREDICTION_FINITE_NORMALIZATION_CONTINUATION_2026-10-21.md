# Finite provider normalization — 2026-10-21

Confirmed malformed public numerical input defects:NaN/sNaN could raise InvalidOperation outside conversion catch;Infinity quantities survived depth normalization;nonfinite market/candle strings were returned instead of missing;zeroquantity top rows hid real deeperliquidity. Corrected _fixed to returnNone for nonfinite Decimal;midpoint/spread/complement helpers explicitly validate finite unitinterval prices;drop depthquantity<=0. No external calls or new subscriptions.

Changed backend/app/prediction/kalshi_public.py andnew tests/test_prediction_finite_normalization.py. Initial test mistakenly named marketquotes instead of prices;original and corrected reproduction retained. Corrected10failed/3passed before sourcecorrection. Final241guardedPython passed8.39s,2inherited warnings,0fail/skip. Added2normalizedprovider->evaluation cases after fullsuite:15focused passed1.71s,1warning(overlap13with241,do notadd counts). Valid finite depth passes;malformedonly depth cannotfill. NewtestRuffPASS;provider2inherited findings unchanged;compilation and diffchecks recorded. No nativebrowser/runtime/provider truth claimed.

All21release decisions/startuplock unchanged;productionNO-GO. No services/providers/Genesis/protectedstate/trading/Discord/Gitoperations or freshruntimecensus. AFI1-10PENDING;sevenphase roadmap retained by verifiedupdater.

Next inspect integrated provider metadata timing and evaluator handling of malformed timing dictionaries/current research clocks. Reproduce failures offline beforeediting. Also continue independent market/AFI functionality rather than repeating oldaudit. Externalprovider rights/PITtruth/nativebrowser/operationalbackuprestore and securityacceptance remainblocked.
