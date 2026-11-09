# Atlas premarket native-release delta and two-account Stop qualification — 2026-11-09

**Status: source-only evidence, not a new native release, accepted PAPER Stop or financial activation.**

## Actual selected R12 versus latest workspace review

Selected release `D:\AtlasRuntime\releases\2d4879878bf58bea5a3ed0a986b809791f638fec` was independently verified earlier using its isolated installed interpreter. Its pinned release receipt SHA256 remains `acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6`; its selected revision-12 record SHA256 remains `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`. Both remain untouched.

A read-only receipt-hash comparison of **17 specifically chosen critical paths** (not a whole-release inventory) returned:

- **7 match installed R12**: `backend/app/investment/alpaca_iex.py`, `backend/app/services/quality_dips_publication_reader.py`, `backend/app/services/unified_paper_runtime.py`, `backend/app/services/personal_hyperliquid_public_data.py`, `backend/app/adapters/hyperliquid.py`, `scripts/observation_runtime/personal_paper_inception.py`, `scripts/observation_runtime/unified_paper_commissioning_preflight.py`.
- **6 workspace content-hash differences**: `backend/app/main.py`, `backend/app/prediction/policy.py`, `backend/app/prediction/paper_engine.py`, `backend/app/api/prediction.py`, `scripts/observation_runtime/alpaca_iex_probe.py`, `scripts/observation_runtime/alpaca_iex_watermarked_probe.py`.
- **4 new workspace files not present in selected R12**: `scripts/observation_runtime/atlas_r12_iex_diagnostic_receipt.py`, `scripts/observation_runtime/atlas_r12_iex_rotation_bridge.py`, `scripts/observation_runtime/atlas_premarket_paper_offline_qualification.py`, `scripts/observation_runtime/atlas_r12_financial_readiness.py`.

This subset comparison **does not establish the complete release-delta inventory**, source freeze, full reproducible build, installation authority, or current selected software's incorporation of recent changes. Next version-safe CODE-ONLY release needs a full explicit selection/inventory, source/dependency audit, independently reviewed installed readback, and separate exact approval for any native installation/selection. Never repurpose the consumed one-shot R12 approval.

## Actual disposable Stop/regression checks

Verified a selected offline suite:
- `tests/test_paper_stop_session_route_two_lanes_offline.py`
- `tests/test_personal_native_owned_shutdown_offline.py`
- `tests/test_paper_stop_receipt_ledger.py`
- `tests/test_unified_stop_binding_contract.py`
- `tests/test_paper_gui_owned_stop_signal_lifecycle_offline.py`
- `tests/test_disposable_native_windows_paper_stop_roundtrip.py`
- `tests/test_personal_paper_journal_lifecycle_integration.py`

Result: **122 passed; 1 skipped**. The only skip is `tests/test_paper_stop_receipt_ledger.py:95`, requiring real symlink creation unavailable to this Windows account. It is a real unverified case, **not** a pass or permission waiver. These tests exercised disposable local Windows IPC, SQLite Stop receipts, two-lane simulated shutdown/recovery and journal rules; they did **not** flatten current independently commissioned financial accounts or prove a real desktop shortcut is ready to close actual PAPER positions. Separate AIP-06 native fixtures remain guard-protected and incomplete, not bypassed.

## Outstanding critical path

1. User already authorized one bounded **20-second data-only** Alpaca IEX diagnostic once the regular stock session opens; no credentialed session was run, and no background future execution is scheduled.
2. Independently verified current QD operational source, data rights and true quote freshness; Hyperliquid public book/fee/funding rights and source; continuous independently accepted financial clock and native ownership.
3. Current QD USD and Hyperliquid USDC simulated account inception, proprietary journal/custody and reconciled Stop proof with actual source evidence; leave Kalshi entirely separate until its exclusive new-listing algorithm and data are independently proven.
4. Reviewed/reproducible next source-only candidate and freshly authorized native code release install; manually invoked Start/Stop with native financial source/Stop admission and durable observations; dashboard/Discord, multi-session reliability and months of PAPER profitability assessment before consideration of any live trading.

No private credentials, public provider socket, financial account, simulated/live trade, installed release, Windows shortcut/time/autostart, paid VPS, Genesis or GitHub push was changed in these checks.
