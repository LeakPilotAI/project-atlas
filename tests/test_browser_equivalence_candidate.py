"""Candidate evidence cannot be promoted into operational browser acceptance."""
import pytest

from scripts.observation_runtime.browser_equivalence_candidate import inspect_candidate


URL = 'http://127.0.0.1:8765/'


def observations():
    return [{'stage': stage, 'target_id': 'isolated-tab-1', 'url': URL,
             'observed_ns': n, 'error': None}
            for n, stage in enumerate(('created', 'navigated', 'rendered'), start=1)]


def test_valid_candidate_never_grants_authority():
    result = inspect_candidate(expected_url=URL, observations=observations())
    assert result['target_continuity_observed'] is True
    assert result['loopback_origin_observed'] is True
    assert result['operational_browser_acceptance'] is False
    assert result['financial_activation_authorized'] is False
    assert result['trusted_windows_chrome_provider_verified'] is False
    assert result['independent_listener_agreement_verified'] is False


@pytest.mark.parametrize('mutate', [
    lambda o: o[1].update(target_id='replaced'),
    lambda o: o[1].update(url='http://127.0.0.2:8765/'),
    lambda o: o[1].update(url='http://127.0.0.1:8766/'),
    lambda o: o[1].update(url='http://attacker@127.0.0.1:8765/'),
    lambda o: o[1].update(url=URL + '?override=1'),
    lambda o: o[1].update(observed_ns=1),
    lambda o: o[1].update(error='navigation failed'),
    lambda o: o[1].update(stage='skipped'),
])
def test_refuse_inconsistent_candidate(mutate):
    items = observations()
    mutate(items)
    with pytest.raises(ValueError):
        inspect_candidate(expected_url=URL, observations=items)


@pytest.mark.parametrize('url', ['https://127.0.0.1:8765/',
                                 'http://example.com:8765/',
                                 'http://127.0.0.1:8765/?q=1'])
def test_refuse_invalid_expected_origin(url):
    with pytest.raises(ValueError):
        inspect_candidate(expected_url=url, observations=observations())

@pytest.mark.parametrize('bad', [None, '', 7, [], {}, 'http://127.0.0.1:8765/other',
                                  'http://127.0.0.1:8765/#fragment',
                                  'http://127.0.0.1:8765/?q=1'])
def test_refuse_bad_browser_url_observation(bad):
    items = observations()
    items[2]['url'] = bad
    with pytest.raises(ValueError):
        inspect_candidate(expected_url=URL, observations=items)


def test_refuse_missing_browser_stage():
    with pytest.raises(ValueError):
        inspect_candidate(expected_url=URL, observations=observations()[:-1])


def test_refuse_extra_browser_stage():
    with pytest.raises(ValueError):
        inspect_candidate(expected_url=URL, observations=observations() + [observations()[-1]])
