# Retained research microseconds continuation — October20,2026

## Working correction

parseRetainedResearch now uses the existing bounded microsecond timestamp helper for report/reference/bar times and exact180s bar-start freshness/completed-minute rules. Exchange-local day extraction explicitly converts microseconds back to Date milliseconds; previous-session-date and percentage semantics are unchanged. Other parser code is byte-preserved. Source schemas, stored records and immutable fixtures unchanged.

Original21 Node tests had4 failures/17 passes: future reference within1ms,1us-over-TTL, sub-minute-misaligned bar and unsafe epoch precision. All21 corrected tests pass, including legitimate fractional clocks, exact available-at equality, freshness/completion boundaries and all unavailable/refusal statuses.

22 new Python integration cases use public normalization → SQLite reopen → actual retained_research API → actual Node parser across premarket, regular, after-hours, UTC-midnight local-date boundary, post-DST open and early-close dates. Known reference exactly at decision asof is accepted; reference1us later is REFUSED without metrics; exact180s is descriptive and180s+1us REFUSED. A not-yet-received/completed later bar cannot enter research. Before/after stored rows remain unchanged. No real data/provider connection or service.

## Exact validation

Full expanded guarded market/replay/research suite650 passed in45.84s, zero failures/skips. This is a joint current run including the prior23-case quote session extension and22 new research cases; prior614/23 overlap counts are not added. Full offline Node426 passed (prior405 +21), zero failures/skips/cancellations. Configured frontend ESLint, targeted Ruff, Node syntax, Python compilation and Git diff pass. Separate prior604 AFI evidence remains preserved, not mislabeled as650 AFI. Existing3 builder lint findings unchanged/no waiver. Original current red log intact; historical overwritten diagnostic limitation remains disclosed with preserved source/terminal/reproduction evidence in DUPLICATE_ACK_CONTINUATION.

## Safety and admission

All21 decisions/startup denial unchanged; production NO-GO. Seven-phase strategy, AFI1–10 PENDING, Gaming objective, Atlas/Genesis separation, E136 consent/recovery and Prediction Market Intelligence V2 safeguards retained. No providers/services/Atlas/Docker/Genesis, trading/PAPER/Discord activation, protected state/configuration/ACL/shortcut/volume, backups/restoration or Git operations. No fresh runtime census. Offline fixture paths work; full Atlas/live feeds require selected-provider rights/entitlements/coverage/storage/display, wire timing/budget acceptance and approved observation-only fixed-release admission/lifecycle. Client consistency is not source authentication, calibrated forecasting or complete calendar authority.

## Exact continuation

Latest result/pins under logs/diagnostics/research-microseconds-20261020; approved updater verifies backup/read-back/outside-managed bytes. Full native Goal preserved, no duplicate/reset/completion/blocked claim or external unattended mechanism. Continue authorized offline work.

Next selected task: descriptive replay/comparison clock ordering. validateResearchReplay and verifyResearchComparison still use millisecond timestamp() for archive cutoff and decision order. Reproduce valid decisions1us apart being rejected and a decision1us beyond archive cutoff being accepted, with correctly rehashed synthetic envelopes and no source-authentication claim. Reuse bounded microseconds only for ordering/cutoff (no arithmetic units elsewhere), preserve exact nested report clocks, all refusal denominators/decision identities and immutable fixtures. Add actual Python replay/export→Node verification for fractional ordered plans where feasible. Do not alter other parser bodies without tests; no production/provider/service/Git operations. Use exclusive fresh evidence paths, then continue other feasible roadmap work.
