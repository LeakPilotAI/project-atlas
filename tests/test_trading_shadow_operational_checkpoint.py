import json
from datetime import datetime,timezone
from pathlib import Path

from app.trading_core.events import TradingEventType
from app.trading_core.event_store import JsonlEventStore
from app.trading_core.shadow_operational_checkpoint import inspect


def test_empty_shadow_store_is_green_and_live_disabled(tmp_path:Path):
    path=tmp_path/"shadow.jsonl"
    result=inspect(event_path=path)
    assert result["status"]=="PAPER_SHADOW_CHECKPOINT_GREEN"
    assert result["event_count"]==0
    assert result["persistent_recovery_ready"] is True
    assert result["shadow_isolation_ready"] is True
    assert result["legacy_state_mutated"] is False
    assert result["real_order_actions"] is False
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False


def test_valid_event_store_is_recoverable(tmp_path:Path):
    path=tmp_path/"shadow.jsonl"
    store=JsonlEventStore(path)
    store.append(event_type=TradingEventType.POSITION_OPENED,trade_id="t1",symbol="BTC",timestamp=datetime.now(timezone.utc).isoformat(),payload={"position":{
        "trade_id":"t1","symbol":"BTC","side":"LONG","strategy_version":"test","opened_at":datetime.now(timezone.utc).isoformat(),
        "signal_price":100.0,"entry_price":100.0,"initial_stop":99.0,"working_stop":99.0,"target_price":101.8,
        "target_r":1.8,"risk_price":1.0,"risk_usd":1.0,"quantity":1.0,"status":"OPEN","mfe_r":0.0,"mae_r":0.0,
        "last_price":100.0,"last_timestamp":datetime.now(timezone.utc).isoformat(),"be_armed":False,"lock_armed":False,
        "closed_at":None,"exit_price":None,"exit_reason":None,"gross_r":None,"net_r":None,"fees_usd":0.0
    }})
    result=inspect(event_path=path)
    assert result["status"]=="PAPER_SHADOW_CHECKPOINT_GREEN"
    assert result["event_count"]==1
    assert result["recovered_open"]==1
    assert result["shadow_snapshot"]["open"]==1


def test_corrupt_middle_line_blocks_checkpoint(tmp_path:Path):
    path=tmp_path/"shadow.jsonl"
    path.write_text('{"bad":true}\nnot-json\n{"x":1}\n',encoding="utf-8")
    result=inspect(event_path=path)
    assert result["status"]=="PAPER_SHADOW_CHECKPOINT_BLOCKED"
    assert result["event_store_corruption"]
    assert result["persistent_recovery_ready"] is False
    assert result["live_capital_allowed"] is False
