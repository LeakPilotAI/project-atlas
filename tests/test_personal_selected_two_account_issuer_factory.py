"""Prove the selected native issuer FACTORY never manufactures an operator.

All synthetic ports are replaced exclusively inside these tests. Production
factory accepts only exact genuine native classes and a preexisting real
local operator record, bound two ledgers, held original Job and UTC.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import (
    personal_selected_two_account_issuer_factory as factory,
)

DIGEST = "a" * 64
def model(monkeypatch):
    events = []
    observer = {"pid": 123, "creation_filetime": 456, "image": "D:\\TEST.exe"}
    accounts = {"QUALITY_DIPS": "a" * 64, "HYPERLIQUID": "b" * 64}

    class Job:
        _phase = "PREINCEPTION_COORDINATION_READY"
        release_digest = DIGEST
        _identity = deepcopy(observer)

        def verify_still_running(self):
            events.append("job_live")
            return True

        def _inspect_roots(self):
            from scripts.observation_runtime.personal_existing_native_resource_evidence import (
                inspect_two_lane_native_roots,
            )
            return inspect_two_lane_native_roots()

        def require_exact_roster(self, *, qd, perp):
            events.append("job_roster")
            if qd["lane"] != "QUALITY_DIPS" or perp["lane"] != "HYPERLIQUID":
                raise ValueError("FAKE_FOREIGN_ROSTER")
            return True

    class Release:
        artifact_digest = DIGEST

    class Clock:
        pass

    class Reader:
        pass

    class Operator:
        def __init__(self, lane, reader, clock, enrollment):
            self._lane = lane
            self.reader = reader
            self.clock = clock
            self.runtime_id = "ORIGINAL"
            self.clock_profile = factory.VERSION_SAFE_PROFILE
            self.enrollment = enrollment
            self.accounts = accounts

        def activation(self, action):
            events.append("operator_" + action)
            return {
                "actions": ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"],
                "release_digest": DIGEST, "origin": "LOCAL_OPERATOR",
                "accounts": self.accounts,
                "approval": "SAME_GENUINE_RECORD",
            }

    class Ledger:
        def __init__(self, enrollment, manifest):
            self.manifest = manifest
            self.images = SimpleNamespace(
                enrollment=factory.digest(enrollment),
                root_id=enrollment["resources"]["coordination"]["native_id"],
            )

    class Custody:
        def __init__(self, ledger):
            self.ledger = ledger

    class Issuer:
        def __init__(self):
            self.installation = None

        def bind_installation(self, installation):
            assert self.installation is None
            self.installation = installation

    class Files:
        pass

    class Readback:
        pass

    class Bootstrap:
        def __init__(self, *, enrollment, publication, issuer, clock, readback):
            self.enrollment = enrollment
            self.publication = publication
            self.issuer = issuer
            self.clock = clock
            self.readback = readback

        def scope(self):
            return {"issued_for": self.enrollment["lane"]}

    class Owner:
        def __init__(self, *, enrollment, authority, inception_intent, ledger, read_only):
            events.append("open_" + enrollment["lane"])
            if getattr(authority, "fail_owner", False):
                raise ValueError("TEST_SECOND_OWNER_UNAVAILABLE")
            self.enrollment = enrollment
            self.authority = authority
            self.ledger = ledger
            self.inception_intent = inception_intent
            self.read_only = read_only
            self.closed = False

        def close(self):
            self.closed = True
            events.append("close_" + self.enrollment["lane"])

    class Technical:
        def __init__(self, *, bootstrap, release, clock, runtime_id,
                     ownership, ledger, files, current, engine, clock_profile):
            assert bootstrap.clock is clock
            assert ownership.ledger is ledger
            assert runtime_id == "ORIGINAL"
            assert current is engine is None
            assert clock_profile == factory.VERSION_SAFE_PROFILE

    class Installation:
        def __init__(self, *, policy, reader, identity, technical, clock,
                     components, release_digest, accounts):
            assert reader is identity.reader and clock is identity.clock
            assert release_digest == DIGEST
            assert policy["simulation_only"] is True
            assert len(components) == 4
            self.identity = identity
            self.technical = technical

    class Publisher:
        def __init__(self, *, bootstrap, custody, ownership, observer, files):
            events.append("publisher_" + bootstrap.enrollment["lane"])
            assert bootstrap.publication is custody
            assert observer()["schema"] == "QD_OP_PROCESS_ID_V1"
            self.bootstrap = bootstrap
            self.custody = custody
            self.ownership = ownership
            self.files = files

    class Pair:
        def __init__(self, *, original_job, quality_dips, hyperliquid):
            assert type(original_job) is Job
            assert quality_dips.bootstrap.issuer.installation is not None
            assert hyperliquid.bootstrap.issuer.installation is not None
            events.append("genuine_pair_assembled")
            self.publishers = (quality_dips, hyperliquid)

    mapping = {
        "RetainedSelectedNativeOwnerPreflight": Job,
        "NativePersonalReleaseIdentity": Release,
        "NativeVersionSafePaperOperatorClock": Clock,
        "NativePersonalActivationReader": Reader,
        "NativePersonalOperatorAuthority": Operator,
        "PersonalNativeCoordination": Ledger,
        "PersonalPublicationCustody": Custody,
        "PersonalPublicationIssuer": Issuer,
        "NativePersonalInceptionFiles": Files,
        "NativePersonalInitialReadback": Readback,
        "PersonalInceptionBootstrap": Bootstrap,
        "NativePersonalWriterOwnership": Owner,
        "NativePersonalTechnicalChecks": Technical,
        "PersonalOperatorInstallation": Installation,
        "PersonalInceptionPublisher": Publisher,
        "NativeSelectedTwoAccountSimulatedInception": Pair,
    }
    for name, value in mapping.items():
        monkeypatch.setattr(factory, name, value)
    monkeypatch.setattr(factory, "observe_self", lambda: deepcopy(observer))
    monkeypatch.setattr(
        factory, "require_version_safe_release_digest",
        lambda *, clock, runtime_id, release_digest:
        type(clock) is Clock and runtime_id == "ORIGINAL"
        and release_digest == DIGEST,
    )
    from scripts.observation_runtime import (
        personal_existing_native_resource_evidence as native,
    )
    monkeypatch.setattr(
        native, "inspect_two_lane_native_roots",
        lambda: {"native_root_total": 12,
                 "existing_empty_root_namespaces": 10,
                 "all_twelve_distinct_and_empty": False},
    )
    monkeypatch.setattr(
        factory, "validate_personal_inception",
        lambda e: (e["lane"], e["native_enrollment"], e["parameters"]),
    )
    job, release, clock, reader = Job(), Release(), Clock(), Reader()
    enrollments, operators, ledgers = {}, {}, {}
    for lane in factory.LANES:
        n = {"lane": lane, "release_digest": DIGEST,
             "resources": {"coordination": {"native_id": [1, 2, 3]}},
             "writers": {"w": {"schema": "QD_OP_PROCESS_ID_V1", **observer}}}
        e = {"lane": lane, "native_enrollment": n,
             "parameters": {"opening_cash": "1000"},
             "personal_policy": {"simulation_only": True}}
        enrollments[lane] = e
        operators[lane] = Operator(lane, reader, clock, n)
        ledgers[lane] = Ledger(n, e["parameters"])
        accounts[lane] = factory.digest(n)
    args = {"job": job, "release": release, "clock": clock,
            "reader": reader, "operators": operators, "ledgers": ledgers,
            "enrollments": enrollments, "runtime_id": "ORIGINAL"}
    return args, events


def test_explicit_genuine_port_factory_only_wires_publishers_never_opens_accounts(
        monkeypatch):
    args, events = model(monkeypatch)
    pair, owners = factory.assemble_selected_two_account_inception(**args)
    assert type(pair) is factory.NativeSelectedTwoAccountSimulatedInception
    assert set(owners) == set(factory.LANES)
    assert events.count("genuine_pair_assembled") == 1
    assert events.count("operator_INITIALIZE_SIMULATED_ACCOUNTS") == 2
    assert not any("publish_account" in e or "order" in e for e in events)
    for owner in owners.values():
        owner.close()
    assert len([x for x in events if x.startswith("close_")]) == 2


@pytest.mark.parametrize("change", [
    "fake_job", "wrong_phase", "wrong_release", "foreign_clock",
    "missing_ledger", "missing_authority", "foreign_reader",
    "unknown_account", "writer_changed", "wrong_release_digest",
    "lost_approval_action", "foreign_approval_record", "foreign_operator_clock",
    "other_account_digests", "incorrect_ledger_digest",
    "wrong_writer_process", "not_started_native_roots",
])
def test_missing_native_financial_prerequisite_refuses_before_writer_create(
        monkeypatch, change):
    args, events = model(monkeypatch)
    if change == "fake_job":
        args["job"] = object()
    elif change == "wrong_phase":
        args["job"]._phase = "PREINCEPTION"
    elif change == "wrong_release":
        args["release"].artifact_digest = "f" * 64
    elif change == "foreign_clock":
        args["clock"] = object()
    elif change == "missing_ledger":
        args["ledgers"].pop("HYPERLIQUID")
    elif change == "missing_authority":
        args["operators"]["QUALITY_DIPS"] = object()
    elif change == "foreign_reader":
        args["reader"] = object()
    elif change == "unknown_account":
        args["enrollments"].pop("QUALITY_DIPS")
    elif change == "writer_changed":
        args["enrollments"]["QUALITY_DIPS"]["native_enrollment"]["writers"] = {}
    elif change == "wrong_release_digest":
        args["enrollments"]["QUALITY_DIPS"]["native_enrollment"]["release_digest"] = "f" * 64
    elif change == "lost_approval_action":
        op = args["operators"]["QUALITY_DIPS"]
        old = op.activation
        def no_init(action):
            row = old(action)
            row["actions"] = ["READ_ONLY"]
            return row
        op.activation = no_init
    elif change == "foreign_approval_record":
        op = args["operators"]["QUALITY_DIPS"]
        old = op.activation
        def foreign(action):
            row = old(action)
            row["approval"] = "FOREIGN"
            return row
        op.activation = foreign
    elif change == "foreign_operator_clock":
        args["operators"]["HYPERLIQUID"].clock = object()
    elif change == "other_account_digests":
        args["operators"]["HYPERLIQUID"].accounts = {"QUALITY_DIPS": "1"*64,
                                                      "HYPERLIQUID": "2"*64}
    elif change == "incorrect_ledger_digest":
        args["ledgers"]["QUALITY_DIPS"].images.enrollment = "1"*64
    elif change == "wrong_writer_process":
        args["job"]._identity["pid"] = 999
    elif change == "not_started_native_roots":
        from scripts.observation_runtime import (
            personal_existing_native_resource_evidence as native,
        )
        monkeypatch.setattr(
            native, "inspect_two_lane_native_roots",
            lambda: {"native_root_total": 12,
                     "existing_empty_root_namespaces": 12,
                     "all_twelve_distinct_and_empty": True},
        )
    with pytest.raises((ValueError, KeyError, TypeError)):
        factory.assemble_selected_two_account_inception(**args)
    assert not any(x.startswith("open_") for x in events)


def test_partial_factory_failure_closes_previously_opened_native_owner(
        monkeypatch):
    args, events = model(monkeypatch)
    args["operators"]["HYPERLIQUID"].fail_owner = True
    with pytest.raises(ValueError, match="TEST_SECOND_OWNER_UNAVAILABLE"):
        factory.assemble_selected_two_account_inception(**args)
    assert "open_QUALITY_DIPS" in events
    assert "close_QUALITY_DIPS" in events
    assert "genuine_pair_assembled" not in events


def test_real_classes_reject_missing_original_native_credentials_and_journals():
    # This test does NOT monkeypatch the product factory. It is a real
    # negative test against the selected-original missing issuer path.
    with pytest.raises(ValueError, match="GENUINE_NATIVE_PORTS"):
        factory.assemble_selected_two_account_inception(
            job=None, release=None, clock=None, reader=None,
            operators={}, ledgers={}, enrollments={}, runtime_id=None)
