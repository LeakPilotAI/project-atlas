import asyncio

import app.services.perp_setup_paper_mirror as mirror_mod


class _Journal:
    def __init__(self, session_r):
        self.session_r=session_r
        self.open_calls=[]
    def list_open(self):
        return []
    async def stats(self):
        return {"sum_r": self.session_r}
    async def open_trade(self, **kwargs):
        self.open_calls.append(kwargs)
        return "t1"


def test_fill_uses_journal_session_r_for_loss_stop(tmp_path, monkeypatch):
    journal=_Journal(-3.0)
    monkeypatch.setattr(mirror_mod,"paper_journal",journal)
    monkeypatch.setattr(mirror_mod.paper_risk_controls,"kill_switch",False)
    mirror=mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path/"pending.jsonl")
    mirror._seeded=True
    instance="BTC:LONG|first|epoch"
    mirror._pending={instance:{
        "event":"armed","setup_instance_id":instance,"setup_key":"BTC:LONG","symbol":"BTC","side":"LONG",
        "limit_price":99.0,"stop":95.0,"tp1":105.0,"tp2":110.0,"signal_price":100.0,"signal_score":80,
        "target_rr":1.8,"tier":"QUALIFIED",
    }}
    assert asyncio.run(mirror._fill_pending(instance, mark=99.0)) is False
    assert not journal.open_calls
    assert "PAPER_RISK_BLOCK" in (tmp_path/"pending.jsonl").read_text(encoding="utf-8")
