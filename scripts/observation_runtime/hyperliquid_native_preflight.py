"""Read-only inventory of native Hyperliquid PAPER prerequisites; never grants acceptance."""
from pathlib import Path
import sqlite3

ROOT = Path('D:/AtlasCustody')

def inspect(*, root=ROOT, budget_path=None):
    parent = Path(root)
    ordinary = lambda p: p.is_dir() and not p.is_symlink() and not p.is_junction()
    # Enumerate names only; do not open or adopt existing financial data.
    children = sorted(p.name for p in parent.iterdir() if ordinary(p)) if ordinary(parent) else []
    # Inspect a supplied existing budget in read-only SQLite mode. Never create,
    # reset or consume a request allowance, and never infer provider rights.
    budget = 'NOT_SUPPLIED'
    if budget_path is not None:
        path = Path(budget_path)
        budget = 'UNVERIFIED'
        try:
            if path.is_file() and not path.is_symlink() and not path.is_junction():
                with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1) as db:
                    rows = db.execute('SELECT id,max_attempts,attempted FROM budget').fetchall()
                if (len(rows) == 1 and len(rows[0]) == 3
                        and all(type(x) is int for x in rows[0])
                        and rows[0][0] == 1 and 0 <= rows[0][2] <= rows[0][1]):
                    budget = 'EXISTING_LEDGER_STRUCTURE_VALID_NOT_AUTHORIZED'
        except (OSError, sqlite3.Error, ValueError):
            pass
    # Presence of a directory or budget is not authenticated account inception.
    return {'schema':'ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1',
            'custody_parent_present':ordinary(parent),
            'custody_child_names':children, 'request_budget_inventory':budget,
            'hyperliquid_native_account_inception':'NOT_INDEPENDENTLY_VERIFIED',
            'provider_rights_and_current_market_data':'NOT_INDEPENDENTLY_VERIFIED',
            'native_writer_ownership':'NOT_INDEPENDENTLY_VERIFIED',
            'paper_startup_authorized':False,'live_trading_authorized':False,
            'reason':'NATIVE_ACCOUNT_PROVIDER_AND_OWNER_PROOF_REQUIRED'}
