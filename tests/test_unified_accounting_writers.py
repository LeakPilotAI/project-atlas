"""Accounting is not entry authority. Synthetic custody only in these tests."""
from copy import deepcopy

import pytest
from app.services.paper_portfolio_risk import check_portfolio_accounting_update
from test_unified_paper_runtime import NOW, policy, runtime, with_perp


def cuts(kind):
    before = with_perp()
    after = deepcopy(before)
    after[1].update(revision=1, head="new-native-head")
    row = after[1]["positions"][0]["derivatives"]
    if kind == "FUNDING": row.update(funding_cash="-.2", funding_cut="hour-2", equity="47.76")
    else: row.update(mark_id="mark-2", unrealized_pnl="-48", equity="1.86", maintenance_margin="5")
    return before, after


@pytest.mark.parametrize("kind", ["FUNDING", "MARK"])
def test_adverse_accounting_does_not_need_entry_risk_approval(kind):
    before, after = cuts(kind)
    assert check_portfolio_accounting_update(policy(), before, after, kind=kind, now=NOW)["positions"] == 1


@pytest.mark.parametrize("damage", ["new-position", "quantity", "collateral", "foreign-lane", "rollback", "unknown"])
def test_accounting_cannot_open_resize_rebind_or_clear_unknown(damage):
    before, after = cuts("FUNDING")
    if damage == "new-position": after[1]["positions"].clear()
    elif damage == "quantity": after[1]["positions"][0]["quantity"] = ".002"
    elif damage == "collateral": after[1]["positions"][0]["derivatives"]["collateral"] = "49"
    elif damage == "foreign-lane": after[0]["head"] = "changed"
    elif damage == "rollback": after[1]["revision"] = 0
    else: before[1]["pending_operations"] = ["unknown"]
    with pytest.raises(ValueError): check_portfolio_accounting_update(policy(), before, after, kind="FUNDING", now=NOW)


@pytest.mark.parametrize("kind", ["FUNDING", "MARK"])
def test_runtime_requires_native_accounting_verifier_before_any_writer(kind):
    r = runtime()
    r.portfolio.before, r.portfolio.projected = cuts(kind)
    with pytest.raises(ValueError, match="CANONICAL_ACCOUNTING"):
        r.dispatch("HYPERLIQUID", {"operation_id": kind, "kind": kind})
    assert not r.lanes["HYPERLIQUID"].calls and not r.portfolio.operations


@pytest.mark.parametrize("kind", ["FUNDING", "MARK"])
def test_paused_disconnected_accounting_is_source_verified_reserved_and_idempotent(kind):
    r = runtime()
    r.pause()
    r.portfolio.before, r.portfolio.projected = cuts(kind)
    r.portfolio.verify_accounting = lambda request: True  # Explicit synthetic test authority.
    p = {"operation_id": kind, "kind": kind}
    receipt = r.dispatch("HYPERLIQUID", p)
    assert r.dispatch("HYPERLIQUID", p) == receipt
    assert len(r.lanes["HYPERLIQUID"].calls) == 1
    with pytest.raises(ValueError): r.dispatch("QUALITY_DIPS", p)
