"""Actual evaluator -> temporary journal -> dashboard script, with no services."""
import json
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest
from app.api import prediction as api
from app.prediction.paper_engine import evaluate_pre_event_repricing
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_prediction_history_time import NOW, history
from test_prediction_history_window import book
from test_prediction_paper_automation import _journal, _market


@pytest.mark.parametrize('case', ['context', 'future', 'window', 'legacy'])
def test_evaluator_journal_dashboard_handoff(tmp_path, monkeypatch, case):
    root = Path(__file__).resolve().parents[1]
    rows = history()
    start, end = int(NOW.timestamp())-360, int(NOW.timestamp())
    if case == 'context':
        context = dict(rows[0], end_period_ts=start-1)
        rows.insert(0, context)
        expected = ['6 of 7', '1 context', 'Event-time order checked (not freshness)', 'Requested window:']
    elif case == 'future':
        rows[-1]['end_period_ts'] = end+1
        expected = ['0 of 6', 'Event-time evidence refused', 'Requested window refused']
    elif case == 'window':
        end -= 120
        expected = ['0 of 6', 'Requested window refused']
    else:
        expected = ['Unknown of Unknown', 'Unknown event-time evidence', 'Requested window unspecified']
    candidate = evaluate_pre_event_repricing(market=_market(NOW), orderbook=book(), candles=rows,
                 side='YES', quantity=Decimal(10), now=NOW, history_start_ts=start, history_end_ts=end)
    if case == 'legacy':
        candidate.pop('history')
    journal = _journal(tmp_path)
    journal.log_candidate(candidate)
    monkeypatch.setattr(api, 'prediction_paper_journal', journal)
    application = FastAPI()
    application.include_router(api.router)
    response = TestClient(application).get('/api/prediction/paper/candidates?limit=10')
    assert response.status_code == 200
    snapshot = response.json()
    assert len(snapshot['candidates']) == 1
    assert journal.open_trade() is None
    node = Path('C:/Program Files/nodejs/node.exe')
    result = subprocess.run([str(node), str(root/'tests/prediction_history_handoff.cjs'),
                             str(root/'backend/app/static/prediction_paper.html')],
                            input=json.dumps({'snapshot': snapshot, 'expected': expected}),
                            text=True, capture_output=True, timeout=15, cwd=tmp_path, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['synthetic_only'] is True
