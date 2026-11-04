"""Parent-observed end-to-end native Stop/exit/readback with synthetic authority."""
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts.observation_runtime import aip06_fixture_guard as guarded


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@contextmanager
def prepared_reader(enabled,repo):
    guarded.require_fixture("cold-reader-profile")
    if enabled:
        raise ValueError("RETAINED_READER_NOT_IN_AIP06_COLD_SCOPE")
    yield None


@pytest.mark.parametrize('sample',[1,2,3])
def test_three_owned_native_shutdowns_include_exit_and_post_exit_readback(sample):
    guard = guarded.require_fixture("owned-stop-timing")
    assert os.environ.get("ATLAS_OWNED_STOP_TIMING_PARENT") == guarded.ROOTS["T"]
    assert os.environ.get("ATLAS_OWNED_STOP_READER_MODE", "COLD") == "COLD"
    result = guard.run_owned_stop_sample(sample, Path(__file__).resolve().parents[1])
    assert result["source_contract_passed"] and result["elapsed_ns"] <= 8 * 10**9
    assert result["native_acceptance"] is False  # External native evidence is separately graded.
