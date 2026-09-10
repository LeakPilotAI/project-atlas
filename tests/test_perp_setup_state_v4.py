from __future__ import annotations

from app.trading_core.models import Side
from app.trading_core.perp_setup_state import PerpSetupState, classify_setup_state


def test_long_state_progression():
    kw = dict(side=Side.LONG, l1=99.0, l2=98.0, l3=97.0, stop=96.0, tp1=102.0, tp2=104.0)
    assert classify_setup_state(mark=100.0, **kw).state is PerpSetupState.WAIT
    assert classify_setup_state(mark=99.4, **kw).state is PerpSetupState.PREPARE
    assert classify_setup_state(mark=99.0, **kw).state is PerpSetupState.L1_ACTIVE
    assert classify_setup_state(mark=98.0, **kw).state is PerpSetupState.L2_ACTIVE
    assert classify_setup_state(mark=97.0, **kw).state is PerpSetupState.L3_ACTIVE
    assert classify_setup_state(mark=95.9, **kw).state is PerpSetupState.INVALIDATED
    assert classify_setup_state(mark=102.0, **kw).state is PerpSetupState.TP1_HIT
    assert classify_setup_state(mark=104.0, **kw).state is PerpSetupState.TP2_HIT


def test_short_state_progression():
    kw = dict(side=Side.SHORT, l1=101.0, l2=102.0, l3=103.0, stop=104.0, tp1=98.0, tp2=96.0)
    assert classify_setup_state(mark=100.0, **kw).state is PerpSetupState.WAIT
    assert classify_setup_state(mark=100.5, **kw).state is PerpSetupState.PREPARE
    assert classify_setup_state(mark=101.0, **kw).state is PerpSetupState.L1_ACTIVE
    assert classify_setup_state(mark=102.0, **kw).state is PerpSetupState.L2_ACTIVE
    assert classify_setup_state(mark=103.0, **kw).state is PerpSetupState.L3_ACTIVE
    assert classify_setup_state(mark=104.1, **kw).state is PerpSetupState.INVALIDATED
    assert classify_setup_state(mark=98.0, **kw).state is PerpSetupState.TP1_HIT
    assert classify_setup_state(mark=96.0, **kw).state is PerpSetupState.TP2_HIT


def test_invalid_mark_rejected():
    try:
        classify_setup_state(side=Side.LONG, mark=0, l1=99, l2=98, l3=97, stop=96, tp1=102, tp2=104)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
