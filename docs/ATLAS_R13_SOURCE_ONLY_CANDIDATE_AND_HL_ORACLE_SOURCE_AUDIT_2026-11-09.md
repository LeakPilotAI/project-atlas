# Atlas R13 source-only candidate and free HyperCore oracle source audit — 2026-11-09

**Disposition: new local review-only source candidate created and independently byte-verified; no installed R13 application, no source grant, no financial PAPER.**

## Why the next action shifted from an oracle-source connector to a source release candidate

The official Hyperliquid information interface supplies hourly rates through `fundingHistory` but not the historical native HyperCore oracle action in force at funding settlement. Official historical raw node sources `hl-mainnet-node-data/explorer_blocks` and `replica_cmds` exist in S3, **but the requester pays transfer**. The Hyper Foundation node service is conditional and best-effort, not a reliable open source for all operators. Source reference: official historical data https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data and foundation node https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/foundation-non-validating-node. No permitted, free, independently verified original HyperCore native oracle-and-funding consensus archive was present in Atlas's existing local custody/diagnostic data. Bitquery native-price/funding index is a **paid** dataset, not permissible under this project's free-only source constraint. A 10-second/one-minute/hourly approximate oracle price is not the exact historical consensus oracle: DO NOT substitute it into financial PAPER.

Rather than add a nonfunctional synthetic source adapter, move a tangible parallel release blocker: current workspace code changes were not in selected native R12.

## Artifact actually created

Existing tracked-source packaging tool: `scripts.build_release_candidate.build_selected`. Source commit:
`c7dfb85665bbcd5ba4494c33365d4dff8ea92b12` (branch `chatgpt/atlas-rebuild-v1`).

A create-only local script in ignored diagnostics `logs/diagnostics/atlas_r13_source_build_20261109_r01.py` created a canonical exact source selection of **952 tracked files** from `backend/app/`, `scripts/`, and `frontend/offline/`; total selected raw bytes **10,791,263**. Only previously committed tracked source files were admitted. The local exact source selection:
`logs/diagnostics/atlas-r13-source-selection-20261109-r01.json`

Inventory (canonical rows) SHA256:
`c070130867636c27ae3ca31f01921a186445e7f4bc8b7ea2e9b14900893680e4`

Create-only artifact directory:
`logs/diagnostics/atlas-r13-source-only-20261109-r01`
containing `atlas-source.zip`, `release-manifest.json` and `archive.sha256`.

ZIP SHA256:
`20167da274294223333ea4668d288514176a675e9308a298786abd0b46b8f39c`

`build_selected` verified source path identity, tracked status, per-file content hash, Windows-safe namespace and exact inventory, then independently verified ZIP. A separate fresh process ran `python -B -m scripts.build_release_candidate --verify ... --expected-sha256 ...`: **verified**. The existing R12 selector file SHA256 remained `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7` throughout.

**This ZIP is source bytes + observed package list, not a reproducibly installed Python application, vetted requirements lock, native Windows ACL/custody package, trusted source signature, publisher authorization or native release selection.** Source verification returned `supplied_bytes_consistent=true`, `source_authenticated=false`, `installation_verified=false`, `activation_approved=false`. It intentionally does not include the full test corpus, generated artifacts, .env credentials, account state or diagnostic sandboxes.

## Cross-feature independent test evidence

A single offline critical-regression run included:
- `test_hyperliquid_consensus_settlement.py`
- `test_hyperliquid_parallel_public_book_reads.py`
- `test_perp_operational_fee_floor.py`
- `test_atlas_qd_native_iex_readonly_pairing.py`
- `test_atlas_qd_scored_research_intake.py`
- `test_alpaca_iex_per_symbol_diagnostics.py`
- `test_kalshi_legacy_autostart_retirement.py`
- `test_paper_stop_session_route_two_lanes_offline.py`
- `test_hyperliquid_source_consistency.py`
- `test_atlas_r12_financial_readiness.py`

Result **138 passed, 0 failed/skipped**, one dependency `discord.player/audioop` deprecation warning. Tests were disposable/offline. No live provider, funded account, simulated financial trading or real order was used.

## Next actual commissioning dependency

1. Review native dependency inventory/lock and build a separately authorized, pinned installed **CODE-ONLY** next runtime; never substitute this source ZIP for an installed verified application. Keep selected native R12 immutable until a new reviewed selection approval.
2. Independently verify admitted free real QD valuation source and current publisher, plus Hyperliquid provider rights, exact price/funding or independently reviewed, versioned conservative **forward-only** PAPER funding policy (not fabricated historical settlement).
3. Accept financial clock/custody, distinct USD and USDC PAPER ledgers, and genuine owned Start/Stop flat-and-log on desktop through supervised operational acceptance. Kalshi remains a separate, uncommissioned new-listing-only YES/NO lane. All nine formal financial operating gates remain **NO-GO, 0/9 accepted**.

No Genesis changes, paid providers, fresh Hyperliquid or Alpaca provider call, Windows boot/clock/shortcuts, passwords/keys or GitHub remote push.
