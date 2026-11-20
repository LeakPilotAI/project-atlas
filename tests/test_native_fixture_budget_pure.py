"""Resource limits tested without changing the real shared session counters."""
import pytest

from scripts.observation_runtime.native_fixture_budget import (
    BYTES,
    FILES,
    BudgetRefused,
    reserve_budget,
)


def test_valid_reservation_is_conservative_and_does_not_mutate_input():
    old={'entries':3,'charged_bytes':49152}
    assert reserve_budget(old,entries=1,size=4097,unit=4096)=={'entries':4,'charged_bytes':65536}
    assert old=={'entries':3,'charged_bytes':49152}


@pytest.mark.parametrize('usage',[None,{}, {'entries':-1,'charged_bytes':0},{'entries':True,'charged_bytes':0},{'entries':3,'charged_bytes':-1},{'entries':3,'charged_bytes':0,'extra':0},{'entries':FILES,'charged_bytes':0},{'entries':FILES+1,'charged_bytes':0},{'entries':3,'charged_bytes':BYTES}])
def test_missing_corrupt_or_exhausted_reservation_refuses(usage):
    with pytest.raises(BudgetRefused):reserve_budget(usage,entries=0,size=1,unit=4096)


@pytest.mark.parametrize('entries,size,unit',[(-1,0,4096),(2,0,4096),(False,0,4096),(0,-1,4096),(0,1024*1024+1,4096),(0,0,1000)])
def test_invalid_request_cannot_decrease_or_bypass_budget(entries,size,unit):
    with pytest.raises(BudgetRefused):reserve_budget({'entries':3,'charged_bytes':49152},entries=entries,size=size,unit=unit)
