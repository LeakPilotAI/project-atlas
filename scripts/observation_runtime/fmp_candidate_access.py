"""FMP candidate access readiness. Never logs or sends credentials or grants authority."""
from __future__ import annotations
import os

KEY_NAMES = ('FMP_API_KEY', 'FMP_KEY', 'FINANCIAL_MODELING_PREP_API_KEY')


def inspect_access(*, environ=None):
    values = os.environ if environ is None else environ
    present = [name for name in KEY_NAMES if isinstance(values.get(name), str) and values[name].strip()]
    return {
        'schema': 'ATLAS_FMP_CANDIDATE_ACCESS_V1',
        'credential_configured': bool(present),
        'credential_source_count': len(present),
        'authenticated_access_tested': False,
        'individual_analyst_records_verified': False,
        'free_tier_entitlement_verified': False,
        'operational_source_accepted': False,
        'paper_fill_authorized': False,
        'live_order_authorized': False,
        'reason': 'FMP_CREDENTIAL_MISSING' if not present else 'FMP_AUTHENTICATED_ACCESS_UNTESTED',
    }


if __name__ == '__main__':
    import json
    print(json.dumps(inspect_access(), sort_keys=True))
