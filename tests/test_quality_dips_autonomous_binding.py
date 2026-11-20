"""Actual FS2/FS3 and V3 continuous behavior under synthetic V4 acceptance."""

import copy
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from app.api.quality_dips_selected_paper import financial_view
from app.services.paper_financial_replay import number
from app.services.quality_dips_autonomous_binding import EnrolledAutonomousRuntime
from qd_autonomous_binding_fixture import build


@pytest.fixture
def system(tmp_path):
    value = os.environ.get("ATLAS_AUTO_RUNTIME_ROOT")
    if not value:
        pytest.skip("NOT EXECUTED: confined V5 root required")
    root = Path(value)
    assert root.parent == Path(__file__).resolve().parents[1] / "logs/diagnostics"
    assert root.name.startswith("qd-auto-runtime-") and tmp_path.is_relative_to(root)
    s = build(tmp_path, root)
    try:
        yield s
    finally:
        if s.runtime.grant is not None:
            s.runtime.stop()
        s.x.x.close()


def view(s):
    r = s.runtime.readonly()
    return financial_view(
        reader=r,
        verifier=r,
        clock=s.x.x.clock,
        account_id=s.x.n.m["epoch"],
        epoch=s.x.n.m["epoch"],
    )


def step(s, n, kind="entry"):
    s.x.n.now[0] += 1
    return s.runtime.accept(s.x.frame(n, kind))


def test_default_refusal():
    with pytest.raises(ValueError, match="DEPENDENCIES"):
        EnrolledAutonomousRuntime()


def test_full_v4_local_enrolled_contract_native_entry_partial_final(system):
    s = system
    assert s.runtime.enrollment["scope"] == "LOCAL_ENROLLED"
    assert s.runtime.enrollment["execution_domain"] == "DISPOSABLE_TEST"
    assert s.runtime.start(s.grant) == "RUNNING"
    assert step(s, 1)["filled"]
    assert number(view(s)["cash"]) == number("899.96")
    assert step(s, 2, "partial")["filled"]
    assert number(next(iter(view(s)["positions"].values()))["remaining"]) == number(
        "0.6"
    )
    assert step(s, 3, "final")["filled"]
    assert number(view(s)["cash"]) == number("1015.9136")
    assert view(s)["positions"] == {}
    assert s.runtime.stop() == "STOPPED"
    assert s.financial.cut()["source_revision"] == 3


@pytest.mark.parametrize(
    "damage",
    [
        "revoked",
        "expired",
        "clock",
        "foreign_root",
        "missing_writer",
        "unknown",
        "custody",
    ],
)
def test_refusal_before_financial_effect(system, damage):
    s = system
    assert s.runtime.start(s.grant) == "RUNNING"
    if damage == "revoked":
        s.f.flags["valid"] = False
    if damage == "expired":
        s.x.n.now[0] = s.native_grant["expires_at"]
    if damage == "clock":
        s.f.flags["clock"] = False
    if damage == "foreign_root":
        s.financial.e = s.financial.e.replace('"native_id":[', '"native_id":[999,', 1)
    if damage == "missing_writer":
        s.f.o["writers"].pop("source")
    if damage == "unknown":
        s.flags["unknown"] = True
    if damage == "custody":
        s.flags["custody"] = False
    before = copy.deepcopy(s.x.x.pins.current())
    with pytest.raises((ValueError, OSError)):
        step(s, 1)
    assert s.x.x.pins.current() == before
    assert s.runtime.stop() == "STOP_INCOMPLETE"


def test_duplicate_and_restart_no_effect(system):
    s = system
    s.runtime.start(s.grant)
    s.x.n.now[0] += 1
    frame = s.x.frame(1)
    first = s.runtime.accept(frame)
    pin = s.x.x.pins.current()
    assert s.runtime.accept(frame) == first and s.x.x.pins.current() == pin
    restarted = EnrolledAutonomousRuntime(
        runtime=s.x.runtime, admission=s.admission, financial=s.financial
    )
    with pytest.raises(ValueError):
        restarted.accept(s.x.frame(2, "partial"))
    with pytest.raises(ValueError):
        restarted.start(s.grant)
    assert s.x.x.pins.current() == pin
    # Reconstruct the actual engine from its durable SQL/native stores; do not
    # rely only on a new wrapper or the synthetic reservation port's memory.
    fresh_engine = s.x.n.new()
    assert fresh_engine.grant is None and fresh_engine.status() == "STOP_INCOMPLETE"
    with pytest.raises(ValueError, match="AUTO_START_REFUSED"):
        fresh_engine.start(s.inner_grant["engine_grant"])
    assert fresh_engine.reconcile()["source_revision"] == 1
    assert s.x.x.pins.current() == pin


