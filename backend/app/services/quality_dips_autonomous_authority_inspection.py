"""Static refusal inventory for V4 autonomous native financial trust wiring.

A source-only inspection: it neither instantiates Windows native readers nor
claims authority from method-name similarity or test doubles.
"""
import inspect
from app.services.quality_dips_autonomous_publication_port import BoundAutonomousFinancialPublication
from app.services.quality_dips_autonomous_enrollment import validate_enrollment


REQUIRED = {
    'publication': ('lease', 'snapshot', 'check'),
    'custody_ack': ('lease', 'check'),
    'financial_replay': ('lease', 'snapshot', 'check', 'verify'),
}


def inspect_financial_authority_adapters(*, publication=None, custody_ack=None,
                                          financial_replay=None):
    """Describe missing interface members without constructing or invoking ports."""
    candidates = {'publication': publication, 'custody_ack': custody_ack,
                  'financial_replay': financial_replay}
    rows = []
    for role, candidate in candidates.items():
        # lease snapshot/check are acquired dynamically: their existence cannot
        # be inferred from a class method or verified without an accepted grant.
        callable_lease = candidate is not None and callable(getattr(candidate, 'lease', None))
        callable_verify = candidate is not None and callable(getattr(candidate, 'verify', None))
        missing = []
        if not callable_lease:
            missing.append('lease')
        if role == 'financial_replay' and not callable_verify:
            missing.append('verify')
        rows.append({'role': role, 'interface_present': not missing,
                     'missing': missing, 'independent_authority_accepted': False})
    return {'schema': 'QD_AUTO_NATIVE_AUTHORITY_SOURCE_INSPECTION_V1',
            'status': 'SOURCE_INSPECTION_NOT_ACCEPTANCE',
            'startup_authorized': False, 'production_authorized': False,
            'operational_evidence_verified': False, 'ports': rows}
