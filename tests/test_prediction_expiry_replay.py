"""Static synthetic records only; no provider, runtime journal or orders."""
from datetime import datetime, timezone

import pytest
from app.prediction.paper_engine import PredictionPaperError
from test_prediction_accounting_completeness import closed, journal, opened, write_rows

AFTER_EVENT = datetime(2026, 10, 21, 21, tzinfo=timezone.utc)


@pytest.mark.parametrize('next_position', [False, True])
def test_closed_trade_cannot_be_expired_from_stale_open_record(tmp_path, next_position):
    j = journal(tmp_path)
    original = opened()
    rows = [original, closed()]
    if next_position:
        rows.append(opened('next'))
    write_rows(j, rows)
    before = j.journal_path.read_bytes()
    with pytest.raises(PredictionPaperError, match='closed'):
        j.expire_unclosed(opened=original, now=AFTER_EVENT)
    assert j.journal_path.read_bytes() == before
    assert j.open_trade() == (rows[-1] if next_position else None)


def test_valid_expiry_is_idempotent_and_has_no_fill_or_pnl(tmp_path):
    j = journal(tmp_path)
    original = opened()
    write_rows(j, [original])
    expired = j.expire_unclosed(opened=original, now=AFTER_EVENT)
    committed = j.journal_path.read_bytes()
    assert expired['event'] == 'expired_unclosed'
    assert expired.get('actual_exit_price') is None
    assert expired.get('net_pnl_dollars') is None
    assert j.expire_unclosed(opened=original, now=AFTER_EVENT) == expired
    assert j.journal_path.read_bytes() == committed
    assert j.open_trade() is None
