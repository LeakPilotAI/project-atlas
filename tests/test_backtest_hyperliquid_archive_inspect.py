from pathlib import Path
import csv
import pytest
from app.backtest.hyperliquid_archive_inspect import inspect_file


def _write(path:Path,header:list[str],rows:list[list[str]])->None:
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)


def test_inspector_detects_required_pit_context_for_all_targets(tmp_path:Path):
    p=tmp_path/"asset_ctxs.csv"
    header=["timestamp","coin","openInterest","dayNtlVlm","markPx"]
    _write(p,header,[
        ["1719792000000","BTC","100","1000","60000"],
        ["1719792000000","ETH","200","2000","3000"],
        ["1719792000000","SOL","300","3000","140"],
    ])
    out=inspect_file(p)
    assert out["detected"]["open_interest"]=="openInterest"
    assert out["detected"]["day_notional_volume"]=="dayNtlVlm"
    assert out["pit_context_candidate"] is True
    assert out["normalization_allowed"] is True
    assert out["live_capital_allowed"] is False


def test_inspector_fails_closed_when_volume_missing(tmp_path:Path):
    p=tmp_path/"asset_ctxs.csv"
    _write(p,["timestamp","coin","openInterest"],[
        ["1","BTC","100"],["1","ETH","200"],["1","SOL","300"]])
    out=inspect_file(p)
    assert out["detected"]["day_notional_volume"] is None
    assert out["pit_context_candidate"] is False
    assert out["normalization_allowed"] is False


def test_inspector_requires_all_locked_symbols(tmp_path:Path):
    p=tmp_path/"asset_ctxs.csv"
    _write(p,["timestamp","coin","openInterest","dayNtlVlm"],[
        ["1","BTC","100","1000"],["1","ETH","200","2000"]])
    out=inspect_file(p)
    assert out["target_sample_counts"]["SOL"]==0
    assert out["normalization_allowed"] is False


def test_inspector_rejects_headerless_archive(tmp_path:Path):
    p=tmp_path/"empty.csv";p.write_text("",encoding="utf-8")
    with pytest.raises(ValueError,match="no header"):inspect_file(p)
