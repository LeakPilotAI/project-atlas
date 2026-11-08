"""Actual disposable Chrome diagnostic, never an operational browser signoff."""
import pytest

from scripts.observation_runtime.browser_equivalence_cdp_probe import CHROME, probe


@pytest.mark.skipif(not CHROME.is_file(), reason='Windows Chrome not installed')
def test_isolated_chrome_observes_target_and_cleans_up():
    evidence = probe()
    assert evidence['diagnostic']['target_continuity_observed'] is True
    assert evidence['diagnostic']['operational_browser_acceptance'] is False
    assert evidence['diagnostic']['financial_activation_authorized'] is False
    assert evidence['cleanup'] == {
        'chrome_parent_exited': True,
        'server_thread_exited': True,
        'server_socket_closed': True,
    }
