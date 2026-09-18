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
