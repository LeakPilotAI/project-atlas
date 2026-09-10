import asyncio

import app.services.perp_setup_paper_mirror as mod


class FakeJournal:
    def __init__(self):
        self.open_rows = []
        self.open_calls = []
        self.close_calls = []
        self.mark_calls = []

    def list_open(self):
        return list(self.open_rows)

    async def open_trade(self, **kwargs):
        self.open_calls.append(dict(kwargs))
        row = {
            "trade_id": f"t{len(self.open_calls)}",
            "trade_type": "PAPER",
            "source": kwargs.get("source"),
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "actual_entry_price": kwargs["entry"],
            "stop_price": kwargs["stop"],
            "working_stop": kwargs["stop"],
            "tp1_price": kwargs["tp1"],
            "tp2_price": kwargs["tp2"],
            "features": kwargs.get("features") or {},
        }
        self.open_rows.append(row)
        return row["trade_id"]

    def update_excursion(self, trade_id, mark):
        self.mark_calls.append((trade_id, mark))

    async def close_trade(self, trade_id, **kwargs):
        self.close_calls.append((trade_id, dict(kwargs)))
        self.open_rows = [r for r in self.open_rows if r.get("trade_id") != trade_id]
        return {"trade_id": trade_id}


def setup(state="L1_ACTIVE", tier="QUALIFIED", side="LONG"):
    return {
        "setup_key": f"BTC:{side}",
        "first_seen_at": "2026-09-10T13:00:00+00:00",
        "symbol": "BTC",
        "side": side,
        "tier": tier,
        "state": state,
        "score": 80.0,
        "price": 100.0,
        "levels": {"l1": 99.0, "l2": 98.0, "l3": 97.0, "stop": 95.0, "tp1": 105.0, "tp2": 110.0, "target_rr": 1.8},
    }


def mirror_with(fake):
    m = mod.PerpSetupPaperMirror()
    m._seeded = True
    mod.paper_journal = fake
    return m


def test_prepare_does_not_paper_enter_early():
    fake = FakeJournal()
    m = mirror_with(fake)
    result = asyncio.run(m.sync([setup(state="PREPARE")], {"BTC": 100.0}))
    assert result["opened"] == 0
    assert fake.open_calls == []


def test_active_qualified_setup_opens_once_at_planned_l1():
    fake = FakeJournal()
    m = mirror_with(fake)
    first = asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    second = asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    assert first["opened"] == 1
    assert second["opened"] == 0
    call = fake.open_calls[0]
    assert call["entry"] == 99.0
    assert call["source"] == "perp_manual_auto"
    assert call["strategy"] == "perp_setup_auto_v1"
    assert call["counts_for_live"] is False
    assert call["features"]["paper_fill_model"] == "L1_LIMIT_ASSUMED"


def test_auto_paper_trade_closes_at_tp1_and_records_mark():
    fake = FakeJournal()
    m = mirror_with(fake)
    asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    result = asyncio.run(m.sync([setup()], {"BTC": 106.0}))
    assert result["closed"] == 1
    assert fake.mark_calls[-1] == ("t1", 106.0)
    assert fake.close_calls[-1][1]["exit_reason"] == "SETUP_TP1"


def test_auto_paper_trade_closes_at_stop():
    fake = FakeJournal()
    m = mirror_with(fake)
    asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    result = asyncio.run(m.sync([setup()], {"BTC": 94.0}))
    assert result["closed"] == 1
    assert fake.close_calls[-1][1]["exit_reason"] == "SETUP_STOP"
