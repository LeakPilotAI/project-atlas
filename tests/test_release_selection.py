import os
import threading
import uuid
from pathlib import Path

import pytest
from release_selection_fixture import DisposableStore, FixtureVerifier, make_release

from scripts.release_selection import (
    NativeInstalledReleaseVerifier,
    ReleaseSelector,
    digest,
    encoded,
    strict,
    validate_spec,
)
from scripts.release_selection_store import NativeSelectionStore


@pytest.fixture
def setup(tmp_path):
    a, b = [make_release(tmp_path, c * 40) for c in "ab"]
    store = DisposableStore(tmp_path / "selection")
    return ReleaseSelector(store=store, verifier=FixtureVerifier(tmp_path)), a, b


def grant(target, expected=None, *, action="SELECT", restores=None):
    return {
        "schema": "QD_CODE_SELECTION_AUTHORIZATION_V1",
        "domain": "DISPOSABLE",
        "action": action,
        "operation": uuid.uuid4().hex,
        "expected_head": expected,
        "target": target,
        "restores": restores,
    }


def select(s, target, head=None):
    return s.change(grant(target, head), approved=True)


def test_valid_selection_durable_receipt_restart_and_old_files_preserved(setup):
    s, a, b = setup
    before = {
        str(p): p.read_bytes()
        for spec in (a, b)
        for p in Path(spec["root"]).rglob("*")
        if p.is_file()
    }
    first = select(s, a)
    assert first["head"] == digest(first["receipt"])
    second = select(s, b, first["head"])
    restarted = ReleaseSelector(
        store=DisposableStore(s.store.root), verifier=s.verifier
    )
    assert restarted.current() == {"head": second["head"], "selected": b}
    assert all(Path(p).read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("value", [False, None, 1, "true"])
def test_default_authorization_refuses_before_storage(setup, monkeypatch, value):
    s, a, _ = setup
    monkeypatch.setattr(s.store, "locked", lambda: pytest.fail("Storage accessed"))
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        s.change(grant(a), approved=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("release", "../x"),
        ("release", "A" * 40),
        ("domain", "WINDOWS_LOCAL"),
        ("root", "relative"),
        ("receipt", "relative"),
        ("artifact_digest", "0"),
        ("receipt_sha256", None),
        ("extra", False),
    ],
)
def test_invalid_target_refuses_before_any_publication(setup, field, value):
    s, a, _ = setup
    bad = {**a, field: value}
    with pytest.raises((ValueError, TypeError)):
        select(s, bad)
    assert list(s.store.root.iterdir()) == []


@pytest.mark.parametrize("fault", ["partial_stage", "after_stage"])
def test_interruption_preserves_old_selection_bytes_and_refuses_restart(setup, fault):
    s, a, b = setup
    first = select(s, a)
    old = {p.name: p.read_bytes() for p in s.store.root.iterdir()}
    s.store.fault = fault
    with pytest.raises(OSError):
        select(s, b, first["head"])
    assert all((s.store.root / n).read_bytes() == v for n, v in old.items())
    reopened = ReleaseSelector(store=DisposableStore(s.store.root), verifier=s.verifier)
    with pytest.raises(ValueError, match="TAIL"):
        reopened.current()
    with pytest.raises(ValueError, match="TAIL"):
        select(reopened, b, first["head"])


def test_pre_effect_failure_leaves_previous_head_and_no_extra_record(setup):
    s, a, b = setup
    first = select(s, a)
    s.store.fault = "before_stage"
    with pytest.raises(OSError):
        select(s, b, first["head"])
    assert s.current() == {"head": first["head"], "selected": a}


def test_commit_before_caller_ack_never_blindly_repeats(setup):
    s, a, b = setup
    first = select(s, a)
    g = grant(b, first["head"])
    s.store.fault = "after_publish"
    with pytest.raises(OSError):
        s.change(g, approved=True)
    restarted = ReleaseSelector(
        store=DisposableStore(s.store.root), verifier=s.verifier
    )
    assert restarted.current()["selected"] == b
    with pytest.raises(ValueError, match="STALE_HEAD_OR_DUPLICATE"):
        restarted.change(g, approved=True)
    assert len(list(s.store.root.iterdir())) == 4


def test_valid_rollback_and_first_selection_unselected_baseline(setup):
    s, a, b = setup
    first = select(s, a)
    second = select(s, b, first["head"])
    result = s.change(
        grant(a, second["head"], action="ROLLBACK", restores=first["head"]),
        approved=True,
    )
    assert s.current() == {"head": result["head"], "selected": a}
    assert len(s.store.records()) == 3


