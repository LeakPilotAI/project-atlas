"""Exercise the actual inline UI against isolated snapshots, never live journals."""
import subprocess
from pathlib import Path


def test_quality_dips_render_and_recovery_contract():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ['node', str(root / 'tests/quality_dips_visual_contract.cjs')],
        cwd=root, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'contracts passed' in result.stdout
