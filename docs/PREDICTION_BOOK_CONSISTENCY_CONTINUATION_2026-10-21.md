# Executable book consistency — 2026-10-21

Twelve failing synthetic reproductions showed evaluator admitted contradictory quote summaries:crossed bid/ask,negative or arithmetically incorrect spread,best prices different from first executable depth,and out-of-range bid. BothYES/NO tested. Correction requires0<=bid<=ask<=1,spread=ask-bid,and first depth prices agree with summary before eligibility. Existing missingquote/depth refusal and maxspread policy preserved.

Changed backend/app/prediction/paper_engine.py;new tests/test_prediction_book_consistency.py;test_prediction_paper_automation.py shared _book fixture corrected only its bid .50 to .40 (ask .42,spread .02),which previously described a crossed book. Historical candle prices and strategy thresholds unchanged. This is fixture correction,not arbitrary expected-result weakening.

Final guarded compatibility222Python passed7.86s,2inherited warnings,0fail/skip;focused49passed(overlap);1dashboardJS passed(18VM assertions). Newtest Ruff importblankline corrected;engineF/E9passed;full engine26inherited findings unchanged,no new findings. Compilation and diff validation recorded. Reproducer12fail retained.

Scope limits:these are selected-side explicit summary/depth contradictions. This does not establish freshness,external authenticity,complete depth correctness,side-complement consistency,or operational PAPER readiness. simulate_depth_fill still assumes provided level ordering;next reproduce unsorted consumed levels and malformed tail behavior before changing. Do not claim fullbookvalidation from this gate.

All21release decisions/startuplock unchanged;productionNO-GO;nativebrowserNOT_ESTABLISHED. No services/providers/Genesis/protectedstate/trading/Discord/Git mutation or fresh runtime census.

Next:validate executable depth ordering and partial-depth assumptions with deterministic synthetic cases;reproduce before correction. Continue all seven phases:1core operational/provider/backup/resource/lint acceptance;2EvidenceEngine/AFIreplay/accountability;3boundedcryptoPAPERresearch;4crossmarket;5SaaSrights/tenancy/billing;6institutionalsecurity;7commercialscale. AFI1-10PENDING and all external gates unchanged.


## Follow-on depth ordering correction

Actual function name is walk_executable_depth (earlier handoff called it simulate_depth_fill);initial test import mistake preserved in depth-reproducer.txt. Corrected reproduction4failed/2passed:inverted consumedBUYasks orSELLbids produced complete modeled fills with negative slippage silently clamped. Added monotonic consumed-level refusal NON_MONOTONIC_EXECUTABLE_DEPTH;equal prices allowed. Does not claim unconsumed-tail validation or actual partial execution:fillablefalse partial levels remain simulation diagnostics only. No sorting/fabricated prices. New tests/test_prediction_depth_order.py covers bothsides/actions and unchanged sortedVWAP/slippage. Final combined228Python passed8.38s,2inherited warnings,0fail/skip;earlier222overlaps,not additive. NewtestRuff/F/E9/compilation/diffPASS;engine26inherited unchanged. Prior1dashboardJS retained. All21gates/startuplock unchanged;productionNO-GO.

Next inspect public orderbook numerical normalization for nonfinite quantities/prices and zero-liquidity rows. It currently Decimal-compares values after catching only conversion InvalidOperation;reproduce any NaN/Infinity behavior offline before changing. Preserve malformed-input refusal,explicit missingdepth and no provider connections. Continue sevenphaseoffline work;nativebrowser and operational/provider-rights gates remain external.
