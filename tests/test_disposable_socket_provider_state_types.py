"""Windows diagnostic preserves missing socket states rather than coercing to zero."""
import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell/.NET required')
def test_socket_provider_state_type_control_never_authorizes():
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'observation_runtime' / 'disposable_socket_provider_state_types.ps1'
    completed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script)],
                               capture_output=True, text=True, timeout=20, check=True)
    result = json.loads(completed.stdout)
    assert result['schema'] == 'ATLAS_SOCKET_PROVIDER_STATE_TYPES_V1'
    assert result['endpoints_redacted'] is True
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
    assert isinstance(result['records'], list)
    for record in result['records']:
        assert record['reader'] in ('cim', 'nettcp')
        if record['direct_type'] == 'null':
            assert record['property_type'] == 'null'
            assert record['direct_string'] == ''
            assert record['property_string'] == ''
            assert record['numeric_state'] is None
