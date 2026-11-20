"""Restricted-token tests on disposable NTFS fixtures; never production ACLs."""
from __future__ import annotations

import ctypes as C
import os
import subprocess
from ctypes import wintypes as W
from pathlib import Path

import pytest
from test_r7e47s_observation_bootstrap import make_fixture

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Native Windows required")


@pytest.mark.parametrize("target", ["runtime-state", "runtime-assets"])
def test_restricted_development_actor_cannot_write_runtime_fixture(tmp_path, target):
    from test_r7e47c_windows_output import m, set_acl

    outputs = []

    def provision(path):
        outputs.append(m.WindowsOutput.create_root(str(path)))

    try:
        manifest, _pin, _contract, _history, world, bootstrap = make_fixture(
            tmp_path / "fixture", protected_runtime=provision,
        )
        runtime = bootstrap.start()
        # Positive control: this exact restricted token can open/write a synthetic
        # development file explicitly granted Everyone access, but not runtime.
        control = Path(manifest["development"]["roots"][1]) / "positive-control.txt"
        control.write_bytes(b"")
        sid = m.current_sid()
        set_acl(control, f"O:{sid}D:P(A;;FA;;;{sid})(A;;FA;;;SY)(A;;FA;;;WD)")
        if target == "runtime-state":
            destination = Path(manifest["state_root"]) / "forbidden.json"
            creation = 1  # CREATE_NEW, no existing state record touched
            before = None
        else:
            destination = Path(manifest["build_root"]) / "index.html"
            creation = 3  # OPEN_EXISTING with write access
            before = destination.read_bytes()
        normal, restricted, everyone = W.HANDLE(), W.HANDLE(), C.c_void_p()
        convert = m.bind(m.A, "ConvertStringSidToSidW", [W.LPCWSTR, C.POINTER(C.c_void_p)])
        restrict = m.bind(m.A, "CreateRestrictedToken", [W.HANDLE, W.DWORD, W.DWORD, C.c_void_p,
                          W.DWORD, C.c_void_p, W.DWORD, C.POINTER(m.SidAttr), C.POINTER(W.HANDLE)])
        impersonate = m.bind(m.A, "ImpersonateLoggedOnUser", [W.HANDLE])
        revert = m.bind(m.A, "RevertToSelf", [])
        m.check(m.open_token(m.process(), 0xE, C.byref(normal)))
        m.check(convert("S-1-1-0", C.byref(everyone)))
        try:
            attr = m.SidAttr(everyone, 0)
            m.check(restrict(normal, 1, 0, None, 0, None, 1, C.byref(attr), C.byref(restricted)))
            m.check(impersonate(restricted))
            try:
                allowed = m.create_file(str(control), m.WRITE, 1, None, 3, 0x00200000, None)
                assert allowed != m.INVALID, "Positive-control write access must succeed"
                try:
                    raw = C.create_string_buffer(b"development-only")
                    written = W.DWORD()
                    m.check(m.write_file(allowed, raw, 16, C.byref(written), None))
                    assert written.value == 16
                finally:
                    m.close_handle(allowed)
                denied = m.create_file(str(destination), m.WRITE, 1, None, creation, 0x00200000, None)
                error = C.get_last_error()
                if denied != m.INVALID:
                    m.close_handle(denied)
                assert denied == m.INVALID and error == 5
            finally:
                m.check(revert())
        finally:
            if restricted:
                m.close_handle(restricted)
            m.close_handle(normal)
            m.local_free(everyone)
        assert control.read_bytes() == b"development-only"
        if before is None:
            assert not destination.exists()
        else:
            assert destination.read_bytes() == before
        assert world.runtime_alive is True
        assert runtime.asset("assets/index.html") == b"fixed-runtime-assets"
    finally:
        for output in outputs:
            output.close()


def test_native_development_junction_cannot_escape_into_runtime_state(tmp_path):
    from scripts.observation_runtime.contracts import DevelopmentWorkspace, Refused

    manifest, _pin, contract, *_ = make_fixture(tmp_path / "fixture")
    link = Path(manifest["development"]["roots"][0]) / "runtime-alias"
    target = Path(manifest["state_root"])
    result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, check=False, timeout=10)
    assert result.returncode == 0, result.stderr
    with pytest.raises(Refused): DevelopmentWorkspace(contract).write(link / "forbidden.txt", b"forbidden")
    assert not (target / "forbidden.txt").exists()
