from pathlib import Path
import json
import pytest

from app.backtest.representative_windows import RepresentativeWindow,locked_representative_windows,write_windows


def test_locked_windows_are_non_overlapping_and_have_holdouts():
    rows=locked_representative_windows()
    assert len(rows)==4
    assert {x.role for x in rows}=={"DEVELOPMENT","HOLDOUT"}
    assert len([x for x in rows if x.role=="HOLDOUT"])==2
    for left,right in zip(rows,rows[1:]):
        assert left.end_utc<=right.start_utc


def test_window_payload_is_research_only_and_declares_holdout_policy(tmp_path:Path):
    out=write_windows(tmp_path/"windows.json")
    payload=json.loads(out.read_text(encoding="utf-8"))
    assert payload["mode"]=="RESEARCH_ONLY_HISTORICAL_WINDOWS"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert "must not be used" in payload["holdout_policy"]
    assert [x["window_id"] for x in payload["windows"]]==[
        "dev-2024-h2","dev-2025-h1","holdout-2025-h2","holdout-2026-h1"
    ]


def test_invalid_window_fails_closed():
    with pytest.raises(ValueError):
        RepresentativeWindow("bad","2026-01-02T00:00:00Z","2026-01-01T00:00:00Z","DEVELOPMENT","bad").validate()
