"""Offline execution-bound clock tests; no socket, writer or provider access."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.investment.alpaca_iex import IEXRefused
from test_iex_research_reference import setup


def clock_port(value):
    port, feed, _, instrument = setup()
    original = port.authority.lease

    @contextmanager
    def lease(request, now):
        with original(request, now) as accepted:
            accepted.snapshot['clock_uncertainty_seconds'] = value
            yield accepted

    port.authority = SimpleNamespace(lease=lease)
    return port, feed, instrument


@pytest.mark.parametrize('value', ['1.001', '2', '999', '-0.001'])
def test_execution_quote_refuses_outside_physical_one_second_bound(value):
    port, feed, instrument = clock_port(value)
    before = feed.snapshot()
    with pytest.raises(IEXRefused, match='CLOCK_UNCERTAINTY'):
        port.quote(instrument)
    assert feed.snapshot() == before
    assert port._issued_frame is None and port._issued_shutdown is None


@pytest.mark.parametrize('value', ['0', '0.999', '1'])
def test_accepted_bound_keeps_separate_whole_second_allowance(value):
    from decimal import Decimal
    port, _, instrument = clock_port(value)
    result = port.quote(instrument)
    assert Decimal(result['clock_uncertainty_seconds']) == Decimal(value) + 1


@pytest.mark.parametrize('route', ['next', 'observe', 'frame'])
@pytest.mark.parametrize('value', ['1.001', '2'])
def test_uncertain_clock_cannot_issue_entry_or_shutdown_observations(route, value):
    port, feed, instrument = clock_port(value)
    port.session_id = 'SYNTHETIC-CLOCK-REFUSAL'
    port.decision_reader = SimpleNamespace(read_request=lambda **kw: {
        'instrument': instrument, 'bundles': [], 'observation': None})
    before = feed.snapshot()
    with pytest.raises(IEXRefused, match='CLOCK_UNCERTAINTY'):
        if route == 'next':
            port.next(.01)
        elif route == 'observe':
            port.observe({'instrument': instrument, 'symbol': instrument['symbol']}, .1)
        else:
            port.frame(session_id=port.session_id, sequence=1, bundles=[], instrument=instrument)
    assert port._sequence == 0 and port._last_quote is None
    assert port._issued_frame is None and port._issued_shutdown is None
    assert feed.snapshot() == before
