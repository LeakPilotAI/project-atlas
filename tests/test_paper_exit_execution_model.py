from app.services.paper_execution_model import conservative_stop_exit, conservative_target_exit


def test_long_gap_stop_uses_worse_mark_and_slippage():
    out=conservative_stop_exit(side="LONG", mark=94.0, stop_price=95.0, slippage_bps=2.0)
    assert out < 94.0


def test_short_gap_stop_uses_worse_mark_and_slippage():
    out=conservative_stop_exit(side="SHORT", mark=106.0, stop_price=105.0, slippage_bps=2.0)
    assert out > 106.0


def test_long_target_caps_at_target_then_slips():
    out=conservative_target_exit(side="LONG", mark=106.0, target_price=105.0, slippage_bps=2.0)
    assert out < 105.0


def test_short_target_caps_at_target_then_slips():
    out=conservative_target_exit(side="SHORT", mark=94.0, target_price=95.0, slippage_bps=2.0)
    assert out > 95.0
