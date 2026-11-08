from scripts.observation_runtime.fmp_candidate_access import inspect_access


def test_missing_credentials_fail_closed():
    row = inspect_access(environ={})
    assert row['reason'] == 'FMP_CREDENTIAL_MISSING'
    assert row['operational_source_accepted'] is False
    assert row['paper_fill_authorized'] is False


def test_configured_credential_never_counts_as_access_or_authority():
    row = inspect_access(environ={'FMP_API_KEY': 'secret-do-not-log'})
    assert row['credential_configured'] is True
    assert row['authenticated_access_tested'] is False
    assert row['free_tier_entitlement_verified'] is False
    assert 'secret-do-not-log' not in str(row)
    assert row['live_order_authorized'] is False


def test_blank_credential_is_missing():
    assert inspect_access(environ={'FMP_KEY': '   '})['credential_configured'] is False
