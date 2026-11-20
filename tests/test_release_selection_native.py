"""Opt-in disposable NTFS only. Never opens an operational release or account."""

import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest
from release_selection_fixture import FixtureVerifier, make_release
from test_release_selection import grant, select

from scripts.release_selection import ReleaseSelector
from scripts.release_selection_store import NativeSelectionStore

SCOPE = os.environ.get("ATLAS_SELECTOR_NATIVE_FIXTURE")
pytestmark = pytest.mark.skipif(
    not SCOPE, reason="Explicit confined native fixture required"
)


@pytest.fixture
def setup():
    from scripts.volume_inspector import windows_output as w

    scope = Path(SCOPE).absolute()
    repo = Path(__file__).resolve().parents[1]
    assert scope.parent == repo / "logs/diagnostics" and scope.name.startswith(
        "qd-selector-v1-native-"
    )
    case = scope / ("case-" + uuid.uuid4().hex)
    with w.WindowsOutput.create_root(str(case)):
        pass
    control = case / "selection"
    with w.WindowsOutput.create_root(str(control)) as out:
        info = w.info(out.root_handle)
        native_id = [info.volume, info.index_hi, info.index_lo]
    a, b = [make_release(case, c * 40) for c in "ab"]
    store = NativeSelectionStore.disposable(root=control, native_root=native_id)
    selector = ReleaseSelector(store=store, verifier=FixtureVerifier(case))
    try:
        yield selector, a, b, native_id
    finally:
        store.close()
        assert not store.output.handles and store.mutex is None


def test_native_atomic_selection_rollback_and_clean_reopen(setup):
    s, a, b, identity = setup
    first = select(s, a)
    second = select(s, b, first["head"])
    restored = s.change(
        grant(a, second["head"], action="ROLLBACK", restores=first["head"]),
        approved=True,
    )
    assert s.current() == {"head": restored["head"], "selected": a}
    root = s.store.root
    s.store.close()
    other = NativeSelectionStore.disposable(root=root, native_root=identity)
    try:
        reopened = ReleaseSelector(store=other, verifier=s.verifier)
        assert reopened.current()["selected"] == a
    finally:
        other.close()


def test_native_partial_stage_refuses_restart_without_repair(setup):
    s, _, _, identity = setup
    with s.store.locked():
        s.store.output.write_bound("r0001.pending", b'{"interrupted"')
    with pytest.raises(ValueError, match="INTERRUPTED_TAIL"):
        s.current()
    root = s.store.root
    s.store.close()
    other = NativeSelectionStore.disposable(root=root, native_root=identity)
    try:
        with other.locked(), pytest.raises(ValueError, match="INTERRUPTED_TAIL"):
            other.records()
    finally:
        other.close()


def test_native_unaccepted_root_and_fixture_authority_cannot_be_operational(setup):
    s, _a, _, identity = setup
    with pytest.raises(ValueError, match="ROOT_SUBSTITUTION"):
        NativeSelectionStore.disposable(
            root=s.store.root, native_root=[identity[0], identity[1], identity[2] ^ 1]
        )
    assert s.store.domain == "DISPOSABLE"
    from scripts.installed_nonfinancial_launcher import InstalledNonfinancialLauncher

    with pytest.raises(ValueError, match="ACCEPTED_NATIVE_SELECTION"):
        InstalledNonfinancialLauncher(selector=s)
    assert not list(Path(s.store.root).iterdir())


def test_native_no_lock_no_publication(setup):
    s, _a, _, _ = setup
    with pytest.raises(ValueError, match="LOCK_OWNERSHIP"):
        s.store.records()
    with pytest.raises(ValueError, match="LOCK_OWNERSHIP"):
        s.store.publish({})
    with (
        s.store.locked(),
        pytest.raises(ValueError, match="REENTRANT"),
        s.store.locked(),
    ):
        pass


def test_native_retained_ancestor_handle_blocks_directory_replacement(setup):
    s, a, _, _ = setup
    selected = select(s, a)
    path = Path(s.store.root)
    with pytest.raises(OSError):
        path.rename(path.with_name("substituted"))
    assert s.current() == {"head": selected["head"], "selected": a}


def test_native_concurrent_ports_share_actual_windows_mutex(setup):
    s, a, b, identity = setup
    other = NativeSelectionStore.disposable(root=s.store.root, native_root=identity)
    second = ReleaseSelector(store=other, verifier=s.verifier)
    barrier = threading.Barrier(2)
    out = []

    def run(selector, target):
        barrier.wait()
        try:
            out.append(select(selector, target))
        except ValueError as e:
            out.append(str(e))

    threads = [
        threading.Thread(target=run, args=(sel, target))
        for sel, target in ((s, a), (second, b))
    ]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
            assert not t.is_alive()
        assert sum(isinstance(v, dict) for v in out) == 1
        with s.store.locked():
            assert len(s.store.records()) == 1
    finally:
        other.close()


def test_native_abrupt_writer_exit_and_restart_refuse_abandoned_pending(setup):
    s, _, _, identity = setup
    Path(__file__).resolve().parents[1]
    code = r"""
import json,os,sys
from pathlib import Path
repo=Path(r'D:\Work\Project Atlas');sys.path[:0]=[str(repo),str(repo/'backend')]
from scripts.release_selection_store import NativeSelectionStore
value=json.loads(sys.stdin.read())
store=NativeSelectionStore.disposable(root=value['root'],native_root=value['identity'])
with store.locked():
 store.output.write_bound('r0001.pending',b'{"interrupted"')
 os._exit(17)
"""
    child = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        input=json.dumps({"root": s.store.root, "identity": identity}).encode(),
        capture_output=True,
        timeout=15,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert child.returncode == 17, child.stderr.decode(errors="replace")
    with pytest.raises(ValueError, match="ABANDONED"):
        s.current()
    path = s.store.root
    s.store.close()
    other = NativeSelectionStore.disposable(root=path, native_root=identity)
    try:
        with other.locked(), pytest.raises(ValueError, match="INTERRUPTED_TAIL"):
            other.records()
    finally:
        other.close()


def test_native_live_selection_lease_cannot_be_closed_under_running_owner(setup):
    selector, a, _, _ = setup
    result = select(selector, a)
    with (
        selector.lease(expected_head=result["head"]),
        pytest.raises(ValueError, match="CLOSE_WHILE_LEASED"),
    ):
        selector.store.close()
    assert not selector.store.poisoned
