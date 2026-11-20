# Atlas r12 IEX 30-slot research rotation plan — 2026-11-09

**Source milestone verified. Not an installed-native release update, provider subscription or financial PAPER acceptance. Full PAPER NO-GO, 0/9 accepted operating workstreams.**

## Implementation

- New read-only `scripts/observation_runtime/atlas_r12_iex_rotation_plan.py` uses the genuine local Alpaca research catalog (13,487 provider-listed U.S. equity research symbols). Its schema, research-only permissions, ordered unique symbols and canonical content SHA must match. A mismatched/symlinked/corrupt/over-limit catalog is refused.
- A bounded roster contains **at most 30** symbols, matching the free Alpaca IEX equity WebSocket plan's concurrency budget used by Atlas. Up to 10 explicitly supplied symbols can be reserved first; remaining slots visit the other research catalog symbols sequentially. The planner does **not** certify that its supplied monitored symbols belong to a financial account—it requires a separately authenticated owner before runtime use.
- Corrected a genuine test-discovered coverage bug: initial implementation wrapped at the end of the catalog and repeated symbols inside a pass. The final implementation emits a short final roster, completes the cycle without repeats, then starts a new pass at the next cursor. It never changes the persistent financial/research cursor or contacts providers.
- A 13,487-symbol catalog needs **450 nonoverlapping rosters** with no reserved symbols. Reserving MSFT would leave 29 rotating slots and need approximately 466 rosters per full cycle. This is a *scheduling-capacity illustration*, not proof a free 30-symbol real-time connection can supply current executable quotes for the complete universe. Connection churn/rate limits, market hours, provider entitlement, price freshness and account custody still require separate validation.
- Output explicitly sets `authenticated_iex_connection=false`, `fresh_quote_delivery_verified=false`, `provider_rights_accepted=false`, `robinhood_brokerage_coverage_verified=false`, `financial_paper_accounts_authorized=false`, `paper_execution_authorized=false`, `startup_authorized=false`. It returns deliberate no-go exit 2.

## Verified tests and boundaries

- Added `tests/test_atlas_r12_iex_rotation_plan.py`: actual catalog capacity; complete-cycle no duplicate/revisit; reserved-symbol retention and rotated symbol fairness; invalid cursors, forged eligibility flags, extra or invalid pinned symbols and altered catalog digest refusals; no-provider CLI inspection.
- Combined IEX source/asset catalog/probe tests **81 passed, 0 failed**. First regression exposed an undefined constant; next exposed wrap-around duplicates; both fixed and full run repeated successfully.
- Selected installed native release remains r12 at `D:\AtlasRuntime\selection\r0012.json`, unchanged. Source-only development files are not installed into that sealed application. No socket, private API credential, PAPER account/ledger, publisher enrollment, simulated or live order, Project Genesis change, Windows Time alteration, desktop shortcut rewrite, paid VPS or GitHub push.

**Next operational dependency:** a separately authorized authenticated, bounded **data-only IEX quote session during U.S. market hours**, followed by operator-owned current forward scanner publication with native issuer/ACK and independent financial time and data rights. The new roster planner can be integrated into an accepted research/observation collector only after those external inputs exist.
