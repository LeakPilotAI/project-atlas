import asyncio
import json

import app.services.perp_setup_paper_mirror as mirror_mod


class _Journal:
    def list_open(self):
        return []


def test_terminal_pending_instance_cannot_fill_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror_mod, "paper_journal", _Journal())
    path = tmp_path / "pending.jsonl"
    instance = "BTC:LONG|first|epoch"
    path.write_text(
        json.dumps({"event":"armed","setup_instance_id":instance,"setup_key":"BTC:LONG","symbol":"BTC","side":"LONG"})+"\n"+
        json.dumps({"event":"filled","setup_instance_id":instance,"setup_key":"BTC:LONG","symbol":"BTC","side":"LONG"})+"\n",
        encoding="utf-8",
    )
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    mirror._pending = {
        instance:{
            "event":"armed","setup_instance_id":instance,"setup_key":"BTC:LONG",
            "symbol":"BTC","side":"LONG","limit_price":99.0,"stop":95.0,"tp1":105.0,"tp2":110.0,
        }
    }
    assert asyncio.run(mirror._fill_pending(instance, mark=99.0)) is False
    assert instance not in mirror._pending
