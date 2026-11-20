"""Research plans cannot propagate nonfinite source prices or sizing inputs."""
import pytest
from app.trading_core.models import Side
from app.trading_core.perp_manual_planner import build_manual_perp_plan


@pytest.mark.parametrize('field', ['reference_price', 'volatility_pct', 'target_rr', 'secondary_rr'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_source_inputs_refuse_before_a_plan_exists(field, value):
    request = {'symbol': 'BTC', 'side': Side.LONG, 'reference_price': 100,
               'hyperliquid_symbols': ['BTC'], 'volatility_pct': 1.0, field: value}
    with pytest.raises(ValueError): build_manual_perp_plan(**request)
