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

@pytest.mark.skipif(not CHROME.is_file(), reason='Windows Chrome not installed')
def test_installed_release_static_preview_is_never_operational():
    path = (r'D:\AtlasRuntime\releases\4fad7ac195fd0b36f1b81577fabf1b8f69932eb9'
            r'\backend\app\static\dashboard.html')
    from pathlib import Path
    if not Path(path).is_file():
        pytest.skip('Installed release not available')
    evidence = probe(installed_static_preview=path)
    assert len(evidence['installed_static_preview_sha256']) == 64
    assert evidence['operational_dashboard_verified'] is False
    assert evidence['diagnostic']['operational_browser_acceptance'] is False
    assert evidence['cleanup']['chrome_parent_exited'] is True


def test_refuse_workspace_html_as_installed_release():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'backend/app/static/dashboard.html'
    with pytest.raises(ValueError, match='INSTALLED_RELEASE_ROOT_REQUIRED'):
        probe(installed_static_preview=path)
