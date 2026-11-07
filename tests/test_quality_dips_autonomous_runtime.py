"""V3 continuous native runtime acceptance, confined disposable dependencies."""
import copy
import os
from pathlib import Path

import pytest
from app.api.quality_dips_selected_paper import financial_view
from app.services.paper_financial_replay import number
from app.services.quality_dips_autonomous_runtime import AutonomousRuntime
from qd_autonomous_runtime_fixture import compose
from test_quality_dips_autonomous_paper import STAMP

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def system(tmp_path):
    value = os.environ.get("ATLAS_AUTO_RUNTIME_ROOT")
    if not value:
        pytest.skip("NOT EXECUTED: confined runtime root required")
    root = Path(value)
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-auto-runtime-")
    assert tmp_path.is_relative_to(root)
    x = compose(tmp_path, root, stamp=STAMP)
    try:
        yield x
    finally:
        x.x.close()


def view(s):
    r = s.runtime.readonly()
    return financial_view(reader=r, verifier=r, clock=s.x.clock,
                          account_id=s.n.m["epoch"], epoch=s.n.m["epoch"])


def advance(s, seq, kind="entry"):
    s.n.now[0] += 1
    return s.runtime.accept(s.frame(seq, kind))


def test_default_missing_authority_refuses_without_dependencies():
    with pytest.raises(ValueError, match="ACCEPTED_DEPENDENCIES"):
        AutonomousRuntime()


def test_continuous_session_entry_partial_full_live_reader(system):
    s = system
    assert s.runtime.start(s.grant) == "RUNNING"
    assert view(s)["cash"] == "1000"
    assert advance(s, 1)["filled"]
    assert number(view(s)["cash"]) == number("899.96")
    assert advance(s, 2, "partial")["filled"]
    v = view(s)
    assert number(next(iter(v["positions"].values()))["remaining"]) == number("0.6")
    assert advance(s, 3, "final")["filled"]
    v = view(s)
    assert number(v["cash"]) == number("1015.9136") and not v["positions"]
    assert number(v["realized"]["net"]) == number("15.9136")
    assert s.runtime.stop() == "STOPPED"
    assert len(s.x.pins.pin["entries"]) == 3


@pytest.mark.parametrize("flag", ["authority", "owner", "clock", "custody"])
def test_missing_local_acceptance_refuses_before_financial_effect(system, flag):
    s = system
    with s.n.ledger.connect(readonly=True) as db:
        before = db.execute("SELECT * FROM autonomous_control").fetchall()
    s.flags[flag] = False
    with pytest.raises(ValueError): s.runtime.start(s.grant)
    assert not s.x.pins.pin["entries"]
    with s.n.ledger.connect(readonly=True) as db:
        assert db.execute("SELECT * FROM autonomous_control").fetchall() == before


@pytest.mark.parametrize("kind", ["resources", "profile", "operational", "process"])
def test_version_identity_and_enrollment_separation(system, kind):
    s = system
    deps = {**s.deps, "enrollment": copy.deepcopy(s.enrollment)}
    if kind == "resources": deps["enrollment"]["reader_enrollment"]["epoch"] = "foreign"
    if kind == "profile": deps["enrollment"]["profile"] = "STRICT_MANUAL"
    if kind == "operational": deps["enrollment"]["scope"] = "LOCAL_ENROLLED"
    if kind == "process": deps["enrollment"]["process_identity"] = {}
    with pytest.raises(ValueError): AutonomousRuntime(**deps)


def test_duplicate_and_conflicting_sequence_do_not_repeat_financial_effect(system):
    s = system
    s.runtime.start(s.grant)
    frame = s.frame(1)
    first = s.runtime.accept(frame)
    assert first == s.runtime.accept(frame)
    frame["request"]["quotes"][0]["ask"] = "99"
    with pytest.raises(ValueError, match="SEQUENCE_CONFLICT"): s.runtime.accept(frame)
    assert len(s.x.pins.pin["entries"]) == 1 and s.runtime.halted


def test_pause_protective_exit_stop_preservation_and_report_only_revision(system):
    s = system
    s.runtime.start(s.grant)
    assert s.runtime.pause() == "PAUSED"
    assert not advance(s, 1)["filled"]
    assert s.runtime.stop() == "STOPPED"
    fresh = {**s.grant, "engine_grant": {**s.grant["engine_grant"], "session_id": "explicit-new-session"}}
    s.grant["engine_grant"]["session_id"] = "explicit-new-session"
    s.runtime.start(fresh)
    assert advance(s, 1)["filled"]
    s.runtime.pause()
    assert advance(s, 2, "partial")["filled"]
    before = view(s)
    s.n.now[0] += 1
    assert s.runtime.stop() == "STOPPED"
    after = view(s)
    assert before["source_identity"] == after["source_identity"]
    assert len(after["positions"]) == 1
    assert after["autonomous"]["session_state"] == "STOPPED"


