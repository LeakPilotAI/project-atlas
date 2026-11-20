"""Disposable legacy rows cannot hide a position through conflicting close evidence."""
from copy import deepcopy

import pytest
from app.services.daily_paper_fixture_adapter import adapt_legacy_rows
from test_daily_paper_fixture_adapter import row


def completed(original):
    return {**original, "event": "close", "status": "closed", "result": "WIN",
            "exit_reason": "FIXTURE", "exit_timestamp": "2026-10-23T20:00:00+00:00",
            "actual_exit_price": "104", "gross_pnl_r": "2", "net_pnl_r": "1.9"}


@pytest.mark.parametrize("field,value", [
    ("symbol", "OTHER"), ("side", "SHORT"), ("trade_type", "LIVE"),
    ("position_size", "9"), ("actual_entry_price", "99"),
    ("risk_price", "3"), ("fees_bps", "4"), ("slippage_bps", "5"),
])
def test_contradictory_close_cannot_erase_original(field, value):
    original = row()
    close = completed(original)
    close[field] = value
    retained = deepcopy([original, close])
    with pytest.raises(ValueError):
        adapt_legacy_rows([original, close], currency="USD")
    assert [original, close] == retained


def test_nonpaper_original_cannot_disappear_via_completed_close():
    original = {**row(), "trade_type": "LIVE"}
    with pytest.raises(ValueError):
        adapt_legacy_rows([original, completed(original)], currency="USD")


def test_compatible_close_and_duplicate_retained_rows():
    original = row()
    close = completed(original)
    assert adapt_legacy_rows([original, original, close, close], currency="USD") == []


@pytest.mark.parametrize("field", ["symbol", "side", "trade_type", "position_size", "actual_entry_price"])
def test_unbound_close_missing_source_fields_refuses(field):
    original = row()
    close = completed(original)
    close.pop(field)
    with pytest.raises(ValueError):
        adapt_legacy_rows([original, close], currency="USD")


@pytest.mark.parametrize("change", ["entry-clock", "reversed"])
def test_close_cannot_replace_entry_clock_or_precede_entry(change):
    original = {**row(), "entry_timestamp": "2026-10-23T13:30:00+00:00"}
    close = completed(original)
    if change == "entry-clock":
        close["entry_timestamp"] = "2026-10-23T13:31:00+00:00"
    else:
        close["exit_timestamp"] = "2026-10-23T13:29:00+00:00"
    with pytest.raises(ValueError):
        adapt_legacy_rows([original, close], currency="USD")
