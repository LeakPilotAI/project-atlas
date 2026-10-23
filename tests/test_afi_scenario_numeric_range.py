"""Conditional positive paths must not publish floating-point underflow as zero."""
import math

import pytest
from app.backtest.forecast_comparison import scenario_research
from app.backtest.forecast_evaluation import ForecastEvidenceRefused


@pytest.mark.parametrize('year', [2050,2126])
def test_unrepresentable_positive_scenario_refuses_instead_of_zero(year):
    with pytest.raises(ForecastEvidenceRefused,match='numeric range'):
        scenario_research(base_year=2026,milestones=[year],
                          annual_assumptions={'bear':-.9999999999999999,'base':0,'bull':.05})


def test_small_positive_representable_path_remains_conditional():
    result = scenario_research(base_year=2026,milestones=[2030,2040],
                               annual_assumptions={'bear':-.9999999999999999,'base':0,'bull':.05})
    for row in result['milestones']:
        assert math.isfinite(row['conditional_index']['bear'])
        assert row['conditional_index']['bear'] > 0
    assert result['probabilities'] is None and result['coverage_guarantee'] is False
    assert result['status'] == 'CONDITIONAL_SCENARIOS_NOT_FORECASTS'
