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

from app.services.paper_capacity_envelope import assess_multi_store_envelope


def complete_stores():
    return {name: {"capacity": 128, "used": 10, "planned": 20, "shutdown_reserve": 5}
            for name in ("GLOBAL", "QUALITY_DIPS", "HYPERLIQUID", "PERP_ORDERS", "REPORTS")}


def test_complete_multi_store_envelope_remains_non_authoritative():
    result = assess_multi_store_envelope(complete_stores())
    assert result["fits_declared_envelope"] is True
    assert result["operational_admission"] is False
    assert result["native_load_verified"] is False
    assert len(result["stores"]) == 5


@pytest.mark.parametrize("failed_store", ["GLOBAL", "QUALITY_DIPS", "HYPERLIQUID", "PERP_ORDERS", "REPORTS"])
def test_any_single_store_capacity_shortfall_vetoes_all(failed_store):
    stores = complete_stores()
    stores[failed_store]["used"] = 125
    result = assess_multi_store_envelope(stores)
    assert not result["fits_declared_envelope"]
    assert not result["stores"][failed_store]["fits_declared_envelope"]


@pytest.mark.parametrize("damage", ["missing", "extra", "wrong_fields", "invalid_value"])
def test_incomplete_or_invalid_store_envelopes_refuse(damage):
    stores = complete_stores()
    if damage == "missing": del stores["REPORTS"]
    elif damage == "extra": stores["UNREVIEWED"] = stores["GLOBAL"].copy()
    elif damage == "wrong_fields": del stores["GLOBAL"]["shutdown_reserve"]
    else: stores["GLOBAL"]["used"] = None
    with pytest.raises(ValueError, match="CAPACITY_ENVELOPE"):
        assess_multi_store_envelope(stores)