def test_commit_before_ack_unknown_blocks_repeat_and_clean_stop(system):
    s = system
    s.runtime.start(s.grant)
    original = s.financial.delegate.publish

    def unknown(*args):
        original(*args)
        raise ValueError("COMMIT_BEFORE_ACK_UNKNOWN")

    s.financial.delegate.publish = unknown
    with pytest.raises(ValueError):
        step(s, 1)
    assert len(s.x.x.pins.current()["entries"]) == 1
    with pytest.raises(ValueError):
        step(s, 1)
    assert len(s.x.x.pins.current()["entries"]) == 1
    assert s.runtime.stop() == "STOP_INCOMPLETE"


def test_read_gets_preserve_files_and_overnight_stop(system):
    s = system
    s.runtime.start(s.grant)
    step(s, 1)
    assert s.runtime.stop() == "STOPPED"
    before = {p: p.read_bytes() for p in s.root.rglob("*.json")}
    assert view(s)["positions"]
    assert before == {p: p.read_bytes() for p in s.root.rglob("*.json")}


@pytest.mark.parametrize("schema", ["QD_AUTO_SESSION_FIXTURE_V1", "QD_OP_SESSION_V1"])
def test_fixture_or_manual_grant_substitution_refuses(system, schema):
    s = system
    grant = copy.deepcopy(s.grant)
    grant["runtime_grant"]["engine_grant"]["schema"] = schema
    before = s.x.x.pins.current()
    with pytest.raises(ValueError, match="NO_FIXTURE_MANUAL"):
        s.runtime.start(grant)
    assert s.x.x.pins.current() == before and not s.f.sessions.used


def test_publication_without_admitted_action_refuses(system):
    s = system
    before = s.x.x.pins.current()
    with pytest.raises(ValueError, match="ADMITTED_FINANCIAL_ACTION"):
        s.financial.publish({}, {}, {})
    assert s.x.x.pins.current() == before


@pytest.mark.parametrize(
    "field", ["account_id", "epoch", "policy_digest", "release_digest"]
)
def test_component_identity_equality_before_start(system, field):
    s = system
    from app.services.paper_financial_replay import body

    e = s.financial.enrollment
    e[field] = "f" * 64
    s.financial.e = body(e)
    before = s.x.x.pins.current()
    with pytest.raises(ValueError):
        s.runtime.start(s.grant)
    assert s.x.x.pins.current() == before


def test_revocation_during_native_commit_preserves_evidence(system):
    s = system
    s.runtime.start(s.grant)
    original = s.financial.delegate.publish

    def revoked(*args):
        result = original(*args)
        s.f.flags["valid"] = False
        return result

    s.financial.delegate.publish = revoked
    with pytest.raises(ValueError):
        step(s, 1)
    assert len(s.x.x.pins.current()["entries"]) == 1
    assert s.runtime.stop() == "STOP_INCOMPLETE"
    with pytest.raises(ValueError):
        step(s, 1)
    assert len(s.x.x.pins.current()["entries"]) == 1


def test_report_failure_after_commit_is_not_clean(system):
    s = system
    s.runtime.start(s.grant)

    def failed(*args):
        raise OSError("SYNTHETIC_REPORT_FAILURE")

    s.x.x.service.publish = failed
    with pytest.raises(OSError):
        step(s, 1)
    assert len(s.x.x.pins.current()["entries"]) == 1
    assert s.runtime.stop() == "STOP_INCOMPLETE"
    assert view(s)["status"] != "ACKNOWLEDGED"


def test_pause_refuses_new_entry(system):
    s = system
    s.runtime.start(s.grant)
    s.runtime.pause()
    assert step(s, 1)["filled"] is False
    assert s.runtime.stop() == "STOPPED"


