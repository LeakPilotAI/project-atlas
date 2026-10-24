# Quality Dips selected-account policy V1 — corrected multi-instrument scope

## Authorization and decision

The October 24 operator correction supersedes the **MSFT-only proposal**, including the current-scope interpretation of the historical B1 V1/V2 proposals and FS123 handoff. Those original artifacts are retained unchanged. MSFT is a synthetic example, never a financial allowlist. This is authorized offline policy engineering, not independent B1 acceptance or operational authority.

B1/C1/D1/E1 remain BLOCKED. All 21 decisions unchanged. PAPER startup NO; production NO-GO. No providers, native protected tests, operational routing, financial sources, startup, or Genesis were accessed.

## Implemented contract

- `PAPER_EPOCH_SELECTED_QD_V2` binds `QD_SELECTED_ACCOUNT_POLICY_V1` at inception. Exactly $1,000 hypothetical opening cash; maximum $100 per entry; one open position; no scale-in; long-only; manual confirmation for entry and partial/full exit. Fractions require explicit supported execution evidence. Existing 2bps fees plus 2bps slippage per side remain synthetic assumptions, calculated under the retained entry-notional roundtrip model. No authenticated cost claim.
- Instrument mappings accept explicitly supplied STOCK and ETF identities and execution facts, regardless of ticker. No symbol is hardcoded in policy. Unsupported or unverified instruments refuse. All eligible instruments may be supplied subject to the bounded contract capacity; this is not evidence that every instrument currently has a supported execution adapter.
- `PAPER_COMMAND_SELECTED_QD_V2` carries instrument binding plus, for entries, a frozen ranking receipt. The wrapper binds the existing Quality Dips V3 strategy/policy/classification/observation/ladder concepts to explicit source, rank revision and instrument identity. Existing research rankings and forward observations are not modified or re-ranked.
- Frozen ranking receipts are pinned by digest in the explicit disposable inception contract. Ranking freshness is explicitly configured, capped at 600 seconds in this offline version; quotes retain the existing 30-second boundary. These durations are engineering bounds, not accepted operational feed freshness policy. A digest, `manual=True`, local timestamps, or caller-created mappings establish no independent authority.
- Rank/order is explanatory selection evidence, not permission to execute. No automatic action follows rank. Stable observation+ladder identity prevents a changed rank or operation ID from creating another financial effect for the same signal. Existing operation retry IDs remain idempotent in the fixture store.
- Canonical `apply_event` validates selected policy/evidence before applying financial changes. Both fixture and native FS2 publishers call this function before financial intent/event publication. Native ordering was checked statically only; no new native acceptance is claimed. Exact Decimal product comparison refuses values just above the $100 boundary even when 28-digit arithmetic would round them down.
- `PAPER_RECEIPT_SELECTED_QD_V2` binds the full original command digest, immutable policy digest and reason codes. Legacy V1 receipt/event/state/report formats and historical goldens remain unchanged. Independent arithmetic audit verifies new event cash, quantities, costs and realized P&L without replacing the canonical engine.
- Held positions can remain overnight and exit without a fresh ranking. Exits still require pinned instrument/source identity, fresh price, exact position/source revisions and manual consent. A falling rank never forces liquidation. Rejection reason codes support future operator explanations; no dashboard or endpoint was connected.

## Evidence and validation

Final single combined run: **133 passed, 0 failed, 0 skipped**, 4.91 seconds. This is 33 new policy cases plus 100 existing disjoint compatibility cases, not cumulative totals across retries.

Selection: `test_quality_dips_selected_policy.py`, `test_fs1_financial_replay.py`, `test_paper_epoch_fixture.py`, `test_paper_strategy_fixture.py`, `test_q7_paper_portfolio.py`.

Cases cover MSFT/AAPL stocks and SPY/QQQ ETFs, a sequential stock-to-ETF account, partial/full exits, overnight holds, replay/restart, independent arithmetic, unsupported and unverified instruments, fractional support, stale/future ranks, stale prices, changed ranking order, duplicate signals, manual refusal, source/identity substitution, one-position/no-scale-in, insufficient cash, exact rounding limits, schema/digest pins and policy expansion refusal. Fixtures are explicitly synthetic and prove no real market eligibility or fills.

Original failure: new source-order test referenced the wrong module path (24 passed, 1 failed in focused reproduction). Corrected to the actual `scripts/volume_inspector/financial_record_store.py`; original diagnostics retained locally. Initial combined sandbox run stalled and was interrupted; no complete result claimed. Final offline selection ran in the permitted host context with disposable stores, unchanged assertions. Earlier 125-pass intermediate run is not added to the final count.

Targeted Ruff, in-memory Python compilation, checkpoint-updater PowerShell parsing and diff whitespace checks are required before publication. No native filesystem/security cases were executed in this milestone. Retained FS2/FS3 native limitations, including true-symlink NOT EXECUTED, are unchanged.

## Remaining integration and authority boundaries

The frozen ranking wrapper and explicit instrument registry are offline contracts. Production needs independently accepted instrument identity/execution support, authenticated current ranking/source revisions, provider rights, fresh quotes, trusted clock and current-pin custody. No adapter currently authenticates those facts into this selected-account contract. The bounded inception pins are immutable; runtime refresh/enrollment of new ranking receipts needs a separately reviewed current-authority protocol, not editing accepted inception or relaxing receipt pins.

V1 remains readable for compatibility and is not promoted into a selected-account startup path. Choosing a legacy manifest does not grant operational admission. Native all-writer exclusion, protected financial storage, trusted issuer, rollback/recovery and opening-account acceptance remain separate gates. The new version is usable only through explicitly supplied offline contracts; no protected writer, dispatch or launcher was changed.

Next exact action: independent review of the corrected all-eligible-stock/ETF B1 scope and explicit ranking/instrument freshness policy, then separately scoped authorization for the actual evidence adapter and selected native writer integration. Do not restore MSFT-only policy or repeat FS1–FS3. No startup permission results from this implementation.

## Seven-phase status

1. Core reliability and Windows PAPER operations: incomplete; selected policy is offline verified only.
2. Evidence Engine/AFI: HOLD; AFI-1 through AFI-10 remain PENDING, zero accepted.
3. Historical/prediction expansion: BLOCKED; optional 15-minute crypto remains deferred.
4. Cross-Market Intelligence: pending.
5. SaaS expansion: pending/deferred.
6. Institutional controls: pending.
7. Commercial readiness: pending.

All original phase definitions and release decisions remain authoritative; this report does not redefine the roadmap.
