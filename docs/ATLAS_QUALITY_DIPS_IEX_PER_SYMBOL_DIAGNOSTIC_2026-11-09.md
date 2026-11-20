# Atlas per-symbol IEX diagnostics for Quality Dips — 2026-11-09

**Status: development-source improvement VERIFIED OFFLINE; no additional provider connection and no financial PAPER authority.**

## Why this was necessary

The user's expressly authorized **single 20-second Alpaca IEX data-only test on November 9** authenticated and subscribed to MSFT and SPY, with at least one accepted fresh SPY quote callback. It recorded 5,108 accepted/processed quote events and 2,041 fresh callbacks, but **did not establish whether MSFT emitted no quote messages or emitted messages that our strict `IEXFeed._quote` validator rejected**. The previous probe only returned aggregate accepted events and the set of symbols with callbacks. Do not infer a particular MSFT rejection reason, missing exchange coverage or any broker entitlement from the incomplete first sample.

## Implemented source-only improvement

- `backend/app/investment/alpaca_iex.py` now tracks bounded **per-symbol counts** of incoming `T=q` frames for explicitly requested symbols, validation-accepted frames, validator-rejected frames, and fresh callback deliveries during a bounded `IEXFeed.run`. Counters are confined to the feed's existing lock and report **per-run deltas**, rather than pretending all previous feed sessions were part of the sample. Roster rotation initializes new symbol counters and still invalidates cached quotes before reauthentication/subscription.
- `scripts/observation_runtime/alpaca_iex_probe.py` optionally admits a complete, validated `per_symbol_quote_diagnostics` map: exactly the requested symbols and four integer counts per symbol. Every count must be nonnegative/nonboolean, received=accepted+rejected, callbacks<=accepted, callbacks must match the observed symbol set, total callbacks match the independently counted callback events, accepted counts cannot exceed the feed's processed quote count. No per-symbol raw bid/ask/size/timestamp, rejected raw frame, account, or credential is emitted. Missing telemetry from historical or mocked feed types stays **UNKNOWN**, not a fabricated all-zero report.
- `scripts/observation_runtime/atlas_r12_iex_diagnostic_receipt.py` can record and independently read back the canonical per-symbol aggregate telemetry in the **existing sanitized create-once diagnostic receipt**. Tampering, noncanonical ordering, fabricated coverage or nonfinancial scope promotion are rejected. Existing historical receipts without telemetry remain valid and untouched; the actual November 9 SPY-only receipt operation ID `14cd7c6f05ff438390197099d82da615` was independently read back, still report-only.
- New `tests/test_alpaca_iex_per_symbol_diagnostics.py`: mocked WebSocket examples distinguish a requested MSFT quote that fails the unchanged condition gate from a missing MSFT frame, while SPY has an accepted callback; receipt write/read, no raw keys/prices, forged metrics refusal, previous receipt schema compatibility. These are simulated examples only; **they do NOT establish what actually happened to MSFT**.

## Actual verification and limits

- Initial focused IEX source, CLI, diagnostic receipt and old probe suites: **107 tests passed, zero failures**.
- Expanded first run while workspace source changes were uncommitted: **137 passed / 1 failed**, specifically `test_atlas_r12_financial_readiness.py::test_actual_r12_audit_process_refuses_start_and_reports_nine_gates`, because it asserts `qd_source_clean is True` and tracked source was intentionally dirty at that stage. This was **not** an independent quote-validation failure. Preserve its unchanged strict clean-source assertion. Rerun once committed, and report actual result.
- The new per-symbol telemetry **cannot be reconstructed retroactively** from the prior SPY-only aggregate diagnostic. A new one-time separately approved *data-only* sample, if warranted, would be required to observe MSFT's actual per-symbol counts. Do not automatically re-use the prior consent.
- IEX is a single venue, not SIP/NBBO. Valid short quotes do not prove complete symbol availability, accepted provider rights, continuous financial-grade clock, durable current QD issuer, executable fills, account inception, safe PAPER Stop, or startup authority. No permissions have been relaxed.

No Project Genesis changes, real broker orders, funding/account access, PAPER financial events, secrets exposure, Windows Time/boot/shortcuts, native selected R12 modification, release install, or remote GitHub push.

## Final post-commit verified outcome

At source commit `d09b57fe`, the combined **seven-suite** IEX/receipt/financial-readiness/rotation regression was re-executed with a clean tracked tree: **138 passed, zero failures or skips**. The previously dirty-source-only failure did not recur and no readiness assertion was relaxed. The selected native R12 remains unchanged; no additional Alpaca credentialed session ran. This outcome supersedes the intermediate uncommitted 137-pass/1-fail diagnostic above, without rewriting its history.
