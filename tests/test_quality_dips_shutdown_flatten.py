"""Explicit shutdown mode over actual disposable V4/V5 native financial stores."""

import copy
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import number
from test_quality_dips_autonomous_binding import step
from test_quality_dips_autonomous_binding import (
    system as system,  # noqa: PLC0414 - pytest fixture re-export
)


def quotes(s, damage=None):
    def observe(position, timeout):
        if damage == "disconnect":
            raise OSError("SYNTHETIC_PROVIDER_DISCONNECT")
        frame = s.x.frame(1, "hold")
        q = frame["request"]["quotes"][0]
        if damage == "stale":
            q["source_timestamp"] -= 60
        if damage == "closed":
            q["session"] = "CLOSED"
        if damage == "liquidity":
            q["bid_size"] = "0.001"
        return {"quotes": [q], "observation": frame["request"]["observation"]}

    return SimpleNamespace(observe=observe)


@pytest.mark.parametrize("partial", [False, True])
def test_graceful_flatten_native_cash_and_duplicate(system, partial):
    s = system
    s.runtime.start(s.grant)
    assert step(s, 1)["filled"]
    if partial:
        assert step(s, 2, "partial")["filled"]
    s.x.n.now[0] += 1
    result = s.runtime.stop(mode="SHUTDOWN_FLATTEN", evidence=quotes(s))
    assert result["status"] == "FLATTENED", result
    assert result["position_state"] == "FLAT" and result["positions"] == {}
    assert number(result["cash"]) == number("1015.9136" if partial else "1019.912")
    assert result["process_shutdown_allowed"] is True
    pin = copy.deepcopy(s.x.x.pins.current())
    assert s.runtime.stop(mode="SHUTDOWN_FLATTEN", evidence=quotes(s)) == result
    assert s.x.x.pins.current() == pin
    assert s.x.n.engine.reconcile()["source_revision"] == (3 if partial else 2)


@pytest.mark.parametrize(
    "damage", ["stale", "closed", "disconnect", "liquidity", "missing"]
)
def test_no_fabricated_exit_allows_only_verified_owned_shutdown(system, damage):
    s = system
    s.runtime.start(s.grant)
    step(s, 1)
    pin = s.x.x.pins.current()
    result = s.runtime.stop(
        mode="SHUTDOWN_FLATTEN",
        evidence=None if damage == "missing" else quotes(s, damage),
    )
    assert result["status"] == "SHUTDOWN_INCOMPLETE", result
    assert result["position_state"] == "POSITION_OPEN", result
    assert result["process_shutdown_allowed"] is True
    assert s.x.x.pins.current() == pin
    with pytest.raises(ValueError):
        s.runtime.accept(s.x.frame(2, "final"))
    fresh = s.x.n.new()
    assert fresh.grant is None and fresh.status() == "STOP_INCOMPLETE"


def test_no_position_and_foreign_ownership_never_calls_close(system):
    s = system
    s.runtime.start(s.grant)
    s.x.flags["owner"] = False
    calls = []
    result = s.runtime.stop(
        mode="SHUTDOWN_FLATTEN",
        evidence=quotes(s),
        owned_close=SimpleNamespace(
            close_verified=lambda identity: calls.append(identity)
        ),
    )
    assert result["status"] == "SHUTDOWN_INCOMPLETE"
    assert not result["process_shutdown_allowed"] and not calls


def test_unknown_native_publication_no_clean_shutdown(system):
    s = system
    s.runtime.start(s.grant)
    step(s, 1)
    original = s.financial.delegate.publish

    def unknown(*args):
        original(*args)
        raise ValueError("SYNTHETIC_COMMIT_BEFORE_ACK")

    s.financial.delegate.publish = unknown
    result = s.runtime.stop(mode="SHUTDOWN_FLATTEN", evidence=quotes(s))
    assert result["status"] == "SHUTDOWN_INCOMPLETE"
    assert result["position_state"] == "UNKNOWN"
    assert len(s.x.x.pins.current()["entries"]) == 2
    assert s.runtime.stop(mode="SHUTDOWN_FLATTEN", evidence=quotes(s)) == result
    assert len(s.x.x.pins.current()["entries"]) == 2


def test_empty_account_flatten_and_emergency_stays_separate(system):
    s = system
    s.runtime.start(s.grant)
    result = s.runtime.stop(mode="SHUTDOWN_FLATTEN")
    assert result["status"] == "FLATTENED" and result["cash"] == "1000"
    assert not s.x.x.pins.current()["entries"]


@pytest.mark.parametrize("acknowledged", [True, False])
def test_exact_owned_close_and_failure_outcome(system, acknowledged):
    s = system
    s.runtime.start(s.grant)
    observed = []

    def close(identity):
        observed.append(identity)
        return acknowledged

    result = s.runtime.stop(
        mode="SHUTDOWN_FLATTEN", owned_close=SimpleNamespace(close_verified=close)
    )
    assert observed == [s.x.runtime.enrollment["process_identity"]]
    assert result["status"] == ("FLATTENED" if acknowledged else "SHUTDOWN_INCOMPLETE")
    assert s.runtime.stop(mode="SHUTDOWN_FLATTEN") == result
    assert len(observed) == 1


def test_persisted_shutdown_corruption_refuses_dashboard_read(system):
    s = system
    s.runtime.start(s.grant)
    assert s.runtime.stop(mode="SHUTDOWN_FLATTEN")["status"] == "FLATTENED"
    with s.x.n.ledger.connect() as db:
        db.execute("UPDATE autonomous_shutdown SET body='{}'")
    with pytest.raises(ValueError, match="SHUTDOWN_OUTCOME_CORRUPT"):
        s.x.x.cap.read_committed(s.x.n.m["epoch"], s.x.n.m["epoch"])
