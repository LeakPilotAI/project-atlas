"""Single-process .NET listener control cannot confer production authority."""
import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell/.NET required')
def test_single_process_disposable_listener_never_authorizes():
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'observation_runtime' / 'disposable_single_process_listener_probe.ps1'
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script), '-Rounds', '2'],
                            capture_output=True, text=True, check=True, timeout=20)
    data = json.loads(result.stdout)
    assert data['schema'] == 'ATLAS_SINGLE_PROCESS_DISPOSABLE_LISTENER_V1'
    assert data['rounds'] == 2
    assert len(data['samples']) == 2
    assert data['endpoints_redacted'] is True
    assert data['operational_listener_accepted'] is False
    assert data['financial_authorized'] is False
    for sample in data['samples']:
        assert set(sample) == {'cim_states', 'cmdlet_states', 'netstat_listener_present', 'socket_accepting'}
