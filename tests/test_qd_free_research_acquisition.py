from pathlib import Path
import pytest
from scripts.observation_runtime import qd_free_research_acquisition as probe


def test_missing_real_contact_refused_before_credentials(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: pytest.fail("credentials accessed"))
    with pytest.raises(ValueError, match="QD_REAL_SYMBOL_AND_SEC_CONTACT_REQUIRED"):
        probe.inspect_free_research(symbol="MSFT", contact=None, credentials_path=Path("unused"))


def test_real_data_diagnostic_does_not_promote_operational_authority(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    class Client:
        domain = "TLS_PUBLIC_PROVIDER"
        def __init__(self, **kwargs):
            assert kwargs["max_attempts"] == 12 and kwargs["seconds"] == 60
    class Metric:
        availability = False
    class Bundle:
        def __init__(self, **kwargs): pass
        def load(self, symbol):
            assert symbol == "MSFT"
            return {"paper_eligible": False, "receipts": [{"id": 1}], "bars": [1,2],
                    "valuation": {k: Metric() for k in ("target_low_price", "target_mean_price", "target_high_price")},
                    "fundamentals": {"revenue": 1},
                    "refusals": ["NO_THREE_EXPLICIT_ACCEPTED_NORMALIZATION_ESTIMATES"]}
    result = probe.inspect_free_research(
        symbol="MSFT", contact="ProjectAtlas/1.0 operator@realmail.org",
        credentials_path=Path("unused"), client_factory=Client, bundle_factory=Bundle)
    assert result["completed_daily_bar_count"] == 2
    assert result["normalization_estimates_accepted"] is False
    assert result["normalization_source_count"] == 0
    assert not any(result["explicit_target_availability"].values())
    assert result["operational_source_accepted"] is False
    assert result["paper_fill_authorized"] is False


def test_synthetic_transport_cannot_pass_as_real(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    class Client:
        domain = "SYNTHETIC"
        def __init__(self, **kwargs): pass
    with pytest.raises(ValueError, match="QD_REAL_PROVIDER_TRANSPORT_REQUIRED"):
        probe.inspect_free_research(
            symbol="MSFT", contact="ProjectAtlas/1.0 operator@realmail.org",
            credentials_path=Path("unused"), client_factory=Client)

def test_bounded_universe_deduplicates_and_never_promotes():
    from app.investment.free_research_transport import ResearchRefused
    with pytest.raises(ResearchRefused):
        probe.inspect_bounded_universe(symbols=['MSFT', 'MSFT'], contact='unused', credentials_path=None)
    with pytest.raises(ResearchRefused):
        probe.inspect_bounded_universe(symbols=['MSFT'] * 9, contact='unused', credentials_path=None)
    calls = []
    def inspect(*, symbol, **kwargs):
        calls.append(symbol)
        if symbol == 'AVGO':
            raise ResearchRefused('SOURCE_UNAVAILABLE')
        return {'schema': 'ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1', 'symbol': symbol, 'transport': 'TLS_PUBLIC_PROVIDER', 'operational_source_accepted': False, 'paper_fill_authorized': False, 'live_order_authorized': False}
    result = probe.inspect_bounded_universe(symbols=['MSFT', 'AVGO'], contact='unused',
                                            credentials_path=None, inspect=inspect)
    assert calls == ['MSFT', 'AVGO']
    assert result['results'][1]['status'] == 'REFUSED'
    assert result['operational_source_accepted'] is result['paper_fill_authorized'] is False


def test_bounded_universe_rejects_cross_symbol_or_unverified_transport():
    def impostor(*, symbol, **kwargs):
        return {'schema': 'ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1', 'symbol': 'OTHER',
                'transport': 'SYNTHETIC', 'operational_source_accepted': False,
                'paper_fill_authorized': False, 'live_order_authorized': False}
    result = probe.inspect_bounded_universe(symbols=['MSFT'], contact='unused',
                                            credentials_path=None, inspect=impostor)
    assert result['acquired_count'] == 0
    assert result['refused_count'] == 1
    assert result['results'][0]['status'] == 'REFUSED'
    assert result['paper_fill_authorized'] is False
