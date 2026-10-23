from decimal import Decimal

import pytest
from app.services.paper_partial_accounting import replay_partial_fills


def position(side="LONG"):
    return {"schema": "PAPER_PARTIAL_POSITION_V1", "trade_id": "t", "quantity": "0.5",
            "entry": "100", "risk_price": "2", "fees_bps": "2", "slippage_bps": "1",
            "side": side, "currency": "USD", "opened_at": 100}


def fill(ident="f", quantity="0.25", price="104"):
    return {"schema": "PAPER_PARTIAL_FILL_V1", "trade_id": "t", "fill_id": ident,
            "quantity": quantity, "price": price, "timestamp": 110}


@pytest.mark.parametrize("side,expected", [("LONG", "1.970"), ("SHORT", "-2.030")])
def test_fractional_partial_replay_and_full_close(side, expected):
    first = fill()
    partial = replay_partial_fills(position(side), [first, first])
    assert Decimal(partial["remaining_quantity"]) == Decimal("0.25")
    result = replay_partial_fills(position(side), [first, fill("second")])
    assert Decimal(result["net_currency"]) == Decimal(expected)
    assert Decimal(result["net_r_original_risk"]) == Decimal(expected)
    assert result["complete"] and result["unique_fill_n"] == 2


@pytest.mark.parametrize("damage", ["over", "conflict", "clock", "identity", "nonfinite"])
def test_invalid_partial_refuses(damage):
    first, second = fill(), fill("second")
    if damage == "over":
        second["quantity"] = "0.3"
    elif damage == "conflict":
        second.update(fill_id="f", price="105")
    elif damage == "clock":
        second["timestamp"] = 99
    elif damage == "identity":
        second["trade_id"] = "other"
    else:
        second["price"] = "NaN"
    with pytest.raises(ValueError):
        replay_partial_fills(position(), [first, second])
