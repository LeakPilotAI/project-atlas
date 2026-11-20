"""Read-only AIP-06 host preflight; never grants execution authority."""

from scripts.observation_runtime.aip06_scoped_context import verify_physical_host_handoff


MISSING_NATIVE_EVIDENCE = (
    'independent_process_identity',
    'original_job_membership',
    'complete_descendant_roster',
    'authenticated_private_channel',
    'independent_reader_native_handles',
    'stop_escrow_and_bounded_cleanup',
)


def inspect(packet, descriptor, guard):
    """Check existing data contracts, then disclose unimplemented native proofs.

    Never accept caller-provided assertions as native evidence. The returned
    report is diagnostic only and cannot be exchanged for execution authority.
    """
    verified = verify_physical_host_handoff(packet, descriptor, guard)
    return {'schema': 'AIP06_HOST_PREFLIGHT_V1',
            'scenario': verified['reservation']['scenario'],
            'native_acceptance': False,
            'execution_authorized': False,
            'missing_native_evidence': MISSING_NATIVE_EVIDENCE}


def require_execution(preflight):
    """The current preflight is not an executable physical host."""
    if type(preflight) is not dict or preflight.get('schema') != 'AIP06_HOST_PREFLIGHT_V1':
        raise ValueError('EXACT_AIP06_HOST_PREFLIGHT_REQUIRED')
    raise ValueError('INDEPENDENT_PHYSICAL_CASE_HOST_NOT_IMPLEMENTED')
