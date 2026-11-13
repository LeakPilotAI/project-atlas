"""DISPOSABLE contract tests only; never install sources or create PAPER accounts."""
import copy
import os

import pytest
from app.services.paper_financial_replay import digest
from test_quality_dips_current_producer import fixture, proof

from scripts.observation_runtime import atlas_r20_qd_selected_source_worker as worker
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)


class FakeVersionSafeClock:
    def __init__(self, stamps):
        self.stamps = stamps
        self.accepted = True

    def __call__(self):
        return self.stamps[0]

    def require_operational(self, runtime_id):
        if not self.accepted or runtime_id != "SYNTHETIC-TEST-RUNTIME":
            raise ValueError("DISPOSABLE_TEST_CLOCK_REFUSED")
        return True


def synthetic_ports(monkeypatch):
    f = fixture(monkeypatch)
    clock = FakeVersionSafeClock(f.s.now)
    f.s.clock = clock
    f.s.archive.clock = clock
    f.s.archive._ports = (f.s.archive.images, f.s.auth, clock)

    f.cut["execution_domain"] = "OPERATIONAL"
    f.flags.receipt_domain = "OPERATIONAL"
    f.owner = f.reopen("OPERATIONAL")

    def verify_input(context, *, now):
        if (context != {
                "enrollment": f.s.e,
                "execution_domain": "OPERATIONAL",
                "input": f.cut,
        } or not f.flags.accepted):
            return False
        return proof("QD_CURRENT_RESEARCH_VERIFIED_V1", context,
                     execution_domain="OPERATIONAL")

    f.owner.input_authority.verify_current = verify_input
    # The existing fixture issuer only knows DISPOSABLE domain. Replace it
    # explicitly with a TEST-ONLY OP domain port; never production authority.
    f.s.auth.verify_publication = lambda c, h, p, sources, now: (
        sources["current_input"]["input"] == f.cut
        and sources["current_input"]["acceptance"]["execution_domain"] == "OPERATIONAL"
        and sources["current_input"]["acceptance"]["binding"] == digest({
            "enrollment": f.s.e,
            "execution_domain": "OPERATIONAL",
            "input": f.cut,
        })
    )
    original = object.__new__(RetainedSelectedNativeOwnerPreflight)
    original._phase = "PREINCEPTION"
    original._identity = {
        "pid": os.getpid(),
        "creation_filetime": 100,
        "image": "SYNTHETIC_INSTALLED_CHILD",
    }
    original.image = r"D:\AtlasRuntime\releases\SYNTHETIC_TEST_ONLY\python\python.exe"
    original.release_digest = f.s.e["release_digest"]
    original.liveness = True
    original.verify_still_running = lambda: original.liveness
    monkeypatch.setattr(worker, "NativeVersionSafePaperOperatorClock", FakeVersionSafeClock)
    monkeypatch.setattr(worker, "observe_self", lambda: copy.deepcopy(original._identity))
    monkeypatch.setattr(worker, "_installed_qd_source", lambda owner: True)
    monkeypatch.setattr(worker, "require_version_safe_release_digest",
                        lambda **kwargs: True)
    return f, original, clock


def runner(f, owner, clock):
    return worker.SelectedOwnerQDForwardPublisher(
        owner=owner, producer=f.owner, clock=clock,
        runtime_id="SYNTHETIC-TEST-RUNTIME",
    )


def test_original_selected_source_handoff_is_one_shot_native_replay_only(monkeypatch):
    f, owner, clock = synthetic_ports(monkeypatch)
    before = copy.deepcopy(f.s.s.files)
    bound = runner(f, owner, clock)
    result = bound.publish_one()
    assert result["schema"] == worker.SCHEMA
    assert result["status"] == "ORIGINAL_NATIVE_SOURCE_CAS_READBACK_ONLY"
    assert result["native_readback_observed"] is True
    assert result["revision"] == 1
    assert result["packet_sha256"] == digest(f.owner.read_publication(0.2))
    assert result["candidate_bundles"] == 1
    assert all(result[name] is False for name in (
        "independent_source_issuer_accepted",
        "valuation_issuer_accepted", "financial_inception_authorized",
        "paper_startup_authorized", "live_trading_authorized",
    ))
    assert f.s.s.files != before  # Disposable non-financial image only.
    unchanged = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError, match="USED"):
        bound.publish_one()
    assert f.s.s.files == unchanged


@pytest.mark.parametrize("problem", [
    "disposable", "foreign_release", "fake_clock", "wrong_job_type",
    "wrong_process", "missing_native_owner", "wrong_image",
    "revoked_clock", "bad_selection", "phase",
])
def test_no_borrowed_fixture_or_wrong_native_identity_can_publish(monkeypatch, problem):
    f, owner, clock = synthetic_ports(monkeypatch)
    if problem == "disposable":
        f.owner = f.reopen("DISPOSABLE")
    elif problem == "foreign_release":
        f.owner.enrollment["release_digest"] = "f" * 64
    elif problem == "fake_clock":
        clock = lambda: f.s.now[0]
    elif problem == "wrong_job_type":
        owner = object()
    elif problem == "wrong_process":
        owner._identity["pid"] += 1
    elif problem == "missing_native_owner":
        owner.liveness = False
    elif problem == "wrong_image":
        monkeypatch.setattr(worker, "_installed_qd_source", lambda owner: False)
    elif problem == "revoked_clock":
        clock.accepted = False
    elif problem == "bad_selection":
        monkeypatch.setattr(worker, "require_version_safe_release_digest",
                            lambda **kwargs: False)
    else:
        owner._phase = "INITIAL_READBACK_PENDING"
    original = copy.deepcopy(f.s.s.files)
    with pytest.raises((ValueError, AttributeError, TypeError)):
        runner(f, owner, clock)
    assert f.s.s.files == original


def test_unaccepted_original_input_refused_without_native_publication(monkeypatch):
    f, owner, clock = synthetic_ports(monkeypatch)
    f.flags.accepted = False
    original = copy.deepcopy(f.s.s.files)
    source = runner(f, owner, clock)
    with pytest.raises(ValueError):
        source.publish_one()
    with pytest.raises(ValueError, match="USED"):
        source.publish_one()
    assert f.s.s.files == original


def test_recheck_original_job_after_publication_and_never_retry(monkeypatch):
    f, owner, clock = synthetic_ports(monkeypatch)
    seen = []
    def verify():
        seen.append(1)
        return len(seen) <= 2
    owner.verify_still_running = verify
    source = runner(f, owner, clock)
    with pytest.raises(ValueError, match="ORIGINAL|UNCERTAIN"):
        source.publish_one()
    frozen = copy.deepcopy(f.s.s.files)
    assert len(seen) == 3
    with pytest.raises(ValueError, match="USED"):
        source.publish_one()
    assert f.s.s.files == frozen


def test_missing_real_installed_source_never_becomes_source_issuer():
    class Empty:
        image = r"D:\AtlasRuntime\releases\ORIGINAL\python\python.exe"
    assert worker._installed_qd_source(Empty()) is False
