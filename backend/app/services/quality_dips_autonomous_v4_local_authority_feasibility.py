"""Local-only V4 authority feasibility inventory; does not issue trust grants.

Existing native storage primitives are useful, but a local process or a
synthetic witness does not become independent merely by using a second path.
"""
from app.services.quality_dips_autonomous_authority_inspection import inspect_financial_authority_adapters


LOCAL_V4_ROLES = (
    {'role': 'publisher', 'candidate': 'snapshot_store.SnapshotStore',
     'existing_capability': 'native immutable snapshot and witness commit with caller pin',
     'missing': ('accepted independent high-water pin custodian',
                 'V4 publication issuer and reserve/commit contract',
                 'authority principal and revocation policy')},
    {'role': 'custody', 'candidate': 'snapshot_store.SyntheticAuthority',
     'existing_capability': 'synthetic two-key test-only attestation',
     'missing': ('non-synthetic independent principal and key custody',
                 'durable acknowledgment bound to native committed publication',
                 'independent rollback-resistant receipt high-water mark')},
    {'role': 'financial_replay', 'candidate': 'V4InceptionFinancialReplay',
     'existing_capability': 'zero-event financial replay and native binding',
     'missing': ('accepted nonzero native V4 event/receipt protocol',
                 'provider/fill provenance and approved accounting policy',
                 'independent complete event-history replay authority')},
    {'role': 'native_reader', 'candidate': 'BoundNativeEnrollmentEvidence',
     'existing_capability': 'Windows native identity and SHA256-bound readback',
     'missing': ('accepted publisher/cut lease and financial authority',
                 'trusted ownership/host/clock evidence')},
)


def inspect_local_v4_authority_feasibility(*, external_witness_accepted=False,
                                            provider_rights_accepted=False,
                                            native_protocol_accepted=False):
    """Never infer acceptance from caller flags or existence of local files."""
    if any(type(v) is not bool for v in (external_witness_accepted,
                                         provider_rights_accepted,
                                         native_protocol_accepted)):
        raise ValueError('V4_AUTHORITY_FEASIBILITY_BOOLEAN_REQUIRED')
    return {'schema': 'QD_AUTO_V4_LOCAL_AUTHORITY_FEASIBILITY_V1',
            'status': 'SOURCE_ONLY_BLOCKED',
            'local_only_possible_in_principle': True,
            'local_only_independence_proven': False,
            'candidate_roles': [dict(row) for row in LOCAL_V4_ROLES],
            'operator_assertions_not_accepted_as_evidence': {
                'external_witness': external_witness_accepted,
                'provider_rights': provider_rights_accepted,
                'native_protocol': native_protocol_accepted},
            'independent_publisher_accepted': False,
            'independent_custody_accepted': False,
            'nonzero_v4_replay_accepted': False,
            'provider_rights_accepted': False,
            'startup_authorized': False, 'production_authorized': False}