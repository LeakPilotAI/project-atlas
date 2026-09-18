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
