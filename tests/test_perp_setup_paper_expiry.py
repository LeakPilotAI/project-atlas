import asyncio
from datetime import datetime, timedelta, timezone

from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror


def test_stale_pending_limit_expires_before_fill(tmp_path):
    path = tmp_path / "pending.jsonl"
    mirror = PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    mirror._pending = {
        "BTC|a|a": {
            "timestamp": old,
            "event": "armed",
            "setup_instance_id": "BTC|a|a",
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "limit_price": 100.0,
            "stop": 95.0,
            "tp1": 110.0,
            "tp2": 120.0,
        }
    }
    out = asyncio.run(mirror.sync([], {"BTC": 99.0}))
    assert out["expired"] == 1
    assert out["cancelled"] >= 1
    assert mirror.status()["pending_count"] == 0


def test_retained_discovery_stale_setup_is_not_age_expired(tmp_path):
    path = tmp_path / "pending.jsonl"
    mirror = PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    instance = "BTC:LONG|first|epoch"
    mirror._pending = {
        instance: {
            "timestamp": old,
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
    setup = {
        "setup_key": "BTC:LONG",
        "first_seen_at": "first",
        "paper_mirror_epoch_at": "epoch",
        "symbol": "BTC",
        "side": "LONG",
        "state": "WAIT",
        "discovery_stale": True,
        "price": 100.0,
        "levels": {"l1": 99.0, "l2": 98.0, "l3": 97.0, "stop": 95.0, "tp1": 105.0, "tp2": 110.0},
    }
    out = asyncio.run(mirror.sync([setup], {"BTC": 100.0}))
    assert out["expired"] == 0
    assert out["cancelled"] == 0
    assert out["pending"] == 1
