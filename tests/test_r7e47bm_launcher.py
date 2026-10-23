"""R7E47BM launcher integration tests."""
import pytest
from scripts.observation_runtime.r7e47bm_launcher import run_offline

def test_guarded_offline_lifecycle():
    report = run_offline()
    assert report["mode"] == "SYNTHETIC_OFFLINE"
    assert report["final_event"] == "GRACEFUL_SHUTDOWN"
    assert report["observations"] == 1
    assert report["budget_remaining"] == 0
    assert report["network_enabled"] is False
    assert report["trading_enabled"] is False

def test_no_live_entrypoint():
    from scripts.observation_runtime import r7e47bm_launcher
    assert not hasattr(r7e47bm_launcher, "run_live")
