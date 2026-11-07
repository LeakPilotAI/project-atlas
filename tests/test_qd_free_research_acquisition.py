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
    class Bundle:
        def __init__(self, **kwargs): pass
        def load(self, symbol):
            assert symbol == "MSFT"
            return {"paper_eligible": False, "receipts": [{"id": 1}], "bars": [1,2],
                    "fundamentals": {"revenue": 1},
                    "refusals": ["NO_THREE_EXPLICIT_ACCEPTED_NORMALIZATION_ESTIMATES"]}
    result = probe.inspect_free_research(
        symbol="MSFT", contact="ProjectAtlas/1.0 operator@realmail.org",
        credentials_path=Path("unused"), client_factory=Client, bundle_factory=Bundle)
    assert result["completed_daily_bar_count"] == 2
    assert result["normalization_estimates_accepted"] is False
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
