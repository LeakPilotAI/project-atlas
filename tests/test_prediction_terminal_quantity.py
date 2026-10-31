"""Full-position terminal evidence cannot claim a different supplied quantity."""
import pytest
from app.prediction.paper_engine import PredictionPaperError
from test_prediction_accounting_completeness import closed, journal, opened, write_rows


@pytest.mark.parametrize('event', ['close', 'expired_unclosed'])
@pytest.mark.parametrize('quantity', ['5', '20'])
def test_different_terminal_quantity_cannot_mark_position_flat(tmp_path, event, quantity):
    j = journal(tmp_path)
    terminal = closed()
    terminal.update(event=event, quantity_contracts=quantity)
    write_rows(j, [opened(), terminal])
    before = j.journal_path.read_bytes()
    with pytest.raises(PredictionPaperError, match='quantity'):
        j.open_trade()
    assert j.journal_path.read_bytes() == before


@pytest.mark.parametrize('quantity', ['10.0', 10, 10.0])
def test_equivalent_numeric_quantity_keeps_legacy_representation(tmp_path, quantity):
    j = journal(tmp_path)
    terminal = closed()
    terminal['quantity_contracts'] = quantity
    write_rows(j, [opened(), terminal])
    before = j.journal_path.read_bytes()
    assert j.open_trade() is None
    assert j.journal_path.read_bytes() == before
