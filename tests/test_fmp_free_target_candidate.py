from scripts.observation_runtime.fmp_free_target_candidate import assess_price_target_consensus
import pytest


def test_aggregated_consensus_never_grants_source_authority():
    row = assess_price_target_consensus([{'symbol': 'MSFT', 'targetLow': 400.0, 'targetConsensus': 500.0, 'targetHigh': 600.0}], symbol='MSFT')
    assert row['individual_analyst_estimates_authenticated'] == 0
    assert row['operational_source_accepted'] is False
    assert row['paper_fill_authorized'] is False
    assert row['live_order_authorized'] is False


@pytest.mark.parametrize('payload', [[], [{}], [{'symbol': 'AVGO'}], [{'symbol': 'MSFT', 'targetLow': -1}], [{'symbol': 'MSFT', 'targetHigh': float('nan')}], [{'symbol': 'MSFT'}, {'symbol': 'MSFT'}]])
def test_invalid_consensus_is_refused(payload):
    with pytest.raises(ValueError):
        assess_price_target_consensus(payload, symbol='MSFT')
