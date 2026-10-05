from datetime import datetime, timedelta, timezone
import json

from app.services.evidence_checkpoint_history import MAX_HISTORY, history_view, load_history, persist, previous_lanes
from app.services.cross_strategy_scorecard import build_cross_strategy_scorecard


def _report(sample=1):
    rows=[{"net_pnl_r": 0.5, "exit_timestamp": "2026-10-05T10:00:00+00:00"}] * sample
    return build_cross_strategy_scorecard(
        day_rows=rows,
        investment_snapshot={"summary": {"open_lots": 0, "closed_lots": 0}, "closed_lots": [], "timeline": []},
        prediction_snapshot={"summary": {"open_positions": 0, "closed_trades": 0}, "events": []},
    )


def test_checkpoint_history_is_telemetry_only_and_drives_movement_not_performance(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    first=_report(1)
    t0=datetime(2026,10,5,10,tzinfo=timezone.utc)
    assert persist(first,path=path,now=t0)["persisted"] is True
    history=load_history(path)
    assert history[0]["telemetry_only"] is True
    assert history[0]["performance_interpretation"] is None
    assert history[0]["strategy_action"] is None
    prior=previous_lanes(history)
    second=build_cross_strategy_scorecard(
        day_rows=[{"net_pnl_r":0.5,"exit_timestamp":"2026-10-05T10:00:00+00:00"},{"net_pnl_r":-0.25,"exit_timestamp":"2026-10-05T11:00:00+00:00"}],
        investment_snapshot={"summary":{},"closed_lots":[],"timeline":[]},
        prediction_snapshot={"summary":{},"events":[]},
        previous_checkpoints=prior,
    )
    day={x["lane"]:x for x in second["lanes"]}["DAY_TRADING"]
    assert day["evidence_checkpoint"]["movement"] == "GROWING"
    assert day["evidence_checkpoint"]["performance_interpretation"] is None
    assert second["comparison_rules"]["thresholds_modified"] is False
    assert second["comparison_rules"]["production_strategy_modified"] is False


def test_unchanged_checkpoint_is_deduped_inside_one_hour(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    report=_report(1)
    t0=datetime(2026,10,5,10,tzinfo=timezone.utc)
    assert persist(report,path=path,now=t0)["persisted"] is True
    result=persist(report,path=path,now=t0+timedelta(minutes=30))
    assert result == {"persisted": False, "reason": "UNCHANGED_WITHIN_INTERVAL"}
    assert len(load_history(path)) == 1


def test_history_reader_ignores_malformed_and_view_is_bounded(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    path.write_text("not-json\n" + json.dumps({"telemetry_only":False}) + "\n",encoding="utf-8")
    base=datetime(2026,10,5,10,tzinfo=timezone.utc)
    for i in range(55):
        persist(_report(1 if i % 2 == 0 else 2),path=path,now=base+timedelta(hours=i))
    view=history_view(path,limit=50)
    assert view["telemetry_only"] is True
    assert view["performance_interpretation"] is None
    assert view["strategy_action"] is None
    assert view["retention_max"] == MAX_HISTORY
    assert view["returned"] == 50
    assert len(view["checkpoints"]) == 50
