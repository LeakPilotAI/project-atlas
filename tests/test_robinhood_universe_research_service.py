from __future__ import annotations

from app.services.robinhood_universe_research import RobinhoodUniverseResearchService


def test_universe_research_defaults_are_deliberately_slow(monkeypatch):
    monkeypatch.delenv("ATLAS_RH_UNIVERSE_BATCH_SIZE", raising=False)
    monkeypatch.delenv("ATLAS_RH_UNIVERSE_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("ATLAS_RH_UNIVERSE_SYNC_SECONDS", raising=False)
    svc = RobinhoodUniverseResearchService()
    assert svc.batch_size == 4
    assert svc.interval_seconds == 21600.0
    assert svc.sync_interval_seconds == 86400.0
    status = svc.status()
    assert status["execution"] == "RESEARCH_ONLY_MANUAL"
    assert status["live_capital_allowed"] is False
    assert status["automatic_real_money_execution"] is False


def test_universe_research_env_cannot_become_high_frequency(monkeypatch):
    monkeypatch.setenv("ATLAS_RH_UNIVERSE_BATCH_SIZE", "999")
    monkeypatch.setenv("ATLAS_RH_UNIVERSE_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("ATLAS_RH_UNIVERSE_SYNC_SECONDS", "1")
    svc = RobinhoodUniverseResearchService()
    assert svc.batch_size == 8
    assert svc.interval_seconds == 3600.0
    assert svc.sync_interval_seconds == 21600.0
