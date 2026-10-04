import csv,json
from pathlib import Path
from app.backtest.io import load_historical_contexts
from app.backtest.hyperliquid_import import HistoricalMarketContext,normalize_hyperliquid_history,write_canonical_csv


def _row(trend="UP"):
    return {"timestamp":"2026-01-01T00:00:00Z","symbol":"BTC","timeframe":"5m","open":100,"high":101,"low":99,"close":100,"volume":10,"funding_rate":0,"open_interest_usd":80000,"volume_24h_usd":200000,"htf_trend":trend}


def test_loader_accepts_explicit_htf_trend_without_legacy_boolean(tmp_path:Path):
    p=tmp_path/"v2.jsonl";p.write_text(json.dumps(_row())+"\n",encoding="utf-8")
    rows=load_historical_contexts(p)
    assert rows[0].htf_trend=="UP";assert rows[0].htf_regime_aligned is None


def test_loader_rejects_invalid_explicit_htf_trend(tmp_path:Path):
    p=tmp_path/"bad.jsonl";p.write_text(json.dumps(_row("SIDEWAYS"))+"\n",encoding="utf-8")
    try:load_historical_contexts(p)
    except ValueError as exc:assert "htf_trend" in str(exc)
    else:raise AssertionError("invalid trend must fail closed")


def test_importer_writes_v2_trend_column_when_explicit_trend_supplied(tmp_path:Path):
    ts=1767225600000
    rows=normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=[{"time":ts,"open":100,"high":101,"low":99,"close":100,"volume":10}],funding_history=[],historical_context=[HistoricalMarketContext("2026-01-01T00:00:00Z",80000,200000,None,"DOWN")])
    p=write_canonical_csv(rows,tmp_path/"BTC-5m.csv")
    with p.open(newline="",encoding="utf-8") as fh:data=list(csv.DictReader(fh))
    assert data[0]["htf_trend"]=="DOWN";assert "htf_regime_aligned" not in data[0]
    loaded=load_historical_contexts(p);assert loaded[0].htf_trend=="DOWN"


def test_loader_keeps_legacy_boolean_fixture_compatibility(tmp_path:Path):
    row=_row();row.pop("htf_trend");row["htf_regime_aligned"]=True
    p=tmp_path/"legacy.jsonl";p.write_text(json.dumps(row)+"\n",encoding="utf-8")
    loaded=load_historical_contexts(p);assert loaded[0].htf_regime_aligned is True;assert loaded[0].htf_trend is None
