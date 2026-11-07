"""Invalid historical quote geometry cannot supply synthetic repricing evidence."""
import pytest
from test_prediction_history_time import evaluate, history


@pytest.mark.parametrize('side', ['YES', 'NO'])
@pytest.mark.parametrize('fault', ['crossed', 'high_above_one', 'high_below_close', 'low_negative', 'low_above_close'])
def test_invalid_quote_geometry_refuses_history(side, fault):
    rows = history()
    for row in rows:
        if fault == 'crossed': row['yes_bid']['close_dollars'] = '0.55'
        if fault == 'high_above_one': row['yes_bid']['high_dollars'] = '1.10'
        if fault == 'high_below_close': row['yes_bid']['high_dollars'] = '0.49'
        if fault == 'low_negative': row['yes_ask']['low_dollars'] = '-0.10'
        if fault == 'low_above_close': row['yes_ask']['low_dollars'] = '0.53'
    result = evaluate(rows, side)
    assert not result['eligible']
    assert result['history']['usable_bars'] == 0
