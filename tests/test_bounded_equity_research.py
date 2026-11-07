from scripts.observation_runtime.bounded_equity_research import run_cycles
import pytest


def test_automatic_bounded_batches():
    calls = []
    def runner(**kwargs):
        calls.append(kwargs)
        return {'status': 'RESEARCH_FINALIZED', 'cursor_advanced': True, 'completed': 2}
    result = run_cycles(contact='contact', cycles=3, batch_size=2, runner=runner)
    assert result['completed'] == 6 and len(calls) == 3
    assert all(call['finalize'] is True for call in calls)
    assert result['paper_execution_authorized'] is False


def test_stops_immediately_on_blocked_provider():
    calls = []
    def runner(**kwargs):
        calls.append(kwargs)
        return {'status': 'BLOCKED', 'cursor_advanced': False}
    result = run_cycles(contact='contact', cycles=4, runner=runner)
    assert result['status'] == 'BLOCKED' and result['completed'] == 0 and len(calls) == 1


@pytest.mark.parametrize('cycles,batch_size', [(0, 1), (11, 1), (1, 0), (1, 3)])
def test_refuses_unbounded_request(cycles, batch_size):
    with pytest.raises(ValueError):
        run_cycles(contact='contact', cycles=cycles, batch_size=batch_size)