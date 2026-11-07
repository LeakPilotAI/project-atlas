"""Read-only inventory of native Hyperliquid PAPER prerequisites; never grants acceptance."""
from pathlib import Path

ROOT = Path('D:/AtlasCustody')

def inspect(*, root=ROOT):
    parent = Path(root)
    ordinary = lambda p: p.is_dir() and not p.is_symlink() and not p.is_junction()
    # Enumerate names only; do not open or adopt existing financial data.
    children = sorted(p.name for p in parent.iterdir() if ordinary(p)) if ordinary(parent) else []
    # Presence of a directory is not authenticated native account inception.
    return {'schema':'ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1',
            'custody_parent_present':ordinary(parent),
            'custody_child_names':children,
            'hyperliquid_native_account_inception':'NOT_INDEPENDENTLY_VERIFIED',
            'provider_rights_and_current_market_data':'NOT_INDEPENDENTLY_VERIFIED',
            'native_writer_ownership':'NOT_INDEPENDENTLY_VERIFIED',
            'paper_startup_authorized':False,'live_trading_authorized':False,
            'reason':'NATIVE_ACCOUNT_PROVIDER_AND_OWNER_PROOF_REQUIRED'}
