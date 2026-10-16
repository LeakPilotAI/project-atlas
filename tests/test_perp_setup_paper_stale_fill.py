import asyncio
from datetime import datetime, timedelta, timezone

import app.services.perp_setup_paper_mirror as mirror_mod


class _Journal:
    def list_open(self):
        return []


def test_stale_mark_before_fill_cancels_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror_mod, "paper_journal", _Journal())
    path = tmp_path / "pending.jsonl"
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    instance = "BTC:LONG|first|epoch"
    mirror._pending = {
        instance: {
            "event":"armed","setup_instance_id":instance,"setup_key":"BTC:LONG",
            "symbol":"BTC","side":"LONG","limit_price":99.0,"stop":95.0,"tp1":105.0,"tp2":110.0,
        }
    }
    setup = {
        "setup_key":"BTC:LONG","first_seen_at":"first","paper_mirror_epoch_at":"epoch",
        "symbol":"BTC","side":"LONG","state":"PREPARE",
        "mark_timestamp": (datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat(),
    }
    assert asyncio.run(mirror._fill_pending(instance, mark=99.0, setup=setup)) is False
    assert instance not in mirror._pending
    assert "STALE_MARK_BEFORE_FILL" in path.read_text(encoding="utf-8")
