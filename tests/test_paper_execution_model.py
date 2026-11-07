from app.services.paper_execution_model import execution_assumptions, touched_with_buffer


def test_conservative_limit_touch_requires_buffer():
    assert touched_with_buffer(side="LONG", mark=99.0, limit_price=99.0) is False
    assert touched_with_buffer(side="LONG", mark=98.98, limit_price=99.0) is True
    assert touched_with_buffer(side="SHORT", mark=101.0, limit_price=101.0) is False
    assert touched_with_buffer(side="SHORT", mark=101.02, limit_price=101.0) is True


def test_execution_assumptions_remain_paper_only():
    out=execution_assumptions()
    assert out["conservative"] is True
    assert out["fill_model"] == "LIMIT_TOUCH_PLUS_BUFFER"
    assert out["automatic_real_money_execution"] is False


from app.services.paper_execution_model import conservative_stop_exit, conservative_target_exit


def test_conservative_stop_exit_uses_worse_gap_price_plus_slippage():
    assert conservative_stop_exit(side="LONG", mark=94.0, stop_price=95.0) < 94.0
    assert conservative_stop_exit(side="SHORT", mark=106.0, stop_price=105.0) > 106.0


def test_conservative_target_exit_caps_at_target_and_applies_slippage():
    long_exit = conservative_target_exit(side="LONG", mark=106.0, target_price=105.0)
    short_exit = conservative_target_exit(side="SHORT", mark=94.0, target_price=95.0)
    assert long_exit < 105.0
    assert short_exit > 95.0
