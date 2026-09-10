from datetime import datetime, timedelta, timezone

import pytest

from app.trading_core.event_store import EventStoreCorruption, JsonlEventStore
from app.trading_core.events import TradingEventType, position_to_payload
from app.trading_core.models import MarketQuote, PaperExecutionConfig, Side, TradeIntent
from app.trading_core.paper_engine import PaperEngine
from app.trading_core.persistent_runtime import PersistentPaperRuntime
from app.trading_core.position_book import PositionBook


T0 = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)


def _intent(trade_id="t1", side=Side.LONG):
    return TradeIntent(
        trade_id=trade_id,
        symbol="BTC",
        side=side,
        signal_price=100.0,
        stop_price=99.0 if side is Side.LONG else 101.0,
        target_r=1.8,
        risk_usd=10.0,
        signal_timestamp=T0,
        strategy_version="v4-test",
    )


def _q(price, seconds=0):
    return MarketQuote(symbol="BTC", price=price, timestamp=T0 + timedelta(seconds=seconds))


def test_store_roundtrip_and_sequence(tmp_path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    e1 = store.append(event_type=TradingEventType.SIGNAL_CREATED, trade_id="t1", symbol="BTC", payload={"x": 1})
    e2 = store.append(event_type=TradingEventType.INTENT_APPROVED, trade_id="t1", symbol="BTC", payload={"x": 2})
    assert e1.sequence == 1
    assert e2.sequence == 2
    loaded = store.load()
    assert [e.sequence for e in loaded] == [1, 2]


def test_duplicate_event_id_is_idempotent(tmp_path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    a = store.append(event_type=TradingEventType.SIGNAL_CREATED, trade_id="t1", symbol="BTC", payload={}, event_id="same")
    b = store.append(event_type=TradingEventType.SIGNAL_CREATED, trade_id="t1", symbol="BTC", payload={}, event_id="same")
    assert a == b
    assert len(store.load()) == 1


def test_position_book_replays_open_and_close(tmp_path):
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    pos = engine.open(_intent(), _q(100))
    store = JsonlEventStore(tmp_path / "events.jsonl")
    e1 = store.append(event_type=TradingEventType.POSITION_OPENED, trade_id="t1", symbol="BTC", payload={"position": position_to_payload(pos)})
    book = PositionBook().replay([e1])
    assert book.get_open("t1") is not None
    closed = engine.mark(pos, _q(102, 1)).position
    e2 = store.append(event_type=TradingEventType.POSITION_CLOSED, trade_id="t1", symbol="BTC", payload={"position": position_to_payload(closed)})
    book = PositionBook.from_events([e1, e2])
    assert book.get_open("t1") is None
    assert book.get_closed("t1") is not None


def test_persistent_runtime_restart_restores_open(tmp_path):
    path = tmp_path / "events.jsonl"
    rt1 = PersistentPaperRuntime(path, PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    rt1.open(_intent(), _q(100))
    rt1.mark("t1", _q(100.5, 1))
    rt2 = PersistentPaperRuntime(path, PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    assert rt2.recover() == 1
    pos = rt2.book.get_open("t1")
    assert pos is not None
    assert pos.mfe_r >= 0.5


def test_persistent_runtime_restart_then_close_once(tmp_path):
    path = tmp_path / "events.jsonl"
    cfg = PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0)
    rt1 = PersistentPaperRuntime(path, cfg)
    rt1.open(_intent(), _q(100))
    rt2 = PersistentPaperRuntime(path, cfg)
    closed = rt2.mark("t1", _q(102, 1))
    assert closed.status.value == "CLOSED"
    rt3 = PersistentPaperRuntime(path, cfg)
    assert rt3.book.get_closed("t1") is not None
    assert len([e for e in rt3.store.load() if e.event_type is TradingEventType.POSITION_CLOSED]) == 1


def test_store_tolerates_truncated_last_line(tmp_path):
    path = tmp_path / "events.jsonl"
    store = JsonlEventStore(path)
    store.append(event_type=TradingEventType.SIGNAL_CREATED, trade_id="t1", symbol="BTC", payload={})
    with path.open("a", encoding="utf-8") as f:
        f.write('{"event_id":"partial"')
    loaded = store.load()
    assert len(loaded) == 1


def test_store_rejects_middle_corruption(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"bad":\n{"event_id":"x"}\n', encoding="utf-8")
    store = JsonlEventStore(path)
    with pytest.raises(EventStoreCorruption):
        store.load()


def test_closed_trade_id_cannot_reopen(tmp_path):
    path = tmp_path / "events.jsonl"
    cfg = PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0)
    rt = PersistentPaperRuntime(path, cfg)
    rt.open(_intent(), _q(100))
    rt.mark("t1", _q(102, 1))
    with pytest.raises(ValueError):
        rt.open(_intent(), _q(100, 2))
