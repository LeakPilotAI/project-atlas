import asyncio
from datetime import datetime, timedelta, timezone

import app.api.command_center as cc_api
import app.services.perp_setup_paper_mirror as mirror_mod
from app.trading_core.perp_setup_lifecycle import reconcile_setups


class _Journal:
    def list_open(self):
        return []


class _ManualService:
    def snapshot(self):
        return {
            "running": True,
            "market_count": 234,
            "setups": [{"setup_key": "BTC:LONG", "symbol": "BTC", "side": "LONG", "state": "PREPARE", "tier": "QUALIFIED"}],
            "plans": [],
            "alert_candidates": [],
        }


class _MirrorStatus:
    def status(self):
        return {"pending_count": 7, "open_count": 2, "opened_total": 72, "closed_total": 70}


def _setup(now: datetime, *, stale: bool = False) -> dict:
    return {
        "setup_key": "BTC:LONG",
        "first_seen_at": (now - timedelta(hours=4)).isoformat(),
        "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
        "paper_mirror_epoch_at": "epoch-1",
        "symbol": "BTC",
        "side": "LONG",
        "tier": "QUALIFIED",
        "score": 80.0,
        "state": "WAIT" if stale else "PREPARE",
        "price": 100.0,
        "mark": 100.0,
        "discovery_stale": stale,
        "levels": {"l1": 99.0, "l2": 98.0, "l3": 97.0, "stop": 95.0, "tp1": 105.0, "tp2": 110.0},
    }


def test_missing_setup_retention_is_measured_from_last_seen_not_first_seen():
    now = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)
    prior = _setup(now)
    out = reconcile_setups([], previous=[prior], now=now, retention_minutes=10)
    assert len(out) == 1
    assert out[0]["discovery_stale"] is True
    assert out[0]["state"] == "WAIT"


def test_missing_setup_expires_after_last_seen_retention_window():
    now = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)
    prior = _setup(now)
    prior["last_seen_at"] = (now - timedelta(minutes=11)).isoformat()
    out = reconcile_setups([], previous=[prior], now=now, retention_minutes=10)
    assert out == []


def test_detached_pending_limit_is_cancelled_instead_of_living_forever(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror_mod, "paper_journal", _Journal())
    m = mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    m._seeded = True
    m._pending = {
        "BTC:LONG|first|epoch": {
            "timestamp": "2026-09-12T10:00:00+00:00",
            "event": "armed",
            "setup_instance_id": "BTC:LONG|first|epoch",
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "limit_price": 99.0,
            "stop": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
        }
    }
    result = asyncio.run(m.sync([], {"BTC": 100.0}))
    assert result["cancelled"] == 1
    assert result["pending"] == 0
    text = (tmp_path / "pending.jsonl").read_text(encoding="utf-8")
    assert "DETACHED_AFTER_RETENTION" in text


def test_retained_stale_setup_keeps_existing_pending_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror_mod, "paper_journal", _Journal())
    now = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)
    row = _setup(now, stale=True)
    row["first_seen_at"] = "first"
    instance = "BTC:LONG|first|epoch-1"
    m = mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    m._seeded = True
    m._pending = {
        instance: {
            "timestamp": now.isoformat(),
            "event": "armed",
            "setup_instance_id": instance,
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "limit_price": 99.0,
            "stop": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
        }
    }
    result = asyncio.run(m.sync([row], {"BTC": 100.0}))
    assert result["cancelled"] == 0
    assert result["pending"] == 1


def test_command_center_route_injects_same_auto_paper_observability(monkeypatch):
    monkeypatch.setattr(cc_api, "perp_manual_service", _ManualService())
    monkeypatch.setattr(cc_api, "perp_setup_paper_mirror", _MirrorStatus())
    monkeypatch.setattr(
        cc_api,
        "build_paper_observability",
        lambda setups: {
            "pending_health": {"pending_count": 7, "currently_backed": 3, "not_in_current_snapshot": 4},
            "clean_cohort": {"cohort": "manual_auto_observability_v1", "opened": 1, "closed": 0, "open": 1},
        },
    )
    out = asyncio.run(cc_api.command_center_summary())
    perps = out["perps"]
    assert perps["auto_paper_pending_count"] == 7
    assert perps["auto_paper_pending_health"]["currently_backed"] == 3
    assert perps["auto_paper_clean_cohort"]["cohort"] == "manual_auto_observability_v1"
