# Atlas Hyperliquid operational PAPER fee-cost admission — 2026-11-09

**Outcome: SOURCE-ONLY financial-cost safeguard implemented; 97 eligible offline tests passed. No financial activation, installed runtime modification, provider request or real trade.**

## Actual cost defect and source

The legacy unapproved Hyperliquid enrollment draft `docs/ATLAS_TWO_ACCOUNT_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json` retains `maker_bps=1`, `taker_bps=2`, and `fee_schedule_id=PENDING_E1_VERIFIED_FEE_SCHEDULE`. Those are explicit **unaccepted placeholders**. The existing financial transition had only required nonnegative fees and matching a declared schedule string; that could allow underpriced costs in a future `PAPER_EPOCH_PERP_OPERATIONAL_V1` simulation.

Hyperliquid's official public [fee schedule](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), inspected November 9, 2026, lists **standard perpetuals base tier 0.015% maker (1.5 bps), 0.045% taker (4.5 bps)**. This is a conservative, **undiscounted modeling policy** for the configured BTC/ETH/SOL validator-operated perpetuals, **not evidence of the user's actual volume/staking/referral discounts, maker rebates or an accepted account entitlement**. A different verified lower-rate model would need explicit new versioned evidence/admission, not weakening this default silently.

For a $100 entry and $100 exit, taker fees are **$0.09 at 4.5 bps** versus **$0.04 at the legacy 2 bps**—a $0.05 understatement under the old policy before slippage/spread/funding.

## Exact change and compatibility boundary

- In `backend/app/services/paper_perp_transition.py`, introduced `require_operational_fee_policy(m)` and invoke it at the **first statement of `transition(m,s,c)`**, before the candidate simulated state is changed. If and only if `schema=PAPER_EPOCH_PERP_OPERATIONAL_V1`, the fee schedule may not begin with `PENDING_`, and its explicit maker/taker bps may not be below 1.5/4.5. A larger explicit modeled fee is preserved, not automatically decreased. **This does not authenticate an arbitrary fee_schedule_id**; the separate existing source/issuer/financial authority gates are still required.
- **No fee floors were added to the historical `PAPER_EPOCH_PERP_FIXTURE_V2` schema**. Historical immutable simulated events, reports and expected outputs retain their original 1/2-bps values.
- Earlier initial implementation enforced the guard within `validate_manifest`, which exposed a real compatibility problem: older *unapproved* V4/V5 draft enrollment documents needed to remain structurally inspectable. That approach was corrected. `validate_manifest` retains historical structural meaning, while `transition` refuses underpriced **financial commands** before a simulated state effect.
- `tests/test_perp_operational_fee_floor.py` tests initial permitted conservative policy, arbitrary old pending schedule refusal, too-low maker or taker rates and other false discounts, higher cost assumptions, exact old fixture preservation, full net arithmetic, and in-memory synthetic entry → partial exit → hourly funding → final exit. For an illustrative existing test path, corrected final cash is `1001.50396` USDC instead of `1001.52936` USDC when using the 4.5-bps taker model, with the same explicit simulated mark, quantity, funding and slippage assumptions.
- Updated synthetic **native operational** fixture policy in `tests/test_operational_perp_store.py` and the disposable publisher in `tests/test_personal_paper_inception_memory.py` to use 1.5/4.5 and the shared explicitly **REVIEW_ONLY** fee schedule ID; its entry/exit evidence uses the same ID and the historical test cash expectation is recalculated. Native operational fixture integration remains **not yet executed** because that guarded Windows test matrix requires its separate approved native test-session/root prerequisites. Its contract was not bypassed.

## Actual verification

Combined source-only cost, independent audit, funding recovery, margin tiers, in-memory once-only inception and historical V4/V5 draft preservation: **97 passed, zero failed/skipped**. Pure synthetic in-memory transition confirms the full partial-exit/funding/final-exit result under the modeled higher taker rates. No broker or Hyperliquid client invoked. Native code-selected R12 and its installed source are unchanged.

## Unfinished operational acceptance

Fee modeling does not independently verify account tier or source rights. Public marks/order books and hourly rate history do **not** prove historical settlement-time oracle, complete cash funding, stable executable maker queue, per-venue maker rebates, user discounts, real entitlement, or financially qualified source/clock/native USDC custody. Original QD issuer and source acceptance also remain open. All nine formal financial operating workstreams remain **0/9 accepted: NO-GO**. No actual PAPER account opening, financial order, live trading, native selection/shortcut/Windows change, Genesis edit or GitHub push occurred.
