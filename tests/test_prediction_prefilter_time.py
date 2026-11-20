"""Cheap synthetic scan refuses ambiguous clocks before expensive data reads."""
import asyncio

import pytest
from app.prediction import prediction_paper_automation as module
from app.prediction.prediction_paper_automation import PredictionPaperAutomation
from test_prediction_history_time import NOW
from test_prediction_paper_automation import _journal, _market


@pytest.mark.parametrize('timing', ['bad', ['bad'], {'occurrence_datetime': '2026-10-02T15:00:00'},
                                  {'occurrence_datetime': '0001-01-01T00:00:00Z'}])
def test_invalid_market_timing_is_a_durable_cheap_refusal(monkeypatch, tmp_path, timing):
    journal = _journal(tmp_path)
    monkeypatch.setattr(module, 'prediction_paper_journal', journal)
    market = _market(NOW)
    market['timing'] = timing
    calls = []
    async def metadata(**kwargs):
        return {'markets': [market]}
    async def forbidden(*args, **kwargs):
        calls.append('expensive')
        raise AssertionError('invalid timing must be rejected before book/candle reads')
    monkeypatch.setattr(module.kalshi_public, 'get_markets', metadata)
    monkeypatch.setattr(module.kalshi_public, 'get_orderbook', forbidden)
    monkeypatch.setattr(module.kalshi_public, 'get_candlesticks', forbidden)
    state = asyncio.run(PredictionPaperAutomation().run_scan_once(now=NOW))
    assert state['markets_prefilter_rejected'] == 1
    assert calls == []
    rows = journal._rows(journal.candidate_path)
    assert len(rows) == 2
    assert all('MISSING_OCCURRENCE_DATETIME' in row['rejection_reasons'] for row in rows)
    assert all(row['occurrence_datetime'] is None and row['flat_deadline'] is None for row in rows)
    assert journal.open_trade() is None
