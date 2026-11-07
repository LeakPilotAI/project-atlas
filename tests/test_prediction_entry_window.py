"""Synthetic eligibility cannot authorize a late or ambiguous journal admission."""
from datetime import datetime, timedelta, timezone

import app.prediction.paper_engine as engine
import pytest
from app.prediction.paper_engine import PredictionPaperError
from test_prediction_accounting_completeness import evaluation, journal

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def candidate():
    return {**evaluation(), 'occurrence_datetime': (NOW+timedelta(hours=2)).isoformat(),
            'flat_deadline': (NOW+timedelta(minutes=90)).isoformat()}


@pytest.mark.parametrize('fault', ['missing-event', 'missing-flat', 'naive-event', 'naive-flat',
                                   'expired-event', 'flat-now', 'expired-flat', 'reversed', 'invalid-event', 'invalid-flat'])
def test_ineligible_commit_window_refuses_before_append(tmp_path, monkeypatch, fault):
    j = journal(tmp_path)
    value = candidate()
    monkeypatch.setattr(engine, '_now', lambda: NOW)
    if fault == 'missing-event': value.pop('occurrence_datetime')
    if fault == 'missing-flat': value.pop('flat_deadline')
    if fault == 'naive-event': value['occurrence_datetime'] = '2026-10-20T14:00:00'
    if fault == 'naive-flat': value['flat_deadline'] = '2026-10-20T13:30:00'
    if fault == 'expired-event':
        value.update(occurrence_datetime=(NOW-timedelta(minutes=30)).isoformat(),
                     flat_deadline=(NOW-timedelta(hours=1)).isoformat())
    if fault == 'flat-now': value['flat_deadline'] = NOW.isoformat()
    if fault == 'expired-flat': value['flat_deadline'] = (NOW-timedelta(microseconds=1)).isoformat()
    if fault == 'reversed': value['flat_deadline'] = (NOW+timedelta(hours=3)).isoformat()
    if fault == 'invalid-event': value['occurrence_datetime'] = 'not-an-instant'
    if fault == 'invalid-flat': value['flat_deadline'] = 'not-an-instant'
    with pytest.raises(PredictionPaperError):
        j.open_from_evaluation(value)
    assert not j.journal_path.exists()
    assert not j._intent_path(j.journal_path).exists()


def test_valid_window_records_actual_admission_clock(tmp_path, monkeypatch):
    j = journal(tmp_path)
    monkeypatch.setattr(engine, '_now', lambda: NOW)
    result = j.open_from_evaluation(candidate())
    assert result['entry_timestamp'] == NOW.isoformat()
    assert result['live_capital_allowed'] is False



def test_explicit_historical_clock_is_not_replaced_by_wall_clock(tmp_path, monkeypatch):
    j = journal(tmp_path)
    monkeypatch.setattr(engine, '_now', lambda: pytest.fail('Unexpected hidden wall clock'))
    result = j.open_from_evaluation(candidate(), now=NOW)
    assert result['entry_timestamp'] == NOW.isoformat()


def test_naive_admission_clock_refuses_before_append(tmp_path):
    j = journal(tmp_path)
    with pytest.raises(PredictionPaperError, match='clock'):
        j.open_from_evaluation(candidate(), now=NOW.replace(tzinfo=None))
    assert not j.journal_path.exists()


def test_clock_is_rechecked_after_position_read(tmp_path, monkeypatch):
    j = journal(tmp_path)
    value = candidate()
    clock = [NOW]
    original = j.open_trade

    def delayed_read():
        result = original()
        clock[0] = datetime.fromisoformat(value['flat_deadline'])
        return result

    monkeypatch.setattr(j, 'open_trade', delayed_read)
    monkeypatch.setattr(engine, '_now', lambda: clock[0])
    with pytest.raises(PredictionPaperError, match='precede'):
        j.open_from_evaluation(value)
    assert not j.journal_path.exists()


def test_strict_flat_boundary_allows_one_microsecond_before(tmp_path):
    j = journal(tmp_path)
    value = candidate()
    value['flat_deadline'] = (NOW+timedelta(microseconds=1)).isoformat()
    assert j.open_from_evaluation(value, now=NOW)['entry_timestamp'] == NOW.isoformat()



def test_explicit_z_timezone_is_supported_without_naive_fallback(tmp_path):
    j = journal(tmp_path)
    value = candidate()
    for key in ('occurrence_datetime', 'flat_deadline'):
        value[key] = value[key].replace('+00:00', 'Z')
    assert j.open_from_evaluation(value, now=NOW)['entry_timestamp'] == NOW.isoformat()
