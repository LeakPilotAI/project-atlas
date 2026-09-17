import json
from pathlib import Path

from app.backtest.cli import run_cli
from app.backtest.io import load_historical_contexts


def _rows():
    rows=[]
    closes=[100]*14+[99.5,99,98.5,98,97.5,97,98,99,100,101,102]
    for i,c in enumerate(closes):
        rows.append({
            "timestamp":f"2026-01-01T00:{i:02d}:00Z","symbol":"BTC","timeframe":"5m",
            "open":c,"high":c+1,"low":c-1,"close":c,"volume":1000,"funding_rate":0,
            "open_interest_usd":100000,"volume_24h_usd":200000,"htf_regime_aligned":True,
        })
    return rows


def test_jsonl_loader_validates_pit_context(tmp_path:Path):
    p=tmp_path/"bars.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in _rows())+"\n",encoding="utf-8")
    rows=load_historical_contexts(p)
    assert len(rows)==25
    assert rows[0].bar.symbol=="BTC"
    assert rows[0].open_interest_usd==100000
    assert rows[0].volume_24h_usd==200000
    assert rows[0].htf_regime_aligned is True


def test_loader_fails_closed_on_missing_required_context(tmp_path:Path):
    row=_rows()[0];row.pop("open_interest_usd")
    p=tmp_path/"bad.jsonl";p.write_text(json.dumps(row)+"\n",encoding="utf-8")
    try:load_historical_contexts(p)
    except ValueError as exc:assert "open_interest_usd" in str(exc)
    else:raise AssertionError("missing PIT OI must fail closed")


def test_cli_runs_locked_baseline_and_persists_research_only_result(tmp_path:Path):
    dataset=tmp_path/"bars.jsonl";dataset.write_text("\n".join(json.dumps(x) for x in _rows())+"\n",encoding="utf-8")
    out=tmp_path/"results"
    assert run_cli(["--dataset",str(dataset),"--output-dir",str(out),"--fee-bps","0","--slippage-bps","0"])==0
    files=list(out.glob("*.json"));assert len(files)==1
    result=json.loads(files[0].read_text(encoding="utf-8"))
    assert result["mode"]=="RESEARCH_ONLY_HISTORICAL_BACKTEST"
    assert result["strategy"]["name"]=="LOCKED_PERP_MICRO_BASELINE"
    assert result["strategy"]["min_open_interest_usd"]==75000
    assert result["strategy"]["min_volume_24h_usd"]==150000
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False
