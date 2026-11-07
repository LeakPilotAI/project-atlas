from datetime import UTC, datetime
import pytest
from scripts.observation_runtime.qd_explicit_valuation_review import review_estimates

NOW = datetime(2026, 11, 7, tzinfo=UTC)

def doc(values=(300, 400, 500)):
    return {"schema": "QD_EXPLICIT_VALUATION_REVIEW_V1", "symbol": "MSFT",
            "estimates": [{"value": value, "provenance": "ANALYST_CONSENSUS",
                           "as_of": "2026-11-06", "source_url": f"https://research{i}.org/msft",
                           "source_name": f"Research {i}"}
                          for i, value in enumerate(values)]}

def test_three_explicit_independent_review_sources_still_not_authority():
    result = review_estimates(doc(), now=NOW)
    assert result["structural_window_complete"] and not result["window_complete"]
    assert result["base"] == 400
    assert result["operational_source_accepted"] is False
    assert result["paper_fill_authorized"] is False

def test_two_sources_do_not_fill_missing_scenario():
    result = review_estimates(doc((300, 500)), now=NOW)
    assert not result["window_complete"] and result["base"] is None

def test_duplicate_issuer_refused():
    packet = doc()
    packet["estimates"][1]["source_url"] = "https://research0.org/other"
    with pytest.raises(ValueError, match="DUPLICATE_ISSUER"):
        review_estimates(packet, now=NOW)

def test_expired_estimates_cannot_complete_window():
    packet = doc()
    packet["estimates"][0]["as_of"] = "2024-01-01"
    assert review_estimates(packet, now=NOW)["window_complete"] is False

def test_http_and_localhost_refused():
    packet = doc()
    packet["estimates"][0]["source_url"] = "http://research0.org/msft"
    with pytest.raises(ValueError, match="SOURCE_URL_REFUSED"):
        review_estimates(packet, now=NOW)


def test_distinct_declared_originating_issuer_families_can_complete_review_only():
    packet = doc()
    for i, estimate in enumerate(packet["estimates"]):
        estimate["issuer_family"] = f"issuer-{i}"
    result = review_estimates(packet, now=NOW)
    assert result["window_complete"] and result["issuer_independence_declared"]
    assert not result["independent_source_authentication"]
    assert not result["paper_fill_authorized"]


def test_overlapping_aggregators_cannot_claim_three_independent_issuers():
    packet = doc()
    for estimate in packet["estimates"]:
        estimate["issuer_family"] = "OVERLAPPING_ANALYST_CONSENSUS"
    result = review_estimates(packet, now=NOW)
    assert result["structural_window_complete"]
    assert not result["window_complete"]
    assert result["distinct_declared_issuer_families"] == 1