def test_first_selection_rollback_is_explicit_unselected_not_fake_previous_release(
    setup,
):
    s, a, _ = setup
    first = select(s, a)
    r = s.change(
        grant(None, first["head"], action="ROLLBACK", restores="BASELINE"),
        approved=True,
    )
    assert s.current() == {"head": r["head"], "selected": None}
    with (
        pytest.raises(ValueError, match="HEAD_REQUIRED"),
        s.lease(expected_head=r["head"]),
    ):
        pass


@pytest.mark.parametrize("restores", ["c" * 64, "0" * 64, None])
def test_missing_or_ambiguous_rollback_refuses(setup, restores):
    s, a, b = setup
    first = select(s, a)
    with pytest.raises(ValueError, match="ROLLBACK_EVIDENCE"):
        s.change(
            grant(b, first["head"], action="ROLLBACK", restores=restores), approved=True
        )
    assert s.current()["selected"] == a


def test_rollback_cannot_substitute_different_release(setup):
    s, a, b = setup
    first = select(s, a)
    second = select(s, b, first["head"])
    with pytest.raises(ValueError, match="TARGET_MISMATCH"):
        s.change(
            grant(b, second["head"], action="ROLLBACK", restores=first["head"]),
            approved=True,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_receipt",
        "wrong_receipt",
        "changed_code",
        "extra_code",
        "copied_identity",
        "linked_code",
    ],
)
def test_incomplete_hash_namespace_and_native_identity_refusal(setup, mutation):
    s, a, _ = setup
    root = Path(a["root"])
    receipt = Path(a["receipt"])
    file = root / "python/python.exe"
    if mutation == "missing_receipt":
        receipt.unlink()
    elif mutation == "wrong_receipt":
        receipt.write_bytes(b"{}")
    elif mutation == "changed_code":
        file.write_bytes(b"changed")
    elif mutation == "extra_code":
        (root / "unexpected").write_bytes(b"x")
    elif mutation == "copied_identity":
        data = file.read_bytes()
        replacement = file.with_suffix(".copy")
        replacement.write_bytes(data)
        os.replace(replacement, file)
    else:
        os.link(file, root / "extra-link")
    with pytest.raises((ValueError, OSError)):
        select(s, a)
    assert not list(s.store.root.iterdir())


def test_root_and_record_namespace_substitution_refuse(setup):
    s, a, _ = setup
    select(s, a)
    old = s.store.root.with_name("preserved-old")
    s.store.root.rename(old)
    s.store.root.mkdir()
    with pytest.raises(ValueError, match="ROOT_SUBSTITUTION"):
        s.current()


@pytest.mark.parametrize(
    "kind",
    [
        "foreign",
        "gap",
        "record_identity",
        "corrupt_json",
        "wrong_previous",
        "duplicate_operation",
    ],
)
def test_corrupted_record_history_never_defaults_to_old_version(setup, kind):
    s, a, b = setup
    first = select(s, a)
    select(s, b, first["head"])
    root = s.store.root
    if kind == "foreign":
        (root / "unknown").write_bytes(b"x")
    elif kind == "gap":
        (root / "r0001.pending").rename(root / "r0003.pending")
        (root / "r0001.json").rename(root / "r0003.json")
    elif kind == "record_identity":
        raw = (root / "r0002.json").read_bytes()
        (root / "r0002.pending").unlink()
        (root / "r0002.json").unlink()
        (root / "r0002.pending").write_bytes(raw)
        os.link(root / "r0002.pending", root / "r0002.json")
    elif kind == "corrupt_json":
        (root / "r0002.pending").write_bytes(b"broken")
    else:
        path = root / "r0002.pending"
        envelope = strict(path.read_bytes())
        if kind == "wrong_previous":
            envelope["record"]["previous"] = "0" * 64
        else:
            envelope["record"]["operation"] = strict(
                (root / "r0001.json").read_bytes()
            )["record"]["operation"]
        path.write_bytes(encoded(envelope))
    with pytest.raises(ValueError):
        s.current()


def test_two_concurrent_writers_only_one_expected_cut_wins(setup):
    s, a, b = setup
    barrier = threading.Barrier(2)
    out = []

    def run(target):
        barrier.wait()
        try:
            out.append(select(s, target))
        except ValueError as e:
            out.append(str(e))

    threads = [threading.Thread(target=run, args=(target,)) for target in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(2)
        assert not t.is_alive()
    assert sum(isinstance(r, dict) for r in out) == 1
    assert len(s.store.records()) == 1


def test_launch_lease_blocks_reselection(setup):
    s, a, b = setup
    first = select(s, a)
    errors = []
    with s.lease(expected_head=first["head"]):
        t = threading.Thread(
            target=lambda: capture(lambda: select(s, b, first["head"]), errors)
        )
        t.start()
        t.join(1)
        assert not t.is_alive()
    assert errors and "BUSY" in errors[0]
    assert s.current()["selected"] == a


def capture(action, errors):
    try:
        action()
    except ValueError as error:
        errors.append(str(error))


def test_capacity_refuses_without_resetting_any_history(setup, monkeypatch):
    import scripts.release_selection as module

    s, a, b = setup
    first = select(s, a)
    monkeypatch.setattr(module, "MAX_RECORDS", 1)
    with pytest.raises(ValueError, match="CAPACITY_NO_RESET"):
        select(s, b, first["head"])
    assert s.current()["selected"] == a


def test_native_factory_and_fixture_operational_substitution_refuse(setup):
    s, a, _ = setup
    with pytest.raises(ValueError):
        ReleaseSelector()
    with pytest.raises(ValueError):
        NativeSelectionStore()
    with pytest.raises(ValueError):
        NativeSelectionStore(root=r"D:\AtlasRuntime\releases", native_root=[1, 2, 3])
    with pytest.raises(ValueError):
        ReleaseSelector(store=s.store, verifier=NativeInstalledReleaseVerifier())
    with pytest.raises(ValueError):
        validate_spec(a, "WINDOWS_LOCAL")


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_duplicate_or_nonfinite_declaration_refuses(raw):
    with pytest.raises(ValueError):
        strict(raw)


def test_observed_complete_tail_removal_is_not_silent_rollback(setup):
    s, a, b = setup
    first = select(s, a)
    select(s, b, first["head"])
    (s.store.root / "r0002.pending").unlink()
    (s.store.root / "r0002.json").unlink()
    with pytest.raises(ValueError, match="OBSERVED_ROLLBACK"):
        s.current()


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "INVALID"),
        ("expected_head", False),
        ("expected_head", {}),
        ("restores", {}),
        ("domain", "WINDOWS_LOCAL"),
        ("schema", "OLD"),
        ("extra", True),
    ],
)
def test_malformed_grant_refuses_before_publication(setup, field, value):
    s, a, _ = setup
    g = grant(a)
    g[field] = value
    with pytest.raises(ValueError):
        s.change(g, approved=True)
    assert not list(s.store.root.iterdir())


def test_native_selector_requires_actual_clock_not_a_boolean_callback():
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="NATIVE_DEPENDENCIES"):
        ReleaseSelector(
            store=NativeSelectionStore.__new__(NativeSelectionStore),
            verifier=NativeInstalledReleaseVerifier(),
            clock=SimpleNamespace(require_operational=lambda _: True),
        )


def test_wrong_explicit_release_refuses_before_verification_child(setup, monkeypatch):
    selector, a, b = setup
    result = select(selector, a)
    monkeypatch.setattr(
        selector.verifier,
        "open",
        lambda _: pytest.fail("Unapproved release verification"),
    )
    with (
        pytest.raises(ValueError, match="EXACT_RELEASE_REQUIRED"),
        selector.lease(expected_head=result["head"], expected_release=b["release"]),
    ):
        pass


def test_failed_native_close_attempts_all_resources_and_retains_failed_handle():
    from types import SimpleNamespace

    store = NativeSelectionStore.__new__(NativeSelectionStore)
    store.owner = None
    store.poisoned = False
    store.file_handles = [1, 2]
    store.mutex = 3
    store.output = SimpleNamespace(handles=[4, 5])
    calls = []

    def close(handle):
        calls.append(handle)
        return handle != 1

    store.native = SimpleNamespace(w=SimpleNamespace(close_handle=close))
    with pytest.raises(OSError, match="CLOSE_UNCONFIRMED"):
        store.close()
    assert calls == [1, 2, 3, 5, 4]
    assert (
        store.file_handles == [1] and store.mutex is None and not store.output.handles
    )
    store.native.w.close_handle = lambda _: True
    store.close()
    assert not store.file_handles
