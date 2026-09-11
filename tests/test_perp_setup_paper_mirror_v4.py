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


def setup(state="PREPARE", tier="QUALIFIED", side="LONG", price=100.0):
    return {
        "setup_key": f"BTC:{side}",
        "first_seen_at": "2026-09-10T13:00:00+00:00",
        "last_seen_at": "2026-09-10T13:01:00+00:00",
        "symbol": "BTC",
        "side": side,
        "tier": tier,
        "state": state,
        "trade_status": "NOT_ENTERED",
        "discovery_stale": False,
        "score": 80.0,
        "price": price,
        "levels_frozen": True,
        "levels": {"l1": 99.0, "l2": 98.0, "l3": 97.0, "stop": 95.0, "tp1": 105.0, "tp2": 110.0, "target_rr": 1.8},
    }


def mirror_with(fake, tmp_path):
    m = mod.PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    m._seeded = True
    mod.paper_journal = fake
    return m


def test_prepare_arms_resting_paper_limit_but_does_not_fake_fill(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    result = asyncio.run(m.sync([setup()], {"BTC": 100.0}))
    assert result["armed"] == 1
    assert result["pending"] == 1
    assert result["opened"] == 0
    assert fake.open_calls == []
    pending = next(iter(m._pending.values()))
    assert pending["limit_price"] == 99.0
    assert pending["source"] == "perp_manual_auto"


def test_pending_limit_fills_once_only_after_price_touches_l1(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    first = asyncio.run(m.sync([setup()], {"BTC": 100.0}))
    second = asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    third = asyncio.run(m.sync([setup()], {"BTC": 98.5}))
    assert first["opened"] == 0
    assert second["opened"] == 1
    assert third["opened"] == 0
    call = fake.open_calls[0]
    assert call["entry"] == 99.0
    assert call["source"] == "perp_manual_auto"
    assert call["strategy"] == "perp_setup_auto_v2_resting_limit"
    assert call["counts_for_live"] is False
    assert call["features"]["paper_order_model"] == "RESTING_L1_LIMIT"
    assert call["features"]["paper_fill_model"] == "LIMIT_TOUCH"


def test_pending_limit_survives_restart_and_fills(tmp_path, monkeypatch):
    fake = FakeJournal()
    path = tmp_path / "pending.jsonl"
    first = mod.PerpSetupPaperMirror(pending_path=path)
    first._seeded = True
    mod.paper_journal = fake
    asyncio.run(first.sync([setup()], {"BTC": 100.0}))
    assert first._pending

    monkeypatch.setattr(mod, "JOURNAL_PATH", tmp_path / "empty-journal.jsonl")
    second = mod.PerpSetupPaperMirror(pending_path=path)
    mod.paper_journal = fake
    result = asyncio.run(second.sync([setup()], {"BTC": 99.0}))
    assert result["opened"] == 1
    assert len(fake.open_calls) == 1


def test_invalidated_gap_through_stop_cancels_pending_without_optimistic_fill(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    asyncio.run(m.sync([setup()], {"BTC": 100.0}))
    result = asyncio.run(m.sync([setup(state="INVALIDATED", price=94.0)], {"BTC": 94.0}))
    assert result["opened"] == 0
    assert result["pending"] == 0
    assert result["cancelled"] >= 1
    assert fake.open_calls == []


def test_stale_discovery_does_not_arm_a_new_paper_order(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    row = setup()
    row["discovery_stale"] = True
    result = asyncio.run(m.sync([row], {"BTC": 100.0}))
    assert result["armed"] == 0
    assert result["pending"] == 0
    assert fake.open_calls == []


def test_watch_tier_does_not_arm_even_if_prepare(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    result = asyncio.run(m.sync([setup(tier="WATCH")], {"BTC": 100.0}))
    assert result["armed"] == 0
    assert result["pending"] == 0


def test_auto_paper_trade_closes_at_tp1_and_records_mark(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    asyncio.run(m.sync([setup()], {"BTC": 100.0}))
    asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    result = asyncio.run(m.sync([setup()], {"BTC": 106.0}))
    assert result["closed"] == 1
    assert fake.mark_calls[-1] == ("t1", 106.0)
    assert fake.close_calls[-1][1]["exit_reason"] == "SETUP_TP1"


def test_auto_paper_trade_closes_at_stop(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    asyncio.run(m.sync([setup()], {"BTC": 100.0}))
    asyncio.run(m.sync([setup()], {"BTC": 99.0}))
    result = asyncio.run(m.sync([setup()], {"BTC": 94.0}))
    assert result["closed"] == 1
    assert fake.close_calls[-1][1]["exit_reason"] == "SETUP_STOP"


def test_real_manual_trade_book_is_never_mutated_by_auto_paper_mirror(tmp_path):
    fake = FakeJournal()
    m = mirror_with(fake, tmp_path)
    row = setup()
    asyncio.run(m.sync([row], {"BTC": 100.0}))
    asyncio.run(m.sync([row], {"BTC": 99.0}))
    assert row["trade_status"] == "NOT_ENTERED"
    assert "entry_price" not in row
    assert all(call.get("trade_type") == "PAPER" for call in fake.open_calls)
