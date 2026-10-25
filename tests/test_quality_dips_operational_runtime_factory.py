"""Operational schemas in new disposable roots; synthetic trust is not installed."""

import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_operational_runtime import compose_operational
from qd_operational_runtime_fixture import (
    components,
    native_dependencies,
    runtime_dependencies,
)
from test_operational_autonomous_store import system as system  # noqa: PLC0414


@pytest.fixture
def composed(system):
    s = system
    c = components(s)
    d = runtime_dependencies(s, c)
    holder = []
    native = native_dependencies(s, holder)

    # Test double of an externally enrolled verifier. No test verifier is shipped
    # in application source, installed, or discoverable through environment/CLI.
    class Installation:
        domain = "OPERATIONAL_ACCEPTED"
        valid = True

        @contextmanager
        def lease(self, request):
            proof = {
                "schema": "QD_AUTO_ACCEPTED_INSTALLATION_V1",
                "domain": self.domain,
                "binding": digest(request),
                "accepted": True,
                "revoked": False,
                "gates": dict.fromkeys(("B1", "C1", "D1", "E1"), "ACCEPTED"),
            }
            yield SimpleNamespace(snapshot=proof, check=lambda p: self.valid,
                                  check_components=lambda ports: ports == self.expected)

    kwargs = {
        "enrollment": s.e,
        "runtime_dependencies": d.deps,
        "native_dependencies": native,
        "store": s.store,
        "native_reader": s.module.OperationalAutonomousReader(**s.dependencies),
        "installation": Installation(),
    }
    kwargs['installation'].expected = {'runtime': dict(d.deps), 'native': dict(native),
                                       'store': s.store, 'reader': kwargs['native_reader']}
    try:
        yield SimpleNamespace(**locals())
    finally:
        c.archive.close()


def test_factory_default_refuses():
    with pytest.raises(ValueError, match="ACCEPTED_INSTALLATION"):
        compose_operational()


@pytest.mark.parametrize(
    "missing",
    [
        "enrollment",
        "runtime_dependencies",
        "native_dependencies",
        "store",
        "native_reader",
        "installation",
    ],
)
def test_missing_operational_dependency_refuses_before_effect(composed, missing):
    x = composed
    before = {p: p.read_bytes() for p in x.s.tmp_path.rglob("*.json")}
    with pytest.raises(ValueError):
        compose_operational(**{**x.kwargs, missing: None})
    assert before == {p: p.read_bytes() for p in x.s.tmp_path.rglob("*.json")}


@pytest.mark.parametrize("domain", ["DISPOSABLE_TEST", "DISPOSABLE", "LOCAL_FILE"])
def test_factory_rejects_synthetic_installation_domain(composed, domain):
    composed.kwargs["installation"].domain = domain
    with pytest.raises(ValueError, match="SYNTHETIC_OR_UNACCEPTED"):
        compose_operational(**composed.kwargs)


def test_factory_constructs_existing_native_components_without_starting(composed):
    x = composed
    r = compose_operational(**x.kwargs)
    x.holder.append(r)
    assert r.runtime.engine is x.c.engine
    assert r.financial.store is x.s.store
    assert r.runtime.halted and r.grant is None
    assert r.financial.cut()["execution_domain"] == "OPERATIONAL_ACCEPTED"


def test_factory_continuous_native_entry_and_graceful_shutdown(composed):
    from test_quality_dips_autonomous_paper import candidate, quote

    x = composed
    r = compose_operational(**x.kwargs)
    x.holder.append(r)
    inner = {**x.s.n.grant, "schema": "QD_AUTO_ENGINE_SESSION_V5"}
    local = {
        "schema": "QD_AUTO_LOCAL_SESSION_V3",
        "profile": x.s.e["profile"],
        "enrollment_digest": digest(r.runtime.enrollment),
        "engine_grant": inner,
        "max_observations": 10,
    }
    native = {
        "schema": "QD_AUTO_NATIVE_SESSION_V4",
        "session_id": inner["session_id"],
        "enrollment_digest": digest(x.s.e),
        "issued_at": inner["issued_at"],
        "expires_at": inner["expires_at"],
        "capabilities": ["AUTO_PAPER"],
    }
    grant = {
        "schema": "QD_AUTO_NATIVE_RUNTIME_SESSION_V5",
        "enrollment_digest": digest(r.enrollment),
        "native_grant": native,
        "runtime_grant": local,
    }
    assert r.start(grant) == "RUNNING"
    b = candidate(x.s.n)
    q = quote(x.s.n, b)
    frame = {
        "schema": "QD_AUTO_OBSERVATION_V3",
        "session_id": inner["session_id"],
        "sequence": 1,
        "observed_at": x.s.n.now[0],
        "connected": True,
        "request": {"bundles": [b], "quotes": [q], "observation": None},
    }
    assert r.accept(frame)["filled"]
    x.s.n.now[0] += 1

    def observe(position, timeout):
        q = quote(x.s.n, candidate(x.s.n))
        q.update(bid="110", ask="110.1")
        return {
            "quotes": [q],
            "observation": {
                "symbol": b["instrument"]["symbol"],
                "instrument": b["instrument"],
                "observed_at": x.s.n.now[0],
                "current": {"evidence_quality": "HIGH"},
            },
        }

    result = r.stop(mode="SHUTDOWN_FLATTEN", evidence=SimpleNamespace(observe=observe))
    assert result["status"] == "FLATTENED", result
    assert result["position_state"] == "FLAT"
    assert len(x.s.pin["entries"]) == 2
    assert r.stop(mode="SHUTDOWN_FLATTEN")["cash"] == result["cash"]
    with pytest.raises(ValueError):
        r.start(grant)


def test_factory_refuses_foreign_root_and_revoked_installation(composed):
    x = composed
    x.kwargs["installation"].valid = False
    with pytest.raises(ValueError):
        compose_operational(**x.kwargs)
    x.kwargs["installation"].valid = True
    foreign = copy.deepcopy(x.s.e)
    foreign["resources"]["source"]["native_id"][1] += 1
    with pytest.raises(ValueError):
        compose_operational(**{**x.kwargs, "enrollment": foreign})


def test_constructed_factory_rechecks_installation_before_actions(composed):
    x = composed
    r = compose_operational(**x.kwargs)
    x.holder.append(r)
    x.kwargs["installation"].valid = False
    before = copy.deepcopy(x.s.pin)
    with pytest.raises(ValueError, match="UNACCEPTED_INSTALLATION"), r._action():
        pytest.fail("Revoked installation reached runtime action")
    assert before == x.s.pin


def test_financial_cut_refuses_negative_presentation_verification(composed):
    x = composed
    r = compose_operational(**x.kwargs)
    x.holder.append(r)
    x.c.cap.verify = lambda *a, **kw: {'verified': False}
    with pytest.raises(ValueError, match='PRESENTATION_UNVERIFIED'):
        r.financial.cut()


def test_factory_refuses_caller_substituted_clock_despite_same_enrollment(composed):
    x = composed
    kwargs = {**x.kwargs, 'runtime_dependencies': {**x.d.deps, 'clock': object()}}
    with pytest.raises(ValueError, match='DEPENDENCY_SUBSTITUTION'):
        compose_operational(**kwargs)


def test_operational_stop_bridge_requires_retained_owned_close(composed):
    from app.services.quality_dips_stop_bridge import PaperStopBridge
    r = compose_operational(**composed.kwargs)
    with pytest.raises(ValueError, match='RETAINED_OWNED_CLOSE_REQUIRED'):
        PaperStopBridge(runtime=r, ownership=object())
