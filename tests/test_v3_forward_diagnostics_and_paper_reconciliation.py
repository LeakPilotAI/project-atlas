import json
from datetime import datetime, timedelta, timezone

from app.investment.quality_dips_v3_forward_readiness import forward_diagnostics
from app.services import perp_paper_observability as obs


def test_forward_diagnostics_reports_daily_symbol_and_state_mix(tmp_path):
    path=tmp_path/"v3.jsonl"
    rows=[
        {"timestamp":"2026-09-18T12:00:00+00:00","symbol":"MSFT","patient_state":"WATCH"},
        {"timestamp":"2026-09-18T13:00:00+00:00","symbol":"MSFT","patient_state":"ACCUMULATION"},
        {"timestamp":"2026-09-19T12:00:00+00:00","symbol":"NVDA","patient_state":"DEEP_VALUE"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows)+"\n",encoding="utf-8")
    out=forward_diagnostics(path)
    assert out["evaluations_per_day"]["2026-09-18"] == 2
    assert out["top_symbols"]["MSFT"] == 2
    assert out["non_watch_evaluations"] == 2
    assert out["non_watch_rate"] == 0.6667


def test_reconciliation_flags_duplicate_fill_instance(tmp_path, monkeypatch):
    journal=tmp_path/"journal.jsonl"
    pending=tmp_path/"pending.jsonl"
    journal.write_text(
        json.dumps({"event":"open","trade_id":"t1","source":obs.SOURCE})+"\n"+
        json.dumps({"event":"close","trade_id":"t1"})+"\n",
        encoding="utf-8",
    )
    pending.write_text(
        json.dumps({"event":"filled","setup_instance_id":"x"})+"\n"+
        json.dumps({"event":"filled","setup_instance_id":"x"})+"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(obs,"JOURNAL_PATH",journal)
    monkeypatch.setattr(obs,"PENDING_EVENT_PATH",pending)
    out=obs.reconciliation_summary()
    assert out["duplicate_fill_count"] == 1
    assert out["reconciliation_ok"] is False
