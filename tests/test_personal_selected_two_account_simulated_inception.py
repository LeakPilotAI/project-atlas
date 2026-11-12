"""No production authority from fixtures: simulate original held dual publication.

Never opens a real native account/Job or invokes a provider. Exact production
classes are replaced only inside pytest and never in installed Atlas code.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import ClassVar

import pytest

from scripts.observation_runtime import (
    personal_selected_two_account_simulated_inception as target,
)


def simulated_pair(monkeypatch):
    now = 1794488400
    release = "b" * 64
    activities = []
    accounts = {}
    reader = object()

    class Owner:
        _phase = "PREINCEPTION"
        release_digest = release
        _identity: ClassVar[dict] = {"pid": 123, "creation_filetime": 456, "image": "D:\\SYNTHETIC.exe"}
        origin: ClassVar[dict] = {
            "selected_artifact_digest_bound": True,
            "financial_writer_lease_issued": False,
            "financial_activation_published": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }

        def require_exact_roster(self, *, qd, perp):
            activities.append("roster")
            if getattr(self, "broken", False):
                raise ValueError("JOB_LOST")
            return True

        def _verify_original_job(self):
            activities.append("job")
            if getattr(self, "broken", False):
                raise ValueError("JOB_LOST")
            return True

        def observe_verified_initial_inceptions(self, *, qd_bootstrap, hl_bootstrap):
            activities.append("fs1_fs3")
            self._phase = "INITIAL_READBACK_ONLY"
            return {
                "both_initial_fs1_fs3_readbacks_verified": True,
                "financial_writer_lease_issued": False,
                "paper_start_authorized": False,
            }

        def verify_still_running(self):
            activities.append("readback")
            return True

    class Clock:
        def __call__(self):
            return now

    class NativeImage:
        def __init__(self, enrollment):
            self.enrollment = target.digest(enrollment)

    class Ledger:
        def __init__(self, enrollment):
            self.images = NativeImage(enrollment)

    class Custody:
        def __init__(self, ledger):
            self.ledger = ledger

    class Files:
        pass

    class InitialReadback:
        pass

    class Op:
        def activation(self, action):
            if action != "INITIALIZE_SIMULATED_ACCOUNTS":
                raise ValueError("ACTION_NOT_PERMITTED")
            return {
                "actions": list(getattr(self, "actions", (
                    "READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"))),
                "accounts": dict(accounts),
            }

    class Technical:
        pass

    class Installation:
        def __init__(self, operator, bootstrap, writer, files, ledger):
            self.identity = operator
            self.clock = operator.clock
            self.reader = reader
            self.policy = bootstrap.enrollment["personal_policy"]
            self.accounts = accounts
            self.release = release
            self.technical = Technical()
            t = self.technical
            t.bootstrap, t.ownership, t.ledger = bootstrap, writer, ledger
            t.files, t.current, t.engine = files, None, None
            t.clock = operator.clock
            t.clock_profile = operator.clock_profile

        @contextmanager
        def lease(self, scope):
            activities.append("installation")
            assert scope["action"] == "INITIALIZE_SIMULATED_ACCOUNTS"
            class Lease:
                snapshot: ClassVar[dict] = {"accepted": True}
                def check(self, snapshot):
                    return snapshot == self.snapshot
            yield Lease()

    class Issuer:
        def __init__(self, installation):
            self.installation = installation

    class Bootstrap:
        def __init__(self, lane, enrollment, clock):
            self.enrollment = {
                "lane": lane,
                "native_enrollment": enrollment,
                "parameters": {
                    "opening_cash": "1000",
                    "release": release,
                    "epoch": lane + "_SYNTHETIC",
                    "currency": "USD" if lane == "QUALITY_DIPS" else "USDC",
                    "opened_at": now - 1,
                },
                "personal_policy": {"policy": "SYNTHETIC_ONLY"},
            }
            self.clock = clock
            self.readback = InitialReadback()
            self.publication = Custody(Ledger(enrollment))
            self.issuer = None

        def scope(self):
            return {"operation_id": self.enrollment["lane"]}

    class Writer:
        def __init__(self, lane, enrollment, operator, bootstrap):
            self.enrollment = enrollment
            self.inception_intent = bootstrap.scope()
            self._lane = lane
            self.read_only = False
            self.ledger = bootstrap.publication.ledger
            self.authority = operator

    class Publisher:
        def __init__(self, bootstrap, writer, files):
            self.bootstrap = bootstrap
            self.ownership = writer
            self.custody = bootstrap.publication
            self.files = files
            self.fails = False
            self.grants_paper = False

        def publish(self):
            lane = self.bootstrap.enrollment["lane"]
            activities.append("published_" + lane)
            if self.fails:
                raise RuntimeError("SOURCE_PUBLICATION_FAILED")
            return {"financial_startup_authorized": self.grants_paper}

    monkeypatch.setattr(target, "RetainedSelectedNativeOwnerPreflight", Owner)
    monkeypatch.setattr(target, "PersonalInceptionPublisher", Publisher)
    monkeypatch.setattr(target, "PersonalInceptionBootstrap", Bootstrap)
    monkeypatch.setattr(target, "NativePersonalInceptionFiles", Files)
    monkeypatch.setattr(target, "NativePersonalInitialReadback", InitialReadback)
    monkeypatch.setattr(target, "NativePersonalWriterOwnership", Writer)
    monkeypatch.setattr(target, "PersonalPublicationCustody", Custody)
    monkeypatch.setattr(target, "PersonalNativeCoordination", Ledger)
    monkeypatch.setattr(target, "NativePersonalCoordinationImages", NativeImage)
    monkeypatch.setattr(target, "PersonalOperatorInstallation", Installation)
    monkeypatch.setattr(target, "NativePersonalOperatorAuthority", Op)
    monkeypatch.setattr(target, "NativePersonalTechnicalChecks", Technical)
    monkeypatch.setattr(target, "PersonalPublicationIssuer", Issuer)
    monkeypatch.setattr(target, "NativeVersionSafePaperOperatorClock", Clock)
    monkeypatch.setattr(
        target, "require_version_safe_release_digest",
        lambda *, clock, runtime_id, release_digest:
        bool(clock and runtime_id == "TEST_ORIGINAL" and release_digest == release),
    )
    monkeypatch.setattr(target, "observe_self", lambda: dict(Owner._identity))
    monkeypatch.setattr(
        target, "validate_personal_inception",
        lambda e: (
            e["lane"], e["native_enrollment"], e["parameters"]),
    )

    clock = Clock()
    owner = Owner()
    pubs = []
    for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
        enrollment = {"schema": "SYNTHETIC_ACCOUNT", "release_digest": release,
                      "lane": lane, "account_id": lane}
        accounts[lane] = target.digest(enrollment)
        bootstrap = Bootstrap(lane, enrollment, clock)
        op = Op()
        op._lane, op.enrollment, op.clock = lane, enrollment, clock
        op.accounts = accounts
        op.reader, op.runtime_id, op.clock_profile = reader, "TEST_ORIGINAL", "TEST_NTP"
        writer = Writer(lane, enrollment, op, bootstrap)
        files = Files()
        installation = Installation(op, bootstrap, writer, files, writer.ledger)
        bootstrap.issuer = Issuer(installation)
        pubs.append(Publisher(bootstrap, writer, files))
    return {"original_job": owner, "quality_dips": pubs[0],
            "hyperliquid": pubs[1]}, activities


def test_two_simulated_issuers_require_original_owner_and_acknowledge_once(monkeypatch):
    ports, log = simulated_pair(monkeypatch)
    coordinator = target.NativeSelectedTwoAccountSimulatedInception(**ports)
    assert coordinator._used is False
    assert not hasattr(coordinator, "start")
    assert not hasattr(coordinator, "place_order")
    assert not hasattr(coordinator, "live_trading")
    result = coordinator.publish_both_once()
    assert result["opened_lanes"] == ["QUALITY_DIPS", "HYPERLIQUID"]
    assert result["financial_writer_lease_issued"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert log.index("published_QUALITY_DIPS") < log.index("published_HYPERLIQUID")
    assert "fs1_fs3" in log
    assert ports["original_job"]._phase == "INITIAL_READBACK_ONLY"
    with pytest.raises(ValueError, match="ALREADY_ATTEMPTED"):
        coordinator.publish_both_once()


@pytest.mark.parametrize("bad", [
    "fake_owner", "fake_qd_publisher", "bad_source_origin", "stale_manifest",
    "missing_clock", "wrong_root_issuer", "missing_read_action",
    "extra_paper_action", "foreign_account", "wrong_job_phase", "parent_process",
])
def test_all_untrusted_or_incomplete_prerequisites_fail_before_account_write(
        monkeypatch, bad):
    ports, log = simulated_pair(monkeypatch)
    q_pub = ports["quality_dips"]
    if bad == "fake_owner":
        ports["original_job"] = object()
    elif bad == "fake_qd_publisher":
        ports["quality_dips"] = object()
    elif bad == "bad_source_origin":
        ports["original_job"].origin["selected_artifact_digest_bound"] = False
    elif bad == "stale_manifest":
        q_pub.bootstrap.enrollment["parameters"]["opened_at"] -= 300
    elif bad == "missing_clock":
        q_pub.bootstrap.clock = object()
    elif bad == "wrong_root_issuer":
        q_pub.bootstrap.issuer.installation = object()
    elif bad == "missing_read_action":
        q_pub.ownership.authority.actions = ["INITIALIZE_SIMULATED_ACCOUNTS"]
    elif bad == "extra_paper_action":
        q_pub.ownership.authority.actions = [
            "READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS", "AUTO_PAPER"]
    elif bad == "foreign_account":
        q_pub.ownership.authority.accounts = {"HYPERLIQUID": "f" * 64}
    elif bad == "wrong_job_phase":
        ports["original_job"]._phase = "INITIAL_READBACK_PENDING"
    elif bad == "parent_process":
        monkeypatch.setattr(target, "observe_self", lambda: {
            "pid": 999, "creation_filetime": 456, "image": "D:\\PARENT.exe"})
    with pytest.raises((ValueError, TypeError, AttributeError)):
        target.NativeSelectedTwoAccountSimulatedInception(**ports)
    assert not any(s.startswith("published_") for s in log)


@pytest.mark.parametrize("break_at", ["first", "second", "job_after_first", "unexpected_paper"])
def test_partial_opening_is_terminally_unknown_no_automatic_retry(monkeypatch, break_at):
    ports, log = simulated_pair(monkeypatch)
    coordinator = target.NativeSelectedTwoAccountSimulatedInception(**ports)
    if break_at == "first":
        ports["quality_dips"].fails = True
    elif break_at == "second":
        ports["hyperliquid"].fails = True
    elif break_at == "job_after_first":
        original = ports["original_job"]
        old = original._verify_original_job
        def interrupt():
            if "published_QUALITY_DIPS" in log:
                raise ValueError("ORIGINAL_JOB_DIED")
            return old()
        original._verify_original_job = interrupt
    elif break_at == "unexpected_paper":
        ports["hyperliquid"].grants_paper = True
    with pytest.raises((RuntimeError, ValueError)):
        coordinator.publish_both_once()
    assert ports["original_job"]._phase == "INITIAL_READBACK_PENDING"
    assert coordinator._used is True
    with pytest.raises(ValueError, match="ALREADY_ATTEMPTED"):
        coordinator.publish_both_once()
    assert log.count("published_QUALITY_DIPS") == 1
    assert log.count("published_HYPERLIQUID") <= 1