def test_continuous_source_runs_all_automatic_actions(system):
    s = system
    s.runtime.start(s.grant)
    complete = Event()

    class Source:
        sequence = 0

        def next(self, timeout):
            if self.sequence < 3:
                self.sequence += 1
                s.x.n.now[0] += 1
                return s.x.frame(
                    self.sequence, ("entry", "partial", "final")[self.sequence - 1]
                )
            complete.set()
            s.x.runtime.stopped.wait(timeout)
            return None

    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(s.runtime.run, Source())
        assert complete.wait(20)
        assert s.runtime.stop() == "STOPPED"
        worker.result(timeout=5)
    assert s.financial.cut()["source_revision"] == 3
    assert number(view(s)["cash"]) == number("1015.9136")


def test_pause_allows_protective_partial_and_full_exits(system):
    s = system
    s.runtime.start(s.grant)
    assert step(s, 1)["filled"]
    assert s.runtime.pause() == "PAUSED"
    assert step(s, 2, "partial")["filled"]
    assert step(s, 3, "final")["filled"]
    assert s.runtime.stop() == "STOPPED"


def test_concurrent_same_operation_is_single_fill(system):
    s = system
    s.runtime.start(s.grant)
    s.x.n.now[0] += 1
    frame = s.x.frame(1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(s.runtime.accept, [frame, frame]))
    assert results[0] == results[1]
    assert len(s.x.x.pins.current()["entries"]) == 1


def test_read_failure_has_no_write_admission_or_lifecycle_mutation(system):
    s = system
    s.runtime.start(s.grant)
    before = {p: p.read_bytes() for p in s.root.rglob("*.json")}
    original = s.x.x.cap.read_committed

    def attempting_writer(*args):
        assert s.financial.actor is None
        s.financial.publish({}, {}, {})
        return original(*args)

    s.x.x.cap.read_committed = attempting_writer
    assert view(s)["status"] != "ACKNOWLEDGED"
    assert s.x.n.engine.status() == "RUNNING"
    assert before == {p: p.read_bytes() for p in s.root.rglob("*.json")}
    s.x.x.cap.read_committed = original


def test_competing_publication_component_is_refused(system):
    s = system
    s.runtime.start(s.grant)
    before = s.x.x.pins.current()
    s.x.n.engine.publication = s.financial.delegate
    with pytest.raises(ValueError):
        step(s, 1)
    assert s.x.x.pins.current() == before
    assert s.runtime.stop() == "STOP_INCOMPLETE"


def test_original_page_renders_native_bound_router_snapshots(system):
    from app.api.quality_dips_selected_paper import create_router

    s = system
    s.runtime.start(s.grant)
    r = s.runtime.readonly()
    router = create_router(
        reader=r,
        verifier=r,
        clock=s.x.x.clock,
        account_id=s.x.n.m["epoch"],
        epoch=s.x.n.m["epoch"],
    )
    get = next(route.endpoint for route in router.routes if "GET" in route.methods)
    frames = []
    for sequence, kind, cash, quantity in (
        (1, "entry", "899.96", "1"),
        (2, "partial", "943.9424", "0.6"),
        (3, "final", "1015.9136", None),
    ):
        assert step(s, sequence, kind)["filled"]
        payload = get()
        assert number(payload["cash"]) == number(cash)
        frames.append({"payload": payload, "cash": cash, "quantity": quantity})
    path = s.root / "synthetic-v5-render-snapshots.json"
    path.write_text(json.dumps(frames), encoding="utf-8")
    result = subprocess.run(
        ["node", "tests/quality_dips_autonomous_binding_frontend.cjs", str(path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_source_exception_closes_dispatch_and_preserves_position(system):
    s = system
    s.runtime.start(s.grant)
    step(s, 1)

    class Source:
        def next(self, timeout):
            raise OSError("SYNTHETIC_FEED_DISCONNECT")

    before = s.x.x.pins.current()
    with pytest.raises(OSError):
        s.runtime.run(Source())
    assert s.x.runtime.engine.dispatch_closed
    assert s.x.x.pins.current() == before
    assert s.runtime.stop() == "STOP_INCOMPLETE"
