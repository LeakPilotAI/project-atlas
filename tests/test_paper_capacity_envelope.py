"""Offline conservative arithmetic, not F11 native acceptance."""
import pytest
from app.services.paper_capacity_envelope import assess_bounded_capacity


def test_exact_headroom_still_requires_independent_acceptance():
    result = assess_bounded_capacity(capacity=128, used=100, planned=24, shutdown_reserve=4)
    assert result['fits_declared_envelope'] is True
    assert result['remaining'] == result['required'] == 28
    assert result['operational_admission'] is False
    assert result['native_load_verified'] is False


@pytest.mark.parametrize('used,planned,reserve', [(100,25,4), (128,0,1), (0,128,1)])
def test_exhaustion_refuses_declared_envelope(used, planned, reserve):
    assert not assess_bounded_capacity(capacity=128, used=used, planned=planned,
                                       shutdown_reserve=reserve)['fits_declared_envelope']


@pytest.mark.parametrize('values', [(-1,0,0,1), (128,-1,0,1), (128,0,-1,1),
                                    (128,0,0,0), (128,129,0,1), (0,0,0,1),
                                    (128,0,1.5,1), (True,0,1,1)])
def test_invalid_envelopes_fail_closed(values):
    with pytest.raises(ValueError, match='CAPACITY_ENVELOPE'):
        assess_bounded_capacity(capacity=values[0], used=values[1],
                                planned=values[2], shutdown_reserve=values[3])