@pytest.mark.parametrize("kind", ["disconnect", "gap", "expired", "clock", "writer", "custody"])
def test_interruption_revocation_and_no_automatic_recovery(system, kind):
    s = system
    s.runtime.start(s.grant)
    assert advance(s, 1)["filled"]
    frame = s.frame(2, "partial")
    if kind == "disconnect": frame["connected"] = False
    if kind == "gap": frame["sequence"] = 4
    if kind == "expired": s.n.now[0] += 3601
    if kind == "clock": s.n.now[0] -= 10
    if kind == "writer": s.flags["owner"] = False
    if kind == "custody": s.flags["custody"] = False
    with pytest.raises(ValueError): s.runtime.accept(frame)
    assert len(s.x.pins.pin["entries"]) == 1
    with pytest.raises(ValueError, match="NOT_RUNNING"): s.runtime.accept(s.frame(3))
    new = AutonomousRuntime(**s.deps)
    assert new.halted and new.grant is None
    assert s.n.new().status() == "STOP_INCOMPLETE"


def test_unknown_native_publication_blocks_drain_and_restart(system, monkeypatch):
    s = system
    s.runtime.start(s.grant)
    def fail(*args): raise OSError("Injected publication interruption")
    monkeypatch.setattr(s.x.target, "publish", fail)
    with pytest.raises(ValueError, match="FINANCIAL_UNKNOWN"): advance(s, 1)
    assert s.runtime.stop() == "STOP_INCOMPLETE"
    assert view(s)["status"] == "UNKNOWN"


@pytest.mark.parametrize("pending", [1, False])
def test_nonparticipating_pending_writer_refuses_clean_stop(system, pending):
    s = system
    s.runtime.start(s.grant)
    s.flags["pending"] = pending
    assert s.runtime.stop() == "STOP_INCOMPLETE"
    assert s.n.engine.entry_admission_closed and s.runtime.halted


def test_report_failure_after_native_ack_refuses_further_financial_dispatch(system, monkeypatch):
    s = system
    s.runtime.start(s.grant)
    def failed(*args): raise OSError("Injected report persistence failure")
    monkeypatch.setattr(s.x.service, "publish", failed)
    with pytest.raises(OSError): advance(s, 1)
    assert len(s.x.pins.pin["entries"]) == 1
    assert view(s)["status"] in ("UNKNOWN", "UNAVAILABLE")
    assert s.runtime.stop() == "STOP_INCOMPLETE"


def test_accepted_observation_cannot_substitute_source_or_session(system):
    s = system
    s.runtime.start(s.grant)
    frame = s.frame(1)
    frame["session_id"] = "foreign-session"
    with pytest.raises(ValueError): s.runtime.accept(frame)
    assert not s.x.pins.pin["entries"]


def test_authority_signature_binding_is_not_a_caller_boolean(system, monkeypatch):
    s = system
    original = s.deps["authority"].verify
    def bad(kind, request, now):
        return {**original(kind, request, now), "binding": "0" * 64}
    monkeypatch.setattr(s.deps["authority"], "verify", bad)
    with pytest.raises(ValueError, match="AUTHORITY_REFUSED"): s.runtime.start(s.grant)
    assert not s.x.pins.pin["entries"]


def test_loop_has_no_startup_side_effect_or_automatic_resume(system):
    s = system
    class Empty:
        def next(self, timeout): raise AssertionError("Unstarted runtime polled a source")
    with pytest.raises(ValueError, match="NOT_RUNNING"): s.runtime.run(Empty())
    assert not s.x.pins.pin["entries"]


def test_exclusive_report_cutoff_catches_up_only_at_next_trusted_tick(system):
    s = system
    s.runtime.start(s.grant)
    assert advance(s, 1)["filled"]
    first = s.x.service.history()[-1]
    assert first["report"]["source"]["cutoff_revision"] == 0
    s.runtime._catch_up_report(s.n.now[0])
    assert s.x.service.history()[-1] == first
    before = view(s)["source_identity"]
    s.n.now[0] += 1
    s.runtime._catch_up_report(s.n.now[0])
    last = s.x.service.history()[-1]
    assert last["report"]["source"]["cutoff_revision"] == 1
    assert number(last["report"]["cash"]["closing"]) == number("899.96")
    assert view(s)["source_identity"] == before
    s.runtime._catch_up_report(s.n.now[0])
    assert s.x.service.history()[-1] == last
