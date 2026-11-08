from pathlib import Path
import pytest
from scripts.observation_runtime.retained_provider_evidence_audit import audit_session
from scripts.observation_runtime.desktop_observation import Session, REPO
import uuid


def test_closed_local_session_is_never_promoted():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('ALPACA_IEX_SESSION_RESULT', {'authenticated': True, 'subscribed': True, 'fresh_quote_observed_during_connection': True})
    s.append('HYPERLIQUID_RESEARCH', {'books': {'BTC': {}, 'ETH': {}, 'SOL': {}}, 'financial_execution_authorized': False})
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


def test_missing_provider_result_refused():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    s.append('SESSION_STOP', {'financial_writers': False})
    with pytest.raises(ValueError, match='OBSERVATION_PROVIDER_RESULT_AMBIGUOUS'):
        audit_session(root)


def test_foreign_root_refused(tmp_path):
    with pytest.raises(ValueError, match='OBSERVATION_SESSION_ROOT_REFUSED'):
        audit_session(tmp_path)


def test_financially_unsafe_provider_result_refused():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('ALPACA_IEX_SESSION_RESULT', {'authenticated': True})
    s.append('HYPERLIQUID_RESEARCH', {'books': {'BTC': {}, 'ETH': {}, 'SOL': {}}, 'financial_execution_authorized': True})
    s.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    s.append('SESSION_STOP', {'financial_writers': False})
    with pytest.raises(ValueError, match='OBSERVATION_PROVIDER_EVIDENCE_INCOMPLETE_OR_UNSAFE'):
        audit_session(root)

def test_cli_refuses_foreign_root_without_leaking_path(capsys, tmp_path):
    from scripts.observation_runtime.retained_provider_evidence_audit import main
    assert main(['--session', str(tmp_path)]) == 2
    import json
    output = json.loads(capsys.readouterr().out)
    assert output['status'] == 'REFUSED'
    assert output['paper_startup_authorized'] is False
    assert str(tmp_path) not in str(output)


def test_cli_reports_closed_capture(capsys):
    from scripts.observation_runtime.retained_provider_evidence_audit import main
    import json
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('ALPACA_IEX_SESSION_RESULT', {'authenticated': True, 'subscribed': True})
    s.append('HYPERLIQUID_RESEARCH', {'books': {'BTC': {}, 'ETH': {}, 'SOL': {}}, 'financial_execution_authorized': False})
    s.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    s.append('SESSION_STOP', {'financial_writers': False})
    assert main(['--session', str(root)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['financial_execution_authorized'] is False
    assert output['hyperliquid_research_retained'] is True

def test_explicit_provider_refusals_are_reported_not_accepted():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('ALPACA_IEX_REFUSED', {'reason': 'DATA_UNAVAILABLE_OR_REFUSED', 'financial_execution_authorized': False})
    s.append('HYPERLIQUID_REFUSED', {'reason': 'RuntimeError'})
    s.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    s.append('SESSION_STOP', {'financial_writers': False})
    result = audit_session(root)
    assert result['alpaca_provider_result'] == 'REFUSED'
    assert result['hyperliquid_provider_result'] == 'REFUSED'
    assert result['hyperliquid_research_retained'] is False
    assert result['financial_execution_authorized'] is False

def test_unexpected_financial_event_kind_is_refused():
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    s = Session(root, test=True)
    s.append('ALPACA_IEX_SESSION_RESULT', {'authenticated': True})
    s.append('HYPERLIQUID_RESEARCH', {'books': {'BTC': {}, 'ETH': {}, 'SOL': {}}, 'financial_execution_authorized': False})
    s.append('FINANCIAL_ORDER_SUBMITTED', {'symbol': 'BTC'})
    s.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    s.append('SESSION_STOP', {'financial_writers': False})
    with pytest.raises(ValueError, match='OBSERVATION_UNEXPECTED_EVENT_KIND'):
        audit_session(root)
