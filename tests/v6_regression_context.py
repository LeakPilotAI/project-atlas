"""Run one historical PREPARATION test in its explicit disposable phase.

The real V5 root is consumed and must stay so. No operational entry, scope or
old test is changed. This fixture never applies to any other test.
"""

import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def historical_v5_preparation_phase(request, tmp_path, monkeypatch):
    if (
        request.node.nodeid
        != "tests/test_installed_acceptance_package_v5.py::test_source_manifest_and_copies_are_exact_without_claim_or_execution"
    ):
        yield
        return
    module = request.module
    original = module.SCOPE
    original_raw = original.read_bytes()
    scope = json.loads(original_raw)
    live = Path(scope["evidence_root"])
    consumed = json.loads((live / "supervisor-result.json").read_bytes())
    assert (live / "single-use-claim.json").is_file()
    assert (
        consumed["authorization_consumed"]
        and consumed["status"] == "REFUSED_PRESERVE_EVIDENCE"
    )
    frozen = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in live.iterdir()
        if p.is_file()
    }
    mirror = tmp_path / "DISPOSABLE_V5_PREPARATION_ONLY"
    mirror.mkdir()
    names = [p.name for p in module.SOURCE.iterdir() if p.suffix in (".py", ".ps1")]
    for name in [*names, "source-manifest.json"]:
        (mirror / name).write_bytes((live / name).read_bytes())
    scope["evidence_root"] = str(mirror)
    scope["fixture_domain"] = "DISPOSABLE_PREPARATION_COPY_NOT_EXECUTION_SCOPE"
    fixture_scope = tmp_path / "synthetic-preparation-scope.json"
    fixture_scope.write_text(json.dumps(scope))
    # The operational validator MUST refuse this synthetic path. The old test
    # exercises only package-copy/hash/default-unclaimed preparation invariants.
    with pytest.raises(ValueError, match="EXACT_V5_PATHS_REQUIRED"):
        module.validate_scope(scope)
    monkeypatch.setattr(module, "SCOPE", fixture_scope)
    yield
    assert original.read_bytes() == original_raw
    assert all(
        hashlib.sha256((live / name).read_bytes()).hexdigest() == digest
        for name, digest in frozen.items()
    )
    assert (live / "single-use-claim.json").is_file()
