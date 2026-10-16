import subprocess
from pathlib import Path


def test_frontend_poll_and_transport_contract():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', str(root / 'tests/runtime_poll_contract.cjs')],
                            cwd=root, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'contracts passed' in result.stdout
