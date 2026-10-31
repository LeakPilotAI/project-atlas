"""Versioned unified control records over the same handle-bound journal protocol."""
from app.services.paper_financial_replay import text
from app.services.unified_portfolio_custody import portfolio_transition

try:
    from scripts.volume_inspector.resting_order_store import RestingOrderStore
except ModuleNotFoundError:
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('unified_order_primitives', Path(__file__).with_name('resting_order_store.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    RestingOrderStore = module.RestingOrderStore


class PortfolioControlStore(RestingOrderStore):
    PIN_TEST = 'UNIFIED_PORTFOLIO_TEST_PIN_V1'
    PIN_OP = 'UNIFIED_PORTFOLIO_OP_PIN_V1'
    SCOPE_SCHEMA = 'UNIFIED_PORTFOLIO_SCOPE_V1'
    RECORD_SCHEMA = 'UNIFIED_PORTFOLIO_RECORD_V1'
    ACK_SCHEMA = 'UNIFIED_PORTFOLIO_ACK_V1'
    LEAF = 'portfolio'
    fold = staticmethod(portfolio_transition)

    def _validate_manifest(self, manifest):
        if (type(manifest) is not dict or set(manifest) != {'schema', 'epoch', 'opened_at', 'accounts', 'policy_digest', 'roster_digest'}
                or manifest['schema'] != 'UNIFIED_CONTROL_BINDING_V1' or type(manifest['opened_at']) is not int
                or set(manifest['accounts']) != {'QUALITY_DIPS', 'HYPERLIQUID'}):
            raise ValueError('UNIFIED_CONTROL_ACCOUNT_AND_POLICY_BINDING_REQUIRED')
        for key in ('epoch', 'policy_digest', 'roster_digest'): text(manifest[key])

    def _initial(self):
        return {'revision': 0, 'last_clock': self.manifest['opened_at'], 'session': None,
                'entry_closed': True, 'sessions': [], 'operations': {}, 'finalized': None}
