"""Disposable .NET listener bind-mode observations grant no authority."""
import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell/.NET required')
def test_wildcard_bind_diagnostic_preserves_missing_states():
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'observation_runtime' / 'disposable_dotnet_listener_probe.ps1'
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script), '-IPv4Wildcard'],
                            capture_output=True, text=True, timeout=20, check=True)
    data = json.loads(result.stdout)
    assert data['schema'] == 'ATLAS_DISPOSABLE_DOTNET_LISTENER_V1'
    assert data['bind_address'] == '0.0.0.0'
    assert data['operational_listener_accepted'] is False
    assert data['financial_authorized'] is False
    assert all(item['state'] is None or isinstance(item['state'], int) for item in data['cim'])
