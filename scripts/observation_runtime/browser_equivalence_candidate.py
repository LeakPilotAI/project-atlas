"""Fail-closed validation of *candidate* isolated Chrome evidence.

This is a NONFINANCIAL proposal diagnostic, never an accepted browser witness.
"""
from urllib.parse import urlsplit


def inspect_candidate(*, expected_url, observations):
    """Validate target continuity and origin without issuing any acceptance."""
    if type(expected_url) is not str:
        raise ValueError('CANDIDATE_EXACT_LOOPBACK_URL_REQUIRED')
    expected = urlsplit(expected_url)
    if (expected.scheme != 'http' or expected.hostname != '127.0.0.1'
            or expected.port is None or expected.username is not None
            or expected.password is not None or expected.query or expected.fragment
            or expected.path not in ('', '/') or expected_url != f'http://127.0.0.1:{expected.port}/'):
        raise ValueError('CANDIDATE_EXACT_LOOPBACK_URL_REQUIRED')
    if type(observations) is not list or len(observations) != 3:
        raise ValueError('CANDIDATE_THREE_OBSERVATIONS_REQUIRED')
    target_id = None
    previous_ns = -1
    for stage, item in zip(('created', 'navigated', 'rendered'), observations, strict=True):
        if (type(item) is not dict or set(item) != {'stage', 'target_id', 'url', 'observed_ns', 'error'}
                or item['stage'] != stage or item['error'] is not None
                or type(item['target_id']) is not str or not item['target_id']
                or type(item['observed_ns']) is not int or item['observed_ns'] <= previous_ns):
            raise ValueError('CANDIDATE_OBSERVATION_INVALID')
        if target_id is None:
            target_id = item['target_id']
        if item['target_id'] != target_id:
            raise ValueError('CANDIDATE_TARGET_REPLACED')
        actual = urlsplit(item['url']) if type(item['url']) is str else None
        if (actual is None or item['url'] != expected_url or actual.scheme != expected.scheme
                or actual.hostname != expected.hostname or actual.port != expected.port
                or actual.path.rstrip('/') != expected.path.rstrip('/')
                or actual.username is not None or actual.password is not None
                or actual.query or actual.fragment):
            raise ValueError('CANDIDATE_ORIGIN_MISMATCH')
        previous_ns = item['observed_ns']
    return {'schema': 'ATLAS_BROWSER_EQUIVALENCE_CANDIDATE_V1',
            'target_continuity_observed': True, 'loopback_origin_observed': True,
            'trusted_windows_chrome_provider_verified': False,
            'independent_listener_agreement_verified': False,
            'operational_browser_acceptance': False,
            'financial_activation_authorized': False}
