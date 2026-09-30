import asyncio

import app.services.perp_setup_paper_mirror as mirror_mod


class _Journal:
    def __init__(self, session_r):
        self.session_r = session_r
        self.open_calls = []

    def list_open(self):
        return []

    async def stats(self):
        return {"sum_r": self.session_r}

    async def open_trade(self, **kwargs):
        self.open_calls.append(kwargs)
        return "t1"


def _armed_mirror(tmp_path):
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    mirror._seeded = True
    instance = "BTC:LONG|first|epoch"
    mirror._pending = {
        instance: {
            "event": "armed",
            "setup_instance_id": instance,
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "limit_price": 99.0,
            "stop": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
            "signal_price": 100.0,
            "signal_score": 80,
            "target_rr": 1.8,
            "tier": "QUALIFIED",
        }
    }
    return mirror, instance


def test_fill_does_not_use_lifetime_journal_r_for_daily_loss_stop(tmp_path, monkeypatch):
    journal = _Journal(-30.0)
    monkeypatch.setattr(mirror_mod, "paper_journal", journal)
    monkeypatch.setattr(mirror_mod.paper_risk_controls, "kill_switch", False)
    monkeypatch.setattr(
        mirror_mod,
        "utc_day_risk_snapshot",
        lambda: {
            "net_r": 0.0,
            "closed": 0,
            "window": "UTC_DAY",
            "window_date": "2026-09-30",
            "source": "PAPER_JOURNAL_REALIZED_CLOSES",
        },
    )
    mirror, instance = _armed_mirror(tmp_path)

    assert asyncio.run(mirror._fill_pending(instance, mark=98.98)) is True
    assert len(journal.open_calls) == 1


def test_fill_uses_current_utc_day_r_for_loss_stop(tmp_path, monkeypatch):
    journal = _Journal(20.0)
    monkeypatch.setattr(mirror_mod, "paper_journal", journal)
    monkeypatch.setattr(mirror_mod.paper_risk_controls, "kill_switch", False)
    monkeypatch.setattr(
        mirror_mod,
        "utc_day_risk_snapshot",
        lambda: {
            "net_r": -3.0,
            "closed": 3,
            "window": "UTC_DAY",
            "window_date": "2026-09-30",
            "source": "PAPER_JOURNAL_REALIZED_CLOSES",
        },
    )
    mirror, instance = _armed_mirror(tmp_path)

    assert asyncio.run(mirror._fill_pending(instance, mark=98.98)) is False
    assert not journal.open_calls
    pending_text = (tmp_path / "pending.jsonl").read_text(encoding="utf-8")
    assert "PAPER_RISK_BLOCK" in pending_text
    assert "paper session loss stop reached" in pending_text
    assert '"window": "UTC_DAY"' in pending_text
