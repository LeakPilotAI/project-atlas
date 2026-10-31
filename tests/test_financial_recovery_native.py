"""Explicitly confined native archive restoration; fixture authority only."""
import copy
import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_quality_dips_read_capability_native import capture

pytest_plugins = ["test_quality_dips_read_capability_native"]

SPEC = importlib.util.spec_from_file_location("tested_financial_recovery", Path(__file__).resolve().parents[1]
                                             / "scripts/volume_inspector/financial_recovery.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class FixtureRecoveryAuthority:
    """Captured external fixture expectations, never operational enrollment."""
    def __init__(self, n):
        self.expected = copy.deepcopy({"schema": "FS_RECOVERY_REQUEST_V1", "recovery_id": "fixture-recovery",
                                       "enrollment": n.enrollment, "current": n.current})
        self.accepted = None
        self.fail = False
        self.valid = True

    @contextmanager
    def lease(self, request):
        if request != self.expected or self.accepted is not None or not self.valid:
            raise ValueError("FIXTURE_AUTHORITY_REJECTED")
        yield self

    def check(self):
        return self.valid

    def accept(self, descriptor, binding):
        if self.fail:
            raise OSError("injected authority acknowledgement interruption")
        self.accepted = copy.deepcopy((descriptor, binding))
        return True

    def validate(self, descriptor, binding):
        return self.valid and self.accepted == (descriptor, binding)


def restore(n, authority=None, **changes):
    authority = authority or FixtureRecoveryAuthority(n)
    protocol = m.DisposableRecovery(authority)
    args = {"roots": (n.source, n.projection, n.reports), "destination": n.tmp_path / "restored",
            "enrollment": n.enrollment, "current": n.current, "recovery_id": "fixture-recovery"}
    args.update(changes)
    receipt = protocol.restore(**args)
    return protocol, receipt, authority


def test_clean_restore_retains_original_bytes_and_overnight_position(native):
    n = native
    before = capture(n.source), capture(n.projection), capture(n.reports)
    protocol, receipt, authority = restore(n)
    view = protocol.read(n.tmp_path / "restored", receipt)
    assert view["evidence"]["state"]["cash"] == "900.0"
    assert len(view["evidence"]["state"]["positions"]) == 1
    assert view["financial_writes_authorized"] is False and view["startup_authorized"] is False
    assert (capture(n.source), capture(n.projection), capture(n.reports)) == before
    mapping = authority.accepted[0]["mapping"]
    assert all(x["original"]["id"] != x["restored"]["id"] for x in mapping)
    assert all(x["original"]["sha256"] == x["restored"]["sha256"] for x in mapping)
    assert not hasattr(protocol, "execute")
    with pytest.raises(ValueError, match="AUTHORITY_REJECTED"):
        restore(n, authority)


@pytest.mark.parametrize("kind", ["unknown", "stale", "rollback", "foreign", "missing", "tail"])
def test_source_refusal_before_destination_allocation(native, kind):
    n = native
    authority = FixtureRecoveryAuthority(n)
    current = copy.deepcopy(n.current)
    enrollment = copy.deepcopy(n.enrollment)
    if kind == "unknown":
        current["status"] = "UNKNOWN"
    elif kind == "stale":
        current["generation"] -= 1
    elif kind == "rollback":
        current["source"]["entries"] = []
    elif kind == "foreign":
        enrollment["source_root"][1] += 1
    elif kind == "missing":
        (n.source / "0001-record.json").rename(n.tmp_path / "retained-record.json")
    else:
        (n.source / "unknown-intent.json").write_bytes(b"{}")
    with pytest.raises((ValueError, OSError, KeyError)):
        restore(n, authority, current=current, enrollment=enrollment)
    assert not (n.tmp_path / "restored").exists()


@pytest.mark.parametrize("boundary", ["intent.json", "copy-0000.json", "commit.json", "authority"])
def test_interruption_retained_and_retry_never_overwrites(native, monkeypatch, boundary):
    n = native
    authority = FixtureRecoveryAuthority(n)
    original = m.f.w.WindowsOutput.write_bound
    def interrupted(output, name, raw):
        result = original(output, name, raw)
        if name == boundary:
            raise OSError("injected after durable publication")
        return result
    monkeypatch.setattr(m.f.w.WindowsOutput, "write_bound", interrupted)
    authority.fail = boundary == "authority"
    with pytest.raises(OSError):
        restore(n, authority)
    retained = capture(n.tmp_path / "restored")
    assert retained and authority.accepted is None
    monkeypatch.setattr(m.f.w.WindowsOutput, "write_bound", original)
    authority.fail = False
    with pytest.raises((OSError, ValueError)):
        restore(n, authority)
    assert capture(n.tmp_path / "restored") == retained


@pytest.mark.parametrize("kind", ["tamper", "missing", "copied_receipt", "expired_custody"])
def test_restored_read_refuses_without_mutating(native, kind):
    n = native
    protocol, receipt, authority = restore(n)
    root = n.tmp_path / "restored"
    if kind == "tamper":
        (root / "copy-0000.json").write_bytes(b"{}")
    elif kind == "missing":
        (root / "copy-0000.json").rename(n.tmp_path / "retained-copy.json")
    elif kind == "copied_receipt":
        receipt["root"][1] += 1
    else:
        authority.valid = False
    before = capture(root)
    with pytest.raises((ValueError, OSError)):
        protocol.read(root, receipt)
    assert capture(root) == before


def test_no_authority_refuses():
    with pytest.raises(ValueError, match="AUTHORITY_REQUIRED"):
        m.DisposableRecovery(None)


def test_destination_cannot_change_original_namespace(native):
    n = native
    before = capture(n.source)
    with pytest.raises(ValueError, match="OVERLAP"):
        restore(n, destination=n.source / "restore")
    assert capture(n.source) == before


def test_restored_hardlink_refused(native):
    import os
    n = native
    protocol, receipt, _ = restore(n)
    root = n.tmp_path / "restored"
    os.link(root / "copy-0000.json", n.tmp_path / "extra-link.json")
    with pytest.raises((ValueError, OSError)):
        protocol.read(root, receipt)


def test_restored_junction_refused(native):
    import subprocess
    n = native
    protocol, receipt, _ = restore(n)
    junction = n.tmp_path / "restore-junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(n.tmp_path / "restored")],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    with pytest.raises((ValueError, OSError)):
        protocol.read(junction, receipt)


@pytest.mark.parametrize("phase,expected_cash", [("partial", "943.968"), ("final", "1009.920")])
def test_partial_and_final_history_restore(native, phase, expected_cash):
    from qd_http_fixture import build_fixture
    n = native
    root = n.tmp_path / "synthetic-phases"
    root.mkdir()
    build_fixture(root)
    data = m.strict((root / "fixture.json").read_text())["phases"][phase]
    selected = SimpleNamespace(tmp_path=n.tmp_path, enrollment=data["enrollment"], current=data["current"],
                               source=root / phase / "source", projection=root / phase / "projection",
                               reports=root / phase / "reports")
    protocol, receipt, _ = restore(selected)
    view = protocol.read(n.tmp_path / "restored", receipt)
    from decimal import Decimal
    assert Decimal(view["evidence"]["state"]["cash"]) == Decimal(expected_cash)
    assert len(view["evidence"]["rows"]) == (2 if phase == "partial" else 3)
