from scripts.observation_runtime.bounded_equity_research import run_cycles
import pytest


def test_automatic_bounded_batches():
    calls = []
    def runner(**kwargs):
        calls.append(kwargs)
        return {'schema': 'ATLAS_BROAD_RESEARCH_CYCLE_V1', 'status': 'RESEARCH_FINALIZED',
                'cursor_advanced': True, 'completed': 2, 'receipt_sha256': 'a'*64,
                'paper_execution_authorized': False, 'live_order_authorized': False}
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
@pytest.mark.parametrize('bad', [
    {'completed': True}, {'completed': 0}, {'completed': 3},
    {'receipt_sha256': 'bad'}, {'receipt_sha256': 'G'*64},
    {'schema': 'WRONG'}, {'paper_execution_authorized': True},
    {'live_order_authorized': True}, {'cursor_advanced': 1},
])
def test_automatic_runner_rejects_forged_or_invalid_finalization(bad):
    good = {'schema': 'ATLAS_BROAD_RESEARCH_CYCLE_V1', 'status': 'RESEARCH_FINALIZED',
            'cursor_advanced': True, 'completed': 2, 'receipt_sha256': 'a'*64,
            'paper_execution_authorized': False, 'live_order_authorized': False}
    result = run_cycles(contact='contact', cycles=2, batch_size=2,
                        runner=lambda **_: {**good, **bad})
    assert result == {'status': 'BLOCKED', 'completed': 0,
                      'paper_execution_authorized': False, 'live_order_authorized': False}


def test_automatic_runner_keeps_only_prior_valid_batch_count():
    calls = [0]
    def runner(**kwargs):
        calls[0] += 1
        return {'schema': 'ATLAS_BROAD_RESEARCH_CYCLE_V1', 'status': 'RESEARCH_FINALIZED',
                'cursor_advanced': True, 'completed': 2 if calls[0] == 1 else 99,
                'receipt_sha256': 'a'*64, 'paper_execution_authorized': False,
                'live_order_authorized': False}
    result = run_cycles(contact='contact', cycles=3, batch_size=2, runner=runner)
    assert result['status'] == 'BLOCKED' and result['completed'] == 2 and calls[0] == 2