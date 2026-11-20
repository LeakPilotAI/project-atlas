"""Offline approval-package checks; no operational store, clock or app launch."""

import ast
import copy
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts.observation_runtime.installed_acceptance_package import (
    selection_baseline,
    validate_scope,
)
from scripts.release_selection import ReleaseSelector, digest

REPO = Path(__file__).resolve().parents[1]
SCOPE = (
    REPO / "docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V4_2026-11-03.json"
)


def history(tmp_path, count=6):
    ref = {
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "DISPOSABLE",
        "release": "a" * 40,
        "root": str(tmp_path / ("a" * 40)),
        "receipt": str(tmp_path / "receipt.json"),
        "receipt_sha256": "b" * 64,
        "artifact_digest": "c" * 64,
    }
    rows = []
    for i in range(1, count + 1):
        rows.append(
            {
                "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
                "domain": "DISPOSABLE",
                "revision": i,
                "action": "SELECT" if i % 2 else "ROLLBACK",
                "operation": f"{i:032x}",
                "previous": digest(rows[-1]) if rows else None,
                "selected": ref if i % 2 else None,
                "restores": None
                if i % 2
                else ("BASELINE" if i == 2 else digest(rows[1])),
            }
        )
    return rows


@pytest.mark.parametrize("count", [2, 4, 6, 126])
def test_independent_metadata_chain_review_agrees_with_existing_selector(
    tmp_path, count
):
    rows = history(tmp_path, count)

    class MemoryStore:
        domain = "DISPOSABLE"

        @contextmanager
        def locked(self):
            yield

        def records(self):
            return copy.deepcopy(rows)

    class NeverOpenedVerifier:
        domain = "DISPOSABLE"

        def open(self, _):
            pytest.fail("UNSELECTED metadata review needs no executable")

    existing = ReleaseSelector(
        store=MemoryStore(), verifier=NeverOpenedVerifier()
    ).current()
    read = selection_baseline(rows, domain="DISPOSABLE")
    assert read == {"revision": count, **existing}


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "chain",
        "bool_revision",
        "restore",
        "schema",
        "selected",
        "capacity",
        "domain",
    ],
)
def test_partial_conflicting_or_nonbaseline_history_refuses(tmp_path, fault):
    rows = history(tmp_path)
    if fault == "duplicate":
        rows[-1]["operation"] = rows[0]["operation"]
    elif fault == "chain":
        rows[-1]["previous"] = "0" * 64
    elif fault == "bool_revision":
        rows[0]["revision"] = True
    elif fault == "restore":
        rows[-1]["restores"] = "0" * 64
    elif fault == "schema":
        rows[-1]["schema"] = "FOREIGN"
    elif fault == "selected":
        rows = rows[:-1]
    elif fault == "capacity":
        rows = history(tmp_path, 128)
    else:
        rows[-1]["domain"] = "WINDOWS_LOCAL"
    with pytest.raises(ValueError):
        selection_baseline(rows, domain="DISPOSABLE")


def test_actual_review_has_current_readback_and_exact_deadlines():
    v = json.loads(SCOPE.read_bytes())
    assert validate_scope(v) is v
    assert v["baseline"]["revision"] == 6 and v["baseline"]["freshly_verified"]
    assert (
        v["selection"]["select_revision"] == 7
        and v["selection"]["rollback_revision"] == 8
    )
    assert v["approval_status"] == "NOT_AUTHORIZED_FRESH_SINGLE_USE_GRANT_REQUIRED"


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("limits", "seconds", 601),
        ("limits", "entries", 8193),
        ("limits", "accounted_bytes", 64 * 1024**2 + 1),
        ("cycle_limits", "complete_stop_seconds", 9),
        ("cycle_limits", "browser_acknowledgement_seconds", 46),
        ("cycle_limits", "maximum_cycles", 3),
        ("clock", "maximum_uncertainty_ms", 1001),
        ("clock", "maximum_age_seconds", 121),
        ("clock", "required_startup", "Manual"),
        ("clock", "required_service_state", "Stopped"),
        ("clock", "fresh_at_selection", False),
        ("baseline", "freshly_verified", False),
        ("baseline", "head", "0" * 64),
        ("baseline", "revision", 4),
        ("selection", "restores", "BASELINE"),
        ("selection", "rollback_revision", 7),
        ("cleanup", "reader_order", ["CIM", "NETSTAT"]),
        ("cleanup", "peer_eof_before_stop", False),
        ("cleanup", "maximum_cim_age_seconds", 3),
        ("cleanup", "maximum_reader_age_seconds", 11),
        ("cleanup", "maximum_collection_seconds", 6),
        ("runtime_isolation", "providers", True),
        ("runtime_isolation", "financial_writers", 0),
        ("runtime_isolation", "workspace_application_fallback", True),
    ],
)
def test_unsafe_contract_mutations_refuse(section, key, value):
    v = json.loads(SCOPE.read_bytes())
    v[section][key] = value
    with pytest.raises(ValueError):
        validate_scope(v)


@pytest.mark.parametrize(
    "key,value",
    [
        ("evidence_root", r"D:\AtlasRuntime"),
        ("public_scope_document", "foreign.json"),
        ("support_id", "0" * 64),
        ("application_release", "0" * 40),
        ("approval_status", "AUTHORIZED"),
        ("status", "BLOCKED_NATIVE_TWO_CYCLE_CLEANUP_VALIDATION"),
    ],
)
def test_foreign_or_self_authorized_scope_refuses(key, value):
    v = json.loads(SCOPE.read_bytes())
    v[key] = value
    with pytest.raises(ValueError):
        validate_scope(v)


def test_exact_v4_source_pins_match_without_an_execution_claim():
    v = json.loads(SCOPE.read_bytes())
    root = Path(v["evidence_root"])
    spec = importlib.util.spec_from_file_location("v4_review_gate", root / "gate.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    raw = (root / "source-manifest.json").read_bytes()
    import hashlib

    assert hashlib.sha256(raw).hexdigest() == v["source_manifest_sha256"]
    gate.verify_sources(json.loads(raw))
    assert len(json.loads(raw)["files"]) == v["source_files"]
    assert json.loads((root / "proposal.json").read_bytes()) == v
    assert (
        not (root / "single-use-claim.json").exists() and not (root / "temp").exists()
    )


def test_frozen_selector_checks_genuine_clock_immediately_before_publication():
    tree = ast.parse((REPO / "scripts/release_selection.py").read_bytes())
    publish = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "publish"
    )
    source = ast.unparse(publish)
    assert source.index("self.clock.require_operational") < source.index(
        "self.store.publish"
    )


def test_operational_write_whitelist_contains_only_four_selector_names():
    v = json.loads(SCOPE.read_bytes())
    assert [p for p in v["allowed_mutations"] if p.startswith("D:\\AtlasRuntime")] == [
        rf"D:\AtlasRuntime\selection\r{n:04d}.{suffix}"
        for n in (7, 8)
        for suffix in ("pending", "json")
    ]


@pytest.mark.parametrize(
    "entry",
    [
        "supervise.py",
        "worker.py",
        "clock_preflight.py",
        "native_preflight.py",
        "restore_known_head.py",
    ],
)
def test_fresh_v4_entries_refuse_without_approval_before_native_action(entry):
    v = json.loads(SCOPE.read_bytes())
    root = Path(v["evidence_root"])
    env = {
        k: value for k, value in os.environ.items() if not k.startswith("ATLAS_AUTH_")
    }
    p = subprocess.run(
        [sys.executable, "-I", "-B", str(root / entry)],
        env=env,
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert p.returncode != 0 and (
        b"NO_NATIVE_ACTION" in p.stderr
        or b"NO_LIVE_EXPLICITLY_APPROVED_ACCEPTANCE_SESSION" in p.stderr
    )
    assert not (root / "single-use-claim.json").exists()
