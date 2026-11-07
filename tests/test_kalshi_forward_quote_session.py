import asyncio
import pytest
from scripts.kalshi_forward_quote_session import run


def test_bounded_session_collects_twice_and_analyzes():
    calls = []
    async def collector():
        calls.append('collect')
        return {'records_written': 1, 'provider_errors': []}
    async def sleep(seconds):
        calls.append(seconds)
    def analyzer():
        calls.append('analyze')
        return {'paired_count': 1}
    result = asyncio.run(run(collector=collector, analyzer=analyzer, sleep=sleep))
    assert calls == ['collect', 60.0, 'collect', 'analyze']
    assert result['cycles_completed'] == 2
    assert result['orders_placed'] == 0
    assert result['unattended_runtime_started'] is False


def test_provider_error_stops_session():
    async def collector():
        return {'provider_errors': ['unavailable']}
    result = asyncio.run(run(collector=collector, analyzer=lambda: {'paired_count': 0}))
    assert result['cycles_completed'] == 1


@pytest.mark.parametrize('cycles,interval', [(0, 60), (4, 60), (2, 0), (2, 301)])
def test_unbounded_session_refused(cycles, interval):
    with pytest.raises(ValueError):
        asyncio.run(run(cycles=cycles, interval_seconds=interval))