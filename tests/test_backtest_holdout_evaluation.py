import json
from pathlib import Path

import pytest

from app.backtest.holdout_evaluation import _thresholds_from_freeze


def _freeze():
    return {
        "status":"DEVELOPMENT_DECISIONS_FROZEN",
        "parameters_frozen":True,
        "same_window_optimization_allowed":False,
        "thresholds":{
            "min_open_interest_usd":75000.0,
            "min_volume_24h_usd":150000.0,
            "rsi_long_max":28.0,
            "rsi_short_min":72.0,
            "min_extension_pct":1.4,
            "max_extension_pct":3.5,
            "min_rr":1.8,
            "htf_alignment_enabled":True,
            "rsi_period":14,
            "extension_lookback_bars":20,
        },
    }


def test_frozen_thresholds_round_trip_exactly():
    t=_thresholds_from_freeze(_freeze())
    assert t.min_open_interest_usd==75000.0
    assert t.min_volume_24h_usd==150000.0
    assert t.rsi_long_max==28.0
    assert t.rsi_short_min==72.0
    assert t.min_extension_pct==1.4
    assert t.max_extension_pct==3.5
    assert t.min_rr==1.8
    assert t.htf_alignment_enabled is True


def test_holdout_refuses_unfrozen_development_state():
    bad=_freeze();bad["parameters_frozen"]=False
    with pytest.raises(RuntimeError):_thresholds_from_freeze(bad)
    bad=_freeze();bad["same_window_optimization_allowed"]=True
    with pytest.raises(RuntimeError):_thresholds_from_freeze(bad)
    bad=_freeze();bad["status"]="WRONG"
    with pytest.raises(RuntimeError):_thresholds_from_freeze(bad)
