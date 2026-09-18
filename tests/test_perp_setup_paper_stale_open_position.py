import asyncio
from datetime import datetime, timedelta, timezone

import app.services.perp_setup_paper_mirror as mirror_mod


class _Journal:
    def __init__(self):
        self.updated = 0
        self.closed = 0
    def list_open(self):
        return [{
            "trade_id":"t1","trade_type":"PAPER","source":mirror_mod.SOURCE,
            "symbol":"BTC","side":"LONG","working_stop":95.0,"stop_price":95.0,
            "tp1_price":105.0,
        }]
    def update_excursion(self,*args,**kwargs):
        self.updated += 1
    async def close_trade(self,*args,**kwargs):
        self.closed += 1


def test_stale_open_position_mark_is_ignored(tmp_path, monkeypatch):
    journal=_Journal()
    monkeypatch.setattr(mirror_mod,"paper_journal",journal)
    mirror=mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path/"pending.jsonl")
    mirror._seeded=True
    stale=(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat()
    setup={"setup_key":"BTC:LONG","first_seen_at":"x","paper_mirror_epoch_at":"x","symbol":"BTC","side":"LONG","mark_timestamp":stale}
    out=asyncio.run(mirror.sync([setup],{"BTC":94.0}))
    assert journal.updated == 0
    assert journal.closed == 0
    assert out["skipped"] >= 1
