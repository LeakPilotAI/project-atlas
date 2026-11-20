# Atlas — Hyperliquid intrahour native Stop-first supervisor
Date: November 13, 2026
Location: D:\Work\Project Atlas

## What was actually implemented

The existing selected original R21 native Windows installation remains unchanged. This change is SOURCE-ONLY and requires a separately authorized original native financial PAPER session. The earlier pure forward-flat policy guarded the UTC window but could not physically close any simulated position. This implementation adds a real owner-bound, risk-reducing Stop path, while keeping the original historical funding contract and all financial gates in force.

- backend/app/services/hyperliquid_intrahour_stop_supervisor.py: Requires the exact existing PersonalInstalledPaperStopOwner tied to an already RUNNING Stop-first session explicitly scoped HYPERLIQUID only. It reads the already-bound runtime clock, not the Windows wall clock. It refuses entry after the 25-minute pre-funding entry cutoff, reserves a maximum 20-minute hold and a five-minute flat buffer, and sends one SHUTDOWN_FLATTEN through the original Stop owner eight minutes ahead of the next UTC funding hour.
- After Stop, it requires the exact durable original Stop receipt, completed FLAT-and-drained native session, verified owner process exit and a clock readback before the T-minus-five-minute cutoff. A late, missing or uncertain result closes admissions, marks STOP_INCOMPLETE, and never retries. A late-tick still makes the reducing Stop attempt but NEVER treats its result as settlement-avoidance proof.
- backend/app/services/unified_paper_runtime.py: Optional intrahour_supervisor is DEFAULT OFF and must match the exact already-accepted InstalledPythonPaperStopSignal and retained HYPERLIQUID-only native issuer session. While active, both planned and direct ENTRY/RESTING_ORDER calls must satisfy the clock entry window. Existing EXIT and risk-reducing CANCEL_RESTING_ORDER paths remain under their unchanged native custody and original Stop rules.
- backend/app/services/personal_installed_stop_owner.py: Optional intrahour_flat_before_funding=False constructs the supervisor only from an already-approved exact Stop owner; recognizes and independently re-verifies the completed native Stop receipt without sending a second Stop.

This first stage intentionally STOPS the whole supervised PAPER session before each UTC funding boundary; it does NOT automatically restart or already support an uninterrupted waking-hours multi-hour financial PAPER session. Continuing automatically without reauthorization would be unsafe. To meet the eventual all-day Start/Stop objective, a separate native authenticated per-position risk-reducing exit owner and readback/restart policy must be accepted.

## Tests and actual execution

- Standalone native owner/time/one-shot/durable Stop/late/missing/rollback/uncertain proof regression: 17 passing tests.
- Run-loop / real Stop-signal contract integration under explicitly disposable synthetic owners: 8 passing tests, including refusal of direct and resting new entries after the intrahour cutoff, no bypass of cancellation, untouched default behavior and one-shot Stop.
- Broader existing native Stop-first, unified runtime, installed Stop, simulated account/coordination, Quality Dips source, Hyperliquid public data and original strict consensus oracle acceptance tests: 450 PASSED.
- Ruff passes on new files; pre-existing broad-exception/unused noqa behavior on original runtime and owner is excluded from Ruff-only check using BLE001/RUF100 (tests not skipped).
- All new source, tests, docs and temporary files only under main D:\Work\Project Atlas. No native installation, account inception, market order, real capital, VPS, paid feed, auto-start or new desktop shortcut.

## Authentic prerequisites NOT completed

1. Separate Windows-local operator approval for an EXACT current selected-native original Job, two fresh 1,000-unit simulated account manifests, original 5+7 writer identities, original protected financial root file IDs, and independent native NTP. Historical V4 fixture operator authority and absent V5 financial approval are not genuine in-session permissions.
2. Original two preinception coordination journals, separate READ_ONLY+INITIALIZE_SIMULATED_ACCOUNTS activation, once-only two genuine native FS1/FS3 $1,000 USD / 1,000 USDC account readbacks, separate CONNECT_APPROVED_DATA activation.
3. Explicit new forward-only intrahour PAPER method under original financial source licensing/fee controls. The old signed historical settlement-oracle rule is still enforced. Public fundingHistory alone does not prove original consensus settlement price.
4. Actual native source/operation issuer, original Stop-first source receipt, supervised financial Start, durable Stop/flatten/restart and read-only dashboard/Discord delivery.
5. QD current independent originating-firm valuation/approved IEX source/127-publication epoch rollover before QD entries; initial pilot can be HL-only with QD watch.

STATUS: SOURCE-ONLY 450-test regression passing; full two-lane financial PAPER production NO-GO. Never manufacture approvals, historical oracle values, durable financial positions or flat receipts. Keep original R21 selected and live money disabled.
