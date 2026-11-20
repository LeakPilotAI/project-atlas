import json
from pathlib import Path

import app.backtest.holdout_evaluation as mod


def _freeze():
    return {
        "status":"DEVELOPMENT_DECISIONS_FROZEN",
        "development_result":"FAILED_NEGATIVE",
        "parameters_frozen":True,
        "same_window_optimization_allowed":False,
        "thresholds":{
            "min_open_interest_usd":75000.0,"min_volume_24h_usd":150000.0,
            "rsi_long_max":28.0,"rsi_short_min":72.0,"min_extension_pct":1.4,
            "max_extension_pct":3.5,"min_rr":1.8,"htf_alignment_enabled":True,
            "rsi_period":14,"extension_lookback_bars":20,
        },
    }


def test_holdout_run_requires_green_audit(tmp_path,monkeypatch):
    freeze=tmp_path/"freeze.json";freeze.write_text(json.dumps(_freeze()),encoding="utf-8")
    monkeypatch.setattr(mod,"audit_representative_bundle",lambda *a,**k:{"ready_for_locked_baseline_batch":False,"audit_id":"bad"})
    try:
        mod.run(freeze_path=freeze,canonical_root=tmp_path,output_root=tmp_path/"runs",summary_path=tmp_path/"summary.json")
    except RuntimeError as exc:
        assert "source audit is not GREEN" in str(exc)
    else:
        raise AssertionError("holdout evaluation must fail closed on non-GREEN source audit")


def test_holdout_run_persists_exact_three_symbol_results(tmp_path,monkeypatch):
    freeze=tmp_path/"freeze.json";freeze.write_text(json.dumps(_freeze()),encoding="utf-8")
    canonical=tmp_path/"canonical";canonical.mkdir()
    for symbol in mod.SYMBOLS:(canonical/f"{symbol}-5m.csv").write_text("stub",encoding="utf-8")
    monkeypatch.setattr(mod,"audit_representative_bundle",lambda *a,**k:{"ready_for_locked_baseline_batch":True,"audit_id":"audit-green"})
    monkeypatch.setattr(mod,"load_historical_contexts",lambda path:[type("C",(),{"bar":type("B",(),{"symbol":path.name.split('-')[0]})()})()])
    monkeypatch.setattr(mod,"_signal_fn",lambda contexts,thresholds:object())
    counts={"BTC":11,"ETH":13,"SOL":17};totals={"BTC":1.1,"ETH":-2.6,"SOL":3.4}
    def fake_backtest(bars,signal_fn,assumptions):
        symbol=bars[0].symbol
        return {"run_id":f"run-{symbol}","metrics":{"trade_count":counts[symbol],"total_r":totals[symbol],"expectancy_r":totals[symbol]/counts[symbol]}}
    monkeypatch.setattr(mod,"run_historical_backtest",fake_backtest)
    def fake_persist(result,output_dir):
        output_dir.mkdir(parents=True,exist_ok=True);path=output_dir/f"{result['run_id']}.json";path.write_text("{}",encoding="utf-8");return path
    monkeypatch.setattr(mod,"persist_backtest_result",fake_persist)
    summary=tmp_path/"summary.json"
    result=mod.run(freeze_path=freeze,canonical_root=canonical,output_root=tmp_path/"runs",summary_path=summary)
    assert result["status"]=="UNTOUCHED_HOLDOUT_EVALUATION_COMPLETE"
    assert result["source_audit_green"] is True
    assert result["source_audit_id"]=="audit-green"
    assert result["parameters_frozen"] is True
    assert result["threshold_retuning_allowed"] is False
    assert result["production_strategy_modified"] is False
    assert result["live_capital_allowed"] is False
    assert [x["symbol"] for x in result["runs"]]==["BTC","ETH","SOL"]
    assert result["aggregate"]["trade_count"]==41
    assert abs(result["aggregate"]["total_r"]-1.9)<1e-12
    assert abs(result["aggregate"]["expectancy_r"]-(1.9/41))<1e-12
    assert summary.is_file()
