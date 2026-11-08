"""Classify a verified observation session without promoting research to trading evidence."""
from scripts.observation_runtime.desktop_observation import Session


def audit_session(path):
    session = Session.__new__(Session)
    session.root = path
    session.test = True
    history = session.history()
    if len(history['sessions']) != 1 or history['sessions'][0]['status'] != 'CLOSED':
        raise ValueError('OBSERVATION_SESSION_NOT_CLOSED')
    records = history['sessions'][0]['records']
    kinds = [row['kind'] for row in records]
    if kinds.count('SESSION_START') != 1 or kinds.count('SESSION_STOP') != 1 or kinds.count('DATA_COLLECTION_STOP') != 1:
        raise ValueError('OBSERVATION_SESSION_INCOMPLETE')
    iex = [row['value'] for row in records if row['kind'] == 'ALPACA_IEX_SESSION_RESULT']
    perps = [row['value'] for row in records if row['kind'] == 'HYPERLIQUID_RESEARCH']
    if len(iex) > 1 or len(perps) > 1:
        raise ValueError('OBSERVATION_PROVIDER_RESULT_AMBIGUOUS')
    equity = iex[0] if iex else {}
    perp = perps[0] if perps else {}
    return {
        'schema': 'ATLAS_RETAINED_PROVIDER_EVIDENCE_AUDIT_V1',
        'session_status': 'CLOSED',
        'archive_integrity': 'VERIFIED_LOCAL_HASH_CHAIN_NOT_PROVIDER_AUTHORITY',
        'alpaca_authenticated': equity.get('authenticated') is True,
        'alpaca_subscribed': equity.get('subscribed') is True,
        'alpaca_fresh_quote_received': equity.get('fresh_quote_observed_during_connection') is True,
        'hyperliquid_research_retained': bool(perp),
        'hyperliquid_symbols': sorted(perp.get('books', {})) if type(perp.get('books', {})) is dict else [],
        'fresh_executable_prices': False,
        'provider_rights_verified': False,
        'financial_execution_authorized': False,
        'paper_startup_authorized': False,
    }

