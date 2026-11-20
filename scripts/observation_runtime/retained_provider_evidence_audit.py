"""Classify a verified observation session without promoting research to trading evidence."""
import argparse
import json
from pathlib import Path
from scripts.observation_runtime.desktop_observation import Session, REPO


def audit_session(path):
    path = Path(path).absolute()
    if (path.parent != REPO / "logs/observation-only" or not path.name.startswith("session-")
            or any(part.is_symlink() or part.is_junction() for part in (path, *path.parents))):
        raise ValueError("OBSERVATION_SESSION_ROOT_REFUSED")
    session = Session.__new__(Session)
    session.root = path
    session.test = True
    history = session.history()
    if len(history['sessions']) != 1 or history['sessions'][0]['status'] != 'CLOSED':
        raise ValueError('OBSERVATION_SESSION_NOT_CLOSED')
    records = history['sessions'][0]['records']
    kinds = [row['kind'] for row in records]
    allowed = {'SESSION_START', 'SESSION_STOP', 'DATA_ONLY_AUTHORIZATION',
               'ALPACA_IEX_STATE_CHANGE', 'ALPACA_IEX_SESSION_RESULT',
               'ALPACA_IEX_REFUSED', 'HYPERLIQUID_PUBLIC_RESPONSE',
               'HYPERLIQUID_RESEARCH', 'HYPERLIQUID_REFUSED',
               'DATA_COLLECTION_STOP'}
    if any(kind not in allowed for kind in kinds):
        raise ValueError('OBSERVATION_UNEXPECTED_EVENT_KIND')
    if (records and records[0]['value'].get('scope') != 'DISPOSABLE_TEST'
            and kinds.count('DATA_ONLY_AUTHORIZATION') != 1):
        raise ValueError('OBSERVATION_DATA_ONLY_SCOPE_UNVERIFIED')
    if (not records or kinds[0] != 'SESSION_START' or kinds[-1] != 'SESSION_STOP'
            or kinds.count('SESSION_START') != 1 or kinds.count('SESSION_STOP') != 1
            or kinds.count('DATA_COLLECTION_STOP') != 1
            or kinds.index('DATA_COLLECTION_STOP') != len(kinds) - 2):
        raise ValueError('OBSERVATION_SESSION_INCOMPLETE')
    iex = [row['value'] for row in records if row['kind'] == 'ALPACA_IEX_SESSION_RESULT']
    perps = [row['value'] for row in records if row['kind'] == 'HYPERLIQUID_RESEARCH']
    iex_refused = [row['value'] for row in records if row['kind'] == 'ALPACA_IEX_REFUSED']
    perp_refused = [row['value'] for row in records if row['kind'] == 'HYPERLIQUID_REFUSED']
    if (len(iex) + len(iex_refused) != 1 or len(perps) + len(perp_refused) != 1
            or any(row.get('financial_execution_authorized') is not False for row in iex_refused)
            or any(row.get('financial_execution_authorized') is True for row in perp_refused)):
        raise ValueError('OBSERVATION_PROVIDER_RESULT_AMBIGUOUS')
    equity = iex[0] if iex else {}
    perp = perps[0] if perps else {}
    if (type(equity) is not dict or type(perp) is not dict
            or (perps and (perp.get('financial_execution_authorized') is not False
                           or sorted(perp.get('books', {})) != ['BTC', 'ETH', 'SOL']))
            or records[-2]['value'].get('financial_writers') is not False
            or records[-1]['value'].get('financial_writers') is not False):
        raise ValueError('OBSERVATION_PROVIDER_EVIDENCE_INCOMPLETE_OR_UNSAFE')
    return {
        'schema': 'ATLAS_RETAINED_PROVIDER_EVIDENCE_AUDIT_V1',
        'session_status': 'CLOSED',
        'archive_integrity': 'VERIFIED_LOCAL_HASH_CHAIN_NOT_PROVIDER_AUTHORITY',
        'alpaca_provider_result': 'REFUSED' if iex_refused else 'RETAINED',
        'hyperliquid_provider_result': 'REFUSED' if perp_refused else 'RETAINED',
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

def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit a closed local observation session; never authorize trading.")
    parser.add_argument("--session", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit_session(args.session)
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({"schema": "ATLAS_RETAINED_PROVIDER_EVIDENCE_AUDIT_V1",
                          "status": "REFUSED", "reason": "SESSION_EVIDENCE_UNVERIFIED",
                          "financial_execution_authorized": False,
                          "paper_startup_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
