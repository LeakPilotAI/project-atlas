"""A simulated partial IOC fill cancels its remainder in the same event/receipt."""
from decimal import Decimal

import pytest
from app.services.paper_epoch_fixture import create_epoch_fixture
from test_perp_financial_v2 import audit, entry, exit_command, manifest


def ioc(side="LONG"):
    c = entry(side=side)
    c["schema"] = "PAPER_PERP_IOC_ENTRY_V1"
    c["quantity"] = "0.1"
    c["evidence"].update(bid_size="1", ask_size="1", ioc={"schema": "PAPER_IOC_CANCEL_REMAINDER_V1",
        "order_id": c["origin_ref"], "requested_quantity": "0.5", "filled_quantity": "0.1",
        "cancelled_quantity": "0.4", "quantity_step": "0.001"})
    return c


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_partial_entry_and_final_exit_have_no_hidden_order_remainder(side, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = ioc(side)
    first = st.execute(c)
    assert st.execute(c) == first
    p = st.snapshot()["positions"][first["position_id"]]
    assert Decimal(p["remaining"]) == Decimal("0.1") and p["ioc"]["cancelled_quantity"] == "0.4"
    st.execute(exit_command(st, qty="0.1"))
    assert Decimal(st.snapshot()["positions"][first["position_id"]]["remaining"]) == 0
    audit(st)


@pytest.mark.parametrize("damage", ["zero-liquidity", "step", "overfill", "uncancelled", "oversized-request", "order-id"])
def test_invalid_partial_fill_or_remainder_never_publishes(damage, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = ioc()
    if damage == "zero-liquidity": c["evidence"]["ask_size"] = "0.0001"
    elif damage == "step": c["evidence"]["ioc"]["quantity_step"] = "0.003"
    elif damage == "overfill": c["quantity"] = "0.2"
    elif damage == "uncancelled": c["evidence"]["ioc"]["cancelled_quantity"] = "0"
    elif damage == "oversized-request": c["evidence"]["ioc"]["requested_quantity"] = "100"
    else: c["evidence"]["ioc"]["order_id"] = "foreign"
    with pytest.raises(ValueError): st.execute(c)
    assert st.snapshot()["revision"] == 0
