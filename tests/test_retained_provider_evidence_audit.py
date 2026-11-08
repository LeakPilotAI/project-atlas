from pathlib import Path
import pytest
from scripts.observation_runtime.retained_provider_evidence_audit import audit_session
from scripts.observation_runtime.desktop_observation import Session, REPO
import uuid


def test_closed_local_session_is_never_promoted():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('ALPACA_IEX_SESSION_RESULT', {'authenticated': True, 'subscribed': True, 'fresh_quote_observed_during_connection': True})
    s.append('HYPERLIQUID_RESEARCH', {'books': {'BTC': {}, 'ETH': {}, 'SOL': {}}})
    s.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    s.append('SESSION_STOP', {'financial_writers': False})
    result = audit_session(root)
    assert result['alpaca_fresh_quote_received'] is True
    assert result['hyperliquid_symbols'] == ['BTC', 'ETH', 'SOL']
    assert result['fresh_executable_prices'] is False
    assert result['provider_rights_verified'] is False
    assert result['paper_startup_authorized'] is False


def test_incomplete_session_refused():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    Session(root, test=True)
    with pytest.raises(ValueError, match='OBSERVATION_SESSION_NOT_CLOSED'):
        audit_session(root)

