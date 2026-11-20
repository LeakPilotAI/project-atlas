"""Genuine product stage D/E/F orchestration, disposable injected ports.

The sole production orchestrator requires original native classes, fresh
operator authority and one living original process. Tests substitute ports
ONLY through pytest monkeypatch; never touch original account directories.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.observation_runtime import (
    personal_selected_native_account_commissioner as target,
)

RELEASE = "a"*64
LANES = ("QUALITY_DIPS", "HYPERLIQUID")


def configured(monkeypatch):
    events = []
    class Release:
        artifact_digest = RELEASE
        def verify(self, *, release_digest):
            assert release_digest == RELEASE
            events.append("native_release_verify")
            return True
    class Admission:
        def __init__(self, release):
            self.release=release
        def verify(self, *, release_digest):
            self.release.verify(release_digest=release_digest)
            events.append("release_admission")
            return True
    class Owner:
        release_digest = RELEASE
        _phase = "PREINCEPTION"
        def __init__(self, release):
            self._release_admission = Admission(release)
            self.alive = True
        def verify_still_running(self):
            events.append("held_owner")
            if not self.alive:
                raise ValueError("ORIGINAL_WINDOWS_OWNER_GONE")
            return True
        def _inspect_roots(self):
            from scripts.observation_runtime.personal_existing_native_resource_evidence import (
                inspect_two_lane_native_roots,
            )
            return inspect_two_lane_native_roots()
        def require_exact_roster(self, *, qd, perp):
            assert qd["lane"]=="QUALITY_DIPS"
            assert perp["lane"]=="HYPERLIQUID"
            events.append("same_twelve_roles")
            return True
    class Clock:
        def require_operational(self, runtime_id):
            assert runtime_id=="EXACT_LOCAL_PROCESS"
            events.append("live_NTP")
            return True
    class Ledger:
        def __init__(self, lane, enrollment):
            self.manifest={"release":RELEASE,"opening_cash":"1000",
                "currency":"USD" if lane=="QUALITY_DIPS" else "USDC",
                "opened_at":1794489500}
            self.images=SimpleNamespace(enrollment=target.digest(enrollment))
    class Reader:
        def __init__(self, *, root=None, native_root=None, binding=None):
            self.root, self.native_root, self.binding = root, native_root, binding
    class Journal:
        def __init__(self, *, job, clock, runtime_id, ledgers, operator_scope):
            events.append("journal_scope_checked")
            assert type(job) is Owner and type(clock) is Clock
            assert runtime_id=="EXACT_LOCAL_PROCESS"
            assert operator_scope=={"human_exact_scope":"JOURNALS_ONLY"}
        def publish_both_original_journals_once(self):
            events.append("journal_publish")
            owner._phase="PREINCEPTION_COORDINATION_READY"
            return {"native_initial_journal_count":2,
                    "paper_start_authorized":False,
                    "live_trading_authorized":False}
    def publish_activation(**kw):
        events.append("activation_publish")
        assert kw["clock_profile"]==target.CLOCK_PROFILE
        assert kw["owned_job"] is owner and kw["prequalified_clock"] is clock
        assert kw["release_digest"]==RELEASE
        return {"schema":"ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1",
                "status":"NATIVE_VERIFIED",
                "root":kw["root"], "native_root":[1,2,3],
                "binding":{"id":[1,2,3],"sha256":"b"*64},
                "paper_start_authorized":False,
                "live_trading_authorized":False}
    class Writer:
        def __init__(self,lane):
            self.lane=lane
            self.closed=False
        def close(self):
            self.closed=True
            events.append("closed_"+self.lane)
    class Pair:
        def publish_both_once(self):
            events.append("accounts_publish")
            owner._phase="INITIAL_READBACK_ONLY"
            return {"status":"TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED",
                    "paper_start_authorized":False,
                    "live_trading_authorized":False}
    def assemble(**kwargs):
        events.append("original_issuer_factory")
        assert kwargs["job"] is owner and kwargs["release"] is release
        assert kwargs["clock"] is clock and kwargs["runtime_id"]=="EXACT_LOCAL_PROCESS"
        assert type(kwargs["reader"]) is Reader
        return Pair(),{lane:Writer(lane) for lane in LANES}
    monkeypatch.setattr(target,"RetainedSelectedNativeOwnerPreflight",Owner)
    monkeypatch.setattr(target,"NativePersonalReleaseIdentity",Release)
    monkeypatch.setattr(target,"NativeFinancialReleaseAdmission",Admission)
    monkeypatch.setattr(target,"NativeVersionSafePaperOperatorClock",Clock)
    monkeypatch.setattr(target,"PersonalNativeCoordination",Ledger)
    monkeypatch.setattr(target,"NativePersonalActivationReader",Reader)
    monkeypatch.setattr(target,"NativeOriginalTwoJournalPreinceptionPermit",Journal)
    monkeypatch.setattr(target,"commission_native_activation",publish_activation)
    monkeypatch.setattr(target,"assemble_selected_two_account_inception",assemble)
    monkeypatch.setattr(target,"require_version_safe_release_digest",
        lambda *,clock,runtime_id,release_digest:
            type(clock) is Clock and runtime_id=="EXACT_LOCAL_PROCESS"
            and release_digest==RELEASE)
    from scripts.observation_runtime import personal_existing_native_resource_evidence
    monkeypatch.setattr(personal_existing_native_resource_evidence,
        "inspect_two_lane_native_roots",
        lambda: {"native_root_total":12,"all_twelve_distinct_and_empty":True})
    release=Release()
    clock=Clock()
    owner=Owner(release)
    enrollments={lane:{"lane":lane} for lane in LANES}
    ledgers={lane:Ledger(lane,enrollments[lane]) for lane in LANES}
    obj=target.NativeSelectedPersonalAccountCommissioner(
        owner=owner,release=release,clock=clock,ledgers=ledgers,
        enrollments=enrollments,runtime_id="EXACT_LOCAL_PROCESS")
    return SimpleNamespace(
        obj=obj,owner=owner,release=release,clock=clock,events=events,
        enrollments=enrollments,ledgers=ledgers,Reader=Reader,
    )


def configured_native_c_d(monkeypatch):
    """Disposable typed-port rehearsal; never accesses real financial roots."""
    x = configured(monkeypatch)
    now = [1794489500]
    created = []
    failing = [None]
    monkeypatch.setattr(type(x.clock), "__call__", lambda self: now[0])

    class OriginalSelfJob:
        def verify(self):
            return True

        def selected_two_account_owner(self, *, qd, perp, release_digest,
                                       release_admission, successor_root_scope=None):
            assert qd["lane"] == "QUALITY_DIPS"
            assert perp["lane"] == "HYPERLIQUID"
            assert release_digest == RELEASE
            assert release_admission is x.owner._release_admission
            if successor_root_scope is not None:
                assert successor_root_scope.plan['successor_release'] == RELEASE[:40]
            return x.owner

    class NativeImages:
        def __init__(self, *, root, native_root, enrollment_digest):
            if failing[0] == root:
                raise OSError("DISPOSABLE_SECOND_NATIVE_HANDLE_REFUSAL")
            self.root = root
            self.root_id = native_root
            self.enrollment = enrollment_digest
            self.closed = False
            created.append(self)

        def close(self):
            self.closed = True

    class NativeLedger:
        def __init__(self, *, manifest, images, path):
            self.manifest = manifest
            self.images = images
            self.path = path

    monkeypatch.setattr(target, "NativeOriginalSelfJob", OriginalSelfJob)
    monkeypatch.setattr(target, "PersonalNativeCoordination", NativeLedger)
    from scripts.observation_runtime import personal_coordination_store, personal_paper_inception
    monkeypatch.setattr(personal_coordination_store, "NativePersonalCoordinationImages", NativeImages)
    monkeypatch.setattr(
        personal_paper_inception, "validate_personal_inception",
        lambda item: (item["lane"], item["native_enrollment"], item["parameters"]),
    )
    candidates = {}
    for lane in LANES:
        manifest = {
            "release": RELEASE, "opened_at": 1794489500,
            "opening_cash": "1000",
            "currency": "USD" if lane == "QUALITY_DIPS" else "USDC",
        }
        enrollment = {
            "lane": lane, "release_digest": RELEASE,
            "inception_digest": target.digest(manifest),
            "resources": {"coordination": {
                "path": r"D:\AtlasPaper\DISPOSABLE_ONLY" + chr(92) + lane,
                "native_id": [1, 2, 3] if lane == "QUALITY_DIPS" else [4, 5, 6],
            }},
        }
        candidates[lane] = {
            "lane": lane, "native_enrollment": enrollment, "parameters": manifest,
        }
    kwargs = {
        "self_job": OriginalSelfJob(), "release": x.release,
        "clock": x.clock, "runtime_id": "EXACT_LOCAL_PROCESS",
        "inceptions": candidates, "admission": x.owner._release_admission,
    }
    return SimpleNamespace(kwargs=kwargs, created=created, now=now,
                           failing=failing, candidates=candidates)


def test_c_d_binds_two_real_native_port_types_without_initialization(monkeypatch):
    x = configured_native_c_d(monkeypatch)
    commissioner, images = target.bind_original_native_two_account_commissioner(
        **x.kwargs)
    assert commissioner.phase == "PREINCEPTION_READY"
    assert list(images) == list(LANES)
    assert len(x.created) == 2
    assert all(not image.closed for image in images.values())
    assert commissioner.owner._phase == "PREINCEPTION"
    for image in images.values():
        image.close()
    assert all(image.closed for image in x.created)


@pytest.mark.parametrize("case", [
    "stale_manifest", "second_handle_failure", "foreign_inception",
    "different_opening", "wrong_currency",
])
def test_c_d_refuses_invalid_native_or_expired_handoff_and_closes_ports(
        monkeypatch, case):
    x = configured_native_c_d(monkeypatch)
    if case == "stale_manifest":
        x.now[0] += 6
    elif case == "second_handle_failure":
        x.failing[0] = x.candidates["HYPERLIQUID"][
            "native_enrollment"]["resources"]["coordination"]["path"]
    elif case == "foreign_inception":
        x.candidates["HYPERLIQUID"]["native_enrollment"][
            "inception_digest"] = "f" * 64
    elif case == "different_opening":
        x.candidates["HYPERLIQUID"]["parameters"]["opened_at"] += 1
    else:
        x.candidates["HYPERLIQUID"]["parameters"]["currency"] = "USD"
    with pytest.raises((ValueError, OSError)):
        target.bind_original_native_two_account_commissioner(**x.kwargs)
    assert all(image.closed for image in x.created)


def test_one_original_c_d_production_call_passes_review_and_owns_native_ports(
        monkeypatch):
    x = configured_native_c_d(monkeypatch)
    approvals = {
        "personal_policy": {"preaccepted": "SYNTHETIC_TEST_ONLY"},
        "operator_acceptance_ids": {
            "QUALITY_DIPS": "TEST_QD", "HYPERLIQUID": "TEST_HL",
        },
        "approved_unstamped_manifest_digests": {
            "QUALITY_DIPS": "a" * 64, "HYPERLIQUID": "b" * 64,
        },
    }
    calls = []

    def reviewed_original_issuer(**kwargs):
        calls.append(kwargs)
        return x.candidates, x.kwargs["admission"]

    monkeypatch.setattr(
        target, "prepare_original_fresh_two_account_inceptions",
        reviewed_original_issuer,
    )
    commissioner, images = target.prepare_and_bind_reviewed_original_native_accounts(
        self_job=x.kwargs["self_job"], release=x.kwargs["release"],
        clock=x.kwargs["clock"], runtime_id=x.kwargs["runtime_id"],
        **approvals,
    )
    assert len(calls) == 1
    assert all(calls[0][key] == value for key, value in approvals.items())
    assert commissioner.phase == "PREINCEPTION_READY"
    assert list(images) == list(LANES)
    assert len(x.created) == 2
    for image in images.values():
        image.close()


def test_c_d_never_accepts_unowned_release_or_unaccepted_job(monkeypatch):
    x = configured_native_c_d(monkeypatch)
    x.kwargs["self_job"] = object()
    with pytest.raises(ValueError, match="EXACT_RETAINED_NATIVE_INPUTS"):
        target.bind_original_native_two_account_commissioner(**x.kwargs)
    assert x.created == []


def first(scope=None):
    return {"operator_scope":scope or {"human_exact_scope":"JOURNALS_ONLY"}}


def second():
    return {
        "root":r"D:\AtlasCustody\PersonalPaper\existing-original",
        "record_path":r"D:\Work\Project Atlas\operator\reviewed.json",
        "policy_path":r"D:\Work\Project Atlas\docs\ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json",
        "accounts_path":r"D:\Work\Project Atlas\operator\accounts.json",
        "qd_enrollment_path":r"D:\Work\Project Atlas\operator\qd.json",
        "perp_enrollment_path":r"D:\Work\Project Atlas\operator\hl.json",
    }


def third(x):
    return {"reader":x.Reader(),
            "operators":{lane:object() for lane in LANES},
            "inception_enrollments":{
                lane:{"native_enrollment":x.enrollments[lane]} for lane in LANES}}


def original_e_f_ports(monkeypatch):
    """Typed disposable activation/issuer ports, no real native writes."""
    x = configured(monkeypatch)
    policy = {"synthetic_local_review": "TEST_ONLY"}
    created = []

    from app.services import personal_paper_runtime
    from scripts.observation_runtime import personal_paper_inception, personal_local_authority
    monkeypatch.setattr(personal_paper_runtime, "validate_policy", lambda value: value)
    monkeypatch.setattr(personal_paper_inception, "validate_personal_inception",
                        lambda entry: (entry["lane"], entry["native_enrollment"],
                                       entry["parameters"]))

    class Operator:
        def __init__(self, *, policy, enrollment, reader, clock,
                     runtime_id, clock_profile, accounts):
            assert policy == {"synthetic_local_review": "TEST_ONLY"}
            assert type(reader) is x.Reader
            assert reader.root == second()["root"]
            assert reader.native_root == [1, 2, 3]
            assert reader.binding == {"id": [1, 2, 3], "sha256": "b" * 64}
            assert clock is x.clock
            assert runtime_id == "EXACT_LOCAL_PROCESS"
            assert clock_profile == target.CLOCK_PROFILE
            assert accounts == {lane: target.digest(x.enrollments[lane])
                                for lane in LANES}
            assert enrollment in list(x.enrollments.values())
            self.revoked = False
            created.append(self)

        def revoke(self):
            self.revoked = True

    monkeypatch.setattr(personal_local_authority, "NativePersonalOperatorAuthority",
                        Operator)
    inceptions = {
        lane: {"lane": lane, "native_enrollment": x.enrollments[lane],
               "parameters": x.ledgers[lane].manifest, "personal_policy": policy}
        for lane in LANES
    }
    return SimpleNamespace(x=x, policy=policy, inceptions=inceptions,
                           created=created)


def test_real_e_f_activation_receipt_binds_both_operators_and_accounts(monkeypatch):
    data = original_e_f_ports(monkeypatch)
    x = data.x
    x.obj.initialize_two_journals_once(**first())
    outcome = x.obj.publish_initialization_activation_and_open_both_once(
        **second(), personal_policy=data.policy,
        inception_enrollments=data.inceptions)
    assert outcome["schema"] == "ATLAS_PERSONAL_ORIGINAL_E_F_ACCOUNT_OPENING_V1"
    assert outcome["paper_start_authorized"] is False
    assert outcome["live_trading_authorized"] is False
    assert x.obj.phase == "TWO_ACCOUNTS_ACKNOWLEDGED"
    assert len(data.created) == 2
    assert all(port.revoked for port in data.created)
    assert x.events.index("activation_publish") < x.events.index("accounts_publish")
    with pytest.raises(ValueError, match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_initialization_activation_and_open_both_once(
            **second(), personal_policy=data.policy,
            inception_enrollments=data.inceptions)


def test_original_e_f_rejects_policy_conflict_before_activation(monkeypatch):
    data = original_e_f_ports(monkeypatch)
    x = data.x
    x.obj.initialize_two_journals_once(**first())
    data.inceptions["HYPERLIQUID"]["personal_policy"] = {"changed": True}
    with pytest.raises(ValueError, match="ONE_APPROVED_ACCOUNT_POLICY"):
        x.obj.publish_initialization_activation_and_open_both_once(
            **second(), personal_policy=data.policy,
            inception_enrollments=data.inceptions)
    assert x.obj.phase == "TWO_JOURNALS_ACKNOWLEDGED"
    assert "activation_publish" not in x.events
    assert data.created == []


def test_original_e_f_malformed_native_root_ack_is_terminal(monkeypatch):
    data = original_e_f_ports(monkeypatch)
    x = data.x
    x.obj.initialize_two_journals_once(**first())
    original = target.commission_native_activation

    def invalid_root(**kwargs):
        result = original(**kwargs)
        result["native_root"] = "NOT_A_NATIVE_ROOT_ID"
        return result

    monkeypatch.setattr(target, "commission_native_activation", invalid_root)
    with pytest.raises(ValueError, match="ORIGINAL_NATIVE_ACTIVATION_ROOT_REFUSED"):
        x.obj.publish_initialization_activation_and_open_both_once(
            **second(), personal_policy=data.policy,
            inception_enrollments=data.inceptions)
    assert x.obj.phase == "ACTIVATION_UNKNOWN"
    assert "accounts_publish" not in x.events
    with pytest.raises(ValueError, match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_initialization_activation_and_open_both_once(
            **second(), personal_policy=data.policy,
            inception_enrollments=data.inceptions)


def test_original_e_f_operator_failure_is_terminal_and_revokes_prior(monkeypatch):
    data = original_e_f_ports(monkeypatch)
    x = data.x
    x.obj.initialize_two_journals_once(**first())
    from scripts.observation_runtime import personal_local_authority
    original = personal_local_authority.NativePersonalOperatorAuthority
    calls = [0]

    def second_operator_fails(**kwargs):
        calls[0] += 1
        if calls[0] == 2:
            raise ValueError("SECOND_ORIGINAL_OPERATOR_REFUSED")
        return original(**kwargs)

    monkeypatch.setattr(personal_local_authority, "NativePersonalOperatorAuthority",
                        second_operator_fails)
    with pytest.raises(ValueError, match="SECOND_ORIGINAL_OPERATOR_REFUSED"):
        x.obj.publish_initialization_activation_and_open_both_once(
            **second(), personal_policy=data.policy,
            inception_enrollments=data.inceptions)
    assert x.obj.phase == "TWO_ACCOUNTS_UNKNOWN"
    assert len(data.created) == 1 and data.created[0].revoked
    assert "accounts_publish" not in x.events


def original_d_f_approval_ports(monkeypatch):
    """Disposable signed-record readback; always explicit, never financial."""
    data = original_e_f_ports(monkeypatch)
    from app.services import personal_paper_runtime
    from scripts.observation_runtime import personal_activation_commission
    from scripts.volume_inspector import windows_output

    monkeypatch.setattr(type(data.x.clock), "__call__",
                        lambda _self: 1794489500)
    monkeypatch.setattr(windows_output, "current_sid",
                        lambda: "SYNTHETIC_OPERATOR_ONLY")
    recorded = {"actions": ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"],
                "accounts": data.x.obj._digest}

    disk = {
        "record": recorded,
        "policy": data.policy,
        "accounts": data.x.obj._digest,
        "quality_dips_enrollment": data.x.enrollments["QUALITY_DIPS"],
        "hyperliquid_enrollment": data.x.enrollments["HYPERLIQUID"],
    }
    expected_paths = {
        "record": "record_path", "policy": "policy_path",
        "accounts": "accounts_path",
        "quality_dips_enrollment": "qd_enrollment_path",
        "hyperliquid_enrollment": "perp_enrollment_path",
    }

    def read_record(path, *, role):
        assert path == second()[expected_paths[role]]
        return disk[role]

    def validate_record(value, *, policy, operator_id, release, accounts, now,
                        action):
        assert value is recorded
        assert policy == data.policy
        assert operator_id == "SYNTHETIC_OPERATOR_ONLY"
        assert release == RELEASE
        assert accounts == data.x.obj._digest
        assert now == 1794489500
        assert action in recorded["actions"]
        return value

    monkeypatch.setattr(personal_activation_commission,
                        "read_bounded_activation_input", read_record)
    monkeypatch.setattr(personal_paper_runtime,
                        "validate_activation_record", validate_record)
    data.recorded = recorded
    data.disk = disk
    return data


def test_original_d_f_one_call_orders_journal_activation_and_both_accounts(
        monkeypatch):
    data = original_d_f_approval_ports(monkeypatch)
    outcome = data.x.obj.initialize_reviewed_original_two_accounts_once(
        operator_scope=first()["operator_scope"], initial_activation=second(),
        personal_policy=data.policy, inception_enrollments=data.inceptions)
    assert outcome["schema"] == "ATLAS_PERSONAL_ORIGINAL_D_F_TWO_ACCOUNT_SEQUENCE_V1"
    assert outcome["paper_start_authorized"] is False
    assert outcome["live_trading_authorized"] is False
    assert outcome["journals"]["native_initial_journal_count"] == 2
    assert outcome["simulated_accounts"]["status"] == (
        "TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED")
    assert data.x.obj.phase == "TWO_ACCOUNTS_ACKNOWLEDGED"
    assert data.x.events.index("journal_publish") < (
        data.x.events.index("activation_publish")
    ) < data.x.events.index("accounts_publish")
    assert len(data.created) == 2 and all(op.revoked for op in data.created)
    with pytest.raises(ValueError, match="REPLAY_OR_UNKNOWN"):
        data.x.obj.initialize_reviewed_original_two_accounts_once(
            operator_scope=first()["operator_scope"], initial_activation=second(),
            personal_policy=data.policy, inception_enrollments=data.inceptions)


@pytest.mark.parametrize("invalid", [
    "wrong_actions", "wrong_accounts", "missing_file", "bad_operator_scope",
    "policy_file_changed", "accounts_file_changed", "qd_file_changed",
    "hl_file_changed",
])
def test_original_d_f_refuses_bad_approval_before_first_journal(
        monkeypatch, invalid):
    data = original_d_f_approval_ports(monkeypatch)
    kw = {"operator_scope": first()["operator_scope"],
          "initial_activation": second(), "personal_policy": data.policy,
          "inception_enrollments": data.inceptions}
    if invalid == "wrong_actions":
        data.recorded["actions"] = ["READ_ONLY", "AUTO_PAPER"]
    elif invalid == "wrong_accounts":
        data.recorded["accounts"] = {"QUALITY_DIPS": "f" * 64}
    elif invalid == "missing_file":
        kw["initial_activation"]["record_path"] = ""
    elif invalid == "policy_file_changed":
        data.disk["policy"] = {"invalid": True}
    elif invalid == "accounts_file_changed":
        data.disk["accounts"] = {"QUALITY_DIPS": "f" * 64}
    elif invalid == "qd_file_changed":
        data.disk["quality_dips_enrollment"] = {"foreign": True}
    elif invalid == "hl_file_changed":
        data.disk["hyperliquid_enrollment"] = {"foreign": True}
    else:
        kw["operator_scope"] = {}
    with pytest.raises(ValueError, match="PERSONAL_D_F_"):
        data.x.obj.initialize_reviewed_original_two_accounts_once(**kw)
    assert data.x.obj.phase == "PREINCEPTION_READY"
    assert "journal_publish" not in data.x.events
    assert "accounts_publish" not in data.x.events


def test_real_product_bridge_orders_three_exact_irreversible_phases(monkeypatch):
    x=configured(monkeypatch)
    assert x.obj.phase=="PREINCEPTION_READY"
    a=x.obj.initialize_two_journals_once(**first())
    assert a["native_initial_journal_count"]==2
    assert x.obj.phase=="TWO_JOURNALS_ACKNOWLEDGED"
    b=x.obj.publish_initialization_activation_once(**second())
    assert b["status"]=="NATIVE_VERIFIED"
    assert x.obj.phase=="INITIALIZE_ACTIVATION_ACKNOWLEDGED"
    c=x.obj.initialize_two_accounts_once(**third(x))
    assert c["status"]=="TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED"
    assert x.obj.phase=="TWO_ACCOUNTS_ACKNOWLEDGED"
    assert x.events.index("journal_publish") < x.events.index("activation_publish")
    assert x.events.index("activation_publish") < x.events.index("accounts_publish")
    assert x.events[-2:]==["closed_HYPERLIQUID","closed_QUALITY_DIPS"]
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_accounts_once(**third(x))
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_journals_once(**first())
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_initialization_activation_once(**second())


@pytest.mark.parametrize("phase",["activation","accounts"])
def test_out_of_order_financial_effects_refuse_before_any_publication(monkeypatch,phase):
    x=configured(monkeypatch)
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        if phase=="activation":
            x.obj.publish_initialization_activation_once(**second())
        else:
            x.obj.initialize_two_accounts_once(**third(x))
    assert "journal_publish" not in x.events
    assert "activation_publish" not in x.events
    assert "accounts_publish" not in x.events


@pytest.mark.parametrize("alter",["missing_scope","bad_scope","dead_job",
     "foreign_release","mutated_enrollment","changed_native_owner_phase"])
def test_journal_admission_is_not_generic_execute_approval(monkeypatch,alter):
    x=configured(monkeypatch)
    kw=first()
    if alter=="missing_scope":kw["operator_scope"]=None
    if alter=="bad_scope":kw["operator_scope"]={"human_exact_scope":"AUTO_PAPER"}
    if alter=="dead_job":x.owner.alive=False
    if alter=="foreign_release":x.owner._release_admission.release=object()
    if alter=="mutated_enrollment":x.obj.enrollments["QUALITY_DIPS"]["lane"]="OTHER"
    if alter=="changed_native_owner_phase":x.owner._phase="CURRENT_READBACK_ONLY"
    with pytest.raises((ValueError,AssertionError)):
        x.obj.initialize_two_journals_once(**kw)
    assert "journal_publish" not in x.events


def test_activation_requires_all_six_explicit_original_paths(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    kw=second()
    kw["accounts_path"]=""
    with pytest.raises(ValueError,match="EXPLICIT_ACTIVATION_INPUTS_REQUIRED"):
        x.obj.publish_initialization_activation_once(**kw)
    assert x.obj.phase=="TWO_JOURNALS_ACKNOWLEDGED"
    assert "activation_publish" not in x.events


def test_activation_failure_is_terminal_unknown_not_restarted(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    def broken(**kw):
        x.events.append("activation_partial")
        raise OSError("TEST_ORIGINAL_ACTIVATION_UNKNOWN")
    monkeypatch.setattr(target,"commission_native_activation",broken)
    with pytest.raises(OSError,match="UNKNOWN"):
        x.obj.publish_initialization_activation_once(**second())
    assert x.obj.phase=="ACTIVATION_UNKNOWN"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_initialization_activation_once(**second())


def test_partial_journal_publication_does_not_replay(monkeypatch):
    x=configured(monkeypatch)
    def fail(*args,**kwargs):
        x.events.append("journal_partly_created")
        raise OSError("FIRST_COMMITTED_SECOND_UNKNOWN")
    monkeypatch.setattr(target.NativeOriginalTwoJournalPreinceptionPermit,
        "publish_both_original_journals_once",fail)
    with pytest.raises(OSError,match="SECOND_UNKNOWN"):
        x.obj.initialize_two_journals_once(**first())
    assert x.obj.phase=="JOURNALS_UNKNOWN"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_journals_once(**first())


@pytest.mark.parametrize("tamper",["reader","operators","enrollments","phase"])
def test_two_account_issuer_requires_bound_original_ports(monkeypatch,tamper):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    kw=third(x)
    if tamper=="reader":kw["reader"]=object()
    if tamper=="operators":kw["operators"].pop("HYPERLIQUID")
    if tamper=="enrollments":
        kw["inception_enrollments"]["QUALITY_DIPS"]["native_enrollment"]={"lane":"ALIEN"}
    if tamper=="phase":x.owner._phase="PREINCEPTION"
    with pytest.raises(ValueError):
        x.obj.initialize_two_accounts_once(**kw)
    assert "accounts_publish" not in x.events


def test_real_unmocked_production_bridge_refuses_without_native_owner():
    with pytest.raises(ValueError,match="EXACT_SELECTED_ORIGINAL_OWNER_REQUIRED"):
        target.NativeSelectedPersonalAccountCommissioner(
            owner=object(),release=object(),clock=object(),
            ledgers={},enrollments={},runtime_id="fake")


def activate_to_two_accounts(x):
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    x.obj.initialize_two_accounts_once(**third(x))


def postinit(x, *, root=None):
    result = second()
    result["root"] = root or r"D:\AtlasCustody\PersonalPaper\postinit-simulated-scope"
    result["record_path"] = r"D:\Work\Project Atlas\operator\postinit-approved.json"
    return result


def stub_original_data_operator_record(monkeypatch,x,*,actions=None):
    from scripts.observation_runtime import personal_activation_commission
    action_list = (["READ_ONLY","CONNECT_APPROVED_DATA"]
                   if actions is None else actions)
    monkeypatch.setattr(
        personal_activation_commission,"read_bounded_activation_input",
        lambda path,role: {
            "actions":action_list,"origin":"LOCAL_OPERATOR",
            "release_digest":RELEASE,"accounts":x.obj._digest,
        })


def test_stage_g_uses_distinct_issuer_and_never_starts_paper(monkeypatch):
    x=configured(monkeypatch)
    activate_to_two_accounts(x)
    stub_original_data_operator_record(monkeypatch,x)
    result=x.obj.publish_postinception_data_activation_once(**postinit(x))
    assert result["status"]=="NATIVE_VERIFIED"
    assert x.obj.phase=="POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED"
    assert x.events.count("activation_publish")==2
    assert x.events.count("accounts_publish")==1
    assert x.events[-1]=="activation_publish"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))


@pytest.mark.parametrize("invalid",[
    "initial_root_reused","initial_root_case_alias","c_drive",
    "wrong_record_actions","initialization_action_reused","auto_paper_action",
    "absent_hyperliquid_source_approval","wrong_account_digests","wrong_release",
])
def test_stage_g_never_reuses_preactivation_or_accepts_auto_paper(
        monkeypatch,invalid):
    x=configured(monkeypatch)
    activate_to_two_accounts(x)
    kw=postinit(x)
    actions=None
    if invalid=="initial_root_reused":
        kw["root"]=second()["root"]
    elif invalid=="initial_root_case_alias":
        kw["root"]=second()["root"].upper()
    elif invalid=="c_drive":
        kw["record_path"]=r"C:\Users\unaccepted\data_approval.json"
    elif invalid=="wrong_record_actions":
        actions=["CONNECT_APPROVED_DATA"]
    elif invalid=="initialization_action_reused":
        actions=["READ_ONLY","INITIALIZE_SIMULATED_ACCOUNTS"]
    elif invalid=="auto_paper_action":
        actions=["READ_ONLY","AUTO_PAPER"]
    elif invalid=="absent_hyperliquid_source_approval":
        actions=[]
    elif invalid=="wrong_account_digests":
        x.obj._digest["HYPERLIQUID"]="0"*64
    elif invalid=="wrong_release":
        x.owner.release_digest="b"*64
    stub_original_data_operator_record(monkeypatch,x,actions=actions)
    with pytest.raises((ValueError,AssertionError)):
        x.obj.publish_postinception_data_activation_once(**kw)
    assert x.events.count("activation_publish")==1


def test_stage_g_partial_publication_terminal_and_no_retry(monkeypatch):
    x=configured(monkeypatch)
    activate_to_two_accounts(x)
    stub_original_data_operator_record(monkeypatch,x)
    def unknown(**kwargs):
        x.events.append("data_activation_unknown")
        raise OSError("SECOND_ACTIVATION_MAY_HAVE_COMMITTED")
    monkeypatch.setattr(target,"commission_native_activation",unknown)
    with pytest.raises(OSError,match="MAY_HAVE_COMMITTED"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))
    assert x.obj.phase=="DATA_ACTIVATION_UNKNOWN"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))


@pytest.mark.parametrize("phase", ["E", "G"])
@pytest.mark.parametrize("field", [
    "paper_start_authorized", "live_trading_authorized",
])
@pytest.mark.parametrize("corruption", ["omitted", "string_false"])
def test_original_activation_ack_must_explicitly_deny_financial_start(
        monkeypatch, phase, field, corruption):
    x = configured(monkeypatch)
    if phase == "E":
        x.obj.initialize_two_journals_once(**first())
        operation, arguments, unknown = (
            x.obj.publish_initialization_activation_once,
            second(), "ACTIVATION_UNKNOWN",
        )
    else:
        activate_to_two_accounts(x)
        stub_original_data_operator_record(monkeypatch, x)
        operation, arguments, unknown = (
            x.obj.publish_postinception_data_activation_once,
            postinit(x), "DATA_ACTIVATION_UNKNOWN",
        )

    def malformed_ack(**kwargs):
        result = {
            "schema": "ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1",
            "status": "NATIVE_VERIFIED",
            "binding": {"id": [1, 2, 3], "sha256": "b" * 64},
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
        if corruption == "omitted":
            result.pop(field)
        else:
            result[field] = "false"
        return result

    monkeypatch.setattr(target, "commission_native_activation", malformed_ack)
    with pytest.raises(ValueError, match="ACTIVATION_UNVERIFIED"):
        operation(**arguments)
    assert x.obj.phase == unknown
    with pytest.raises(ValueError, match="REPLAY_OR_UNKNOWN"):
        operation(**arguments)


def test_stage_g_requires_real_initial_fs1_fs3_not_just_journals(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    stub_original_data_operator_record(monkeypatch,x)
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))


def test_writer_handle_close_failure_leaves_account_outcome_unknown_and_closes_all(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    events=x.events
    class Publisher:
        def publish_both_once(self):
            x.owner._phase="INITIAL_READBACK_ONLY"
            events.append("two_accounts_acknowledged")
            return {"status":"TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED",
                    "paper_start_authorized":False,"live_trading_authorized":False}
    class Writer:
        def __init__(self,lane):self.lane=lane
        def close(self):
            events.append("close_"+self.lane)
            if self.lane=="HYPERLIQUID":
                raise OSError("HYPERLIQUID_NATIVE_WRITER_CLOSE_UNKNOWN")
    monkeypatch.setattr(target,"assemble_selected_two_account_inception",
                        lambda **kw:(Publisher(),{lane:Writer(lane) for lane in LANES}))
    with pytest.raises(OSError,match="CLOSE_UNKNOWN"):
        x.obj.initialize_two_accounts_once(**third(x))
    assert x.obj.phase=="TWO_ACCOUNTS_UNKNOWN"
    assert events[-2:]==["close_HYPERLIQUID","close_QUALITY_DIPS"]
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_accounts_once(**third(x))


def original_fresh_stage_c_model(monkeypatch):
    """Only stubs select/clock/Windows ports, not production account grant."""
    from copy import deepcopy
    from scripts.observation_runtime import (
        personal_current_selected_dual_account_draft as draft,
        personal_existing_native_resource_evidence as roots_module,
        personal_paper_inception as inception_module,
    )
    from app.services import personal_paper_runtime as runtime
    from app.services import paper_financial_replay as ledger
    T=1794500100
    class Release:
        artifact_digest=RELEASE
        def verify(self, *, release_digest):
            assert release_digest==RELEASE
            return {"source_commit":"test-only"}
    class Job:
        identity={"pid":432,"creation_filetime":123456789,
                  "image":r"D:\ATLAS_SELECTED_TEST_PYTHON.exe"}
        def verify(self):return True
    class Clock:
        def __init__(self):self.stamp=T
        def __call__(self):return self.stamp
        def require_operational(self,runtime_id):
            assert runtime_id=="ORIGINAL_SELECTED"
    class Admission:
        def __init__(self, *, release):self.release=release
        def verify(self, *, release_digest):
            assert release_digest==self.release.artifact_digest
            return {"selected_artifact_digest_bound":True}
    roots={"native_root_total":12,"existing_empty_root_namespaces":12,
           "all_twelve_distinct_and_empty":True,"lanes":{}}
    candidate={"status":"TWO_CURRENT_RELEASE_ACCOUNT_DRAFTS_UNACCEPTED_NO_FINANCE",
               "selected_artifact_digest":RELEASE,"original_native_root_count":12,
               "native_account_inceptions_published":0,
               "operator_financial_approval_accepted":False,
               "paper_start_authorized":False,"live_trading_authorized":False,
               "accounts":{}}
    for idx,lane in enumerate(LANES):
        manifest={
            "schema":"TEST_ONLY_MANIFEST","opening_cash":"1000",
            "currency":"USD" if lane=="QUALITY_DIPS" else "USDC",
            "release":RELEASE,"opened_at":T-123,"epoch":lane+"_EPOCH",
            "fees_bps":"2","initial_net_r":"0",
        }
        native_resources={}
        root_rows={}
        for k,role in enumerate(("source","projection","report",
                                "control","coordination","custody")):
            identity=[1,idx*6+k+1,999]
            native_resources[role]={"native_id":identity,
                "path":r"D:\DISPOSABLE_ATLAS_ORIGINAL_INPUTS"
                        +"\\"+lane+"\\"+role}
            root_rows[role]={"native_id":identity,
                             "existing_empty_namespace_verified":True}
        native={"lane":lane,"release_digest":RELEASE,"epoch":manifest["epoch"],
                "resources":native_resources,
                "writers":None,"acceptance_id":None}
        candidate["accounts"][lane]={
            "unaccepted_historical_parameters":manifest,
            "unaccepted_historical_enrollment":native,
            "unaccepted_historical_report_scope":{"policy_digest":"historic"},
            "opening_timestamp_historical_stale":True,
            "operator_approval_unissued":True,
            "fee_rights_unreviewed":True,
            "fs1_fs3_not_published":True,
            "operational_market_rights_unaccepted":True,
        }
        roots["lanes"][lane]={"roots":root_rows}
    monkeypatch.setattr(target,"NativeOriginalSelfJob",Job)
    monkeypatch.setattr(target,"NativePersonalReleaseIdentity",Release)
    monkeypatch.setattr(target,"NativeVersionSafePaperOperatorClock",Clock)
    monkeypatch.setattr(target,"NativeFinancialReleaseAdmission",Admission)
    monkeypatch.setattr(target,"require_version_safe_release_digest",
        lambda *,clock,runtime_id,release_digest:
            type(clock) is Clock and runtime_id=="ORIGINAL_SELECTED"
            and release_digest==RELEASE)
    monkeypatch.setattr(roots_module,"inspect_two_lane_native_roots",lambda:deepcopy(roots))
    monkeypatch.setattr(draft,"inspect",lambda:deepcopy(candidate))
    monkeypatch.setattr(runtime,"validate_policy",lambda p:deepcopy(p))
    monkeypatch.setattr(ledger,"validate_manifest",lambda m:m)
    monkeypatch.setattr(inception_module,"validate_personal_inception",
        lambda e:(e["lane"],e["native_enrollment"],e["parameters"]))
    digests={lane:target.digest({k:v for k,v in candidate["accounts"][lane]
         ["unaccepted_historical_parameters"].items() if k!="opened_at"})
         for lane in LANES}
    approvals={lane:"OPERATOR_REVIEWED_"+lane for lane in LANES}
    kw={"self_job":Job(),"release":Release(),"clock":Clock(),
        "runtime_id":"ORIGINAL_SELECTED","personal_policy":{"scope":"TEST_ONLY"},
        "operator_acceptance_ids":approvals,
        "approved_unstamped_manifest_digests":digests}
    return SimpleNamespace(kw=kw, draft=candidate, roots=roots)


def conservative_stage_c_review(monkeypatch):
    from copy import deepcopy
    from app.services.hyperliquid_forward_flat_paper_policy import (
        CONSERVATIVE_LOCAL_FEE_POLICY_ID,
        derive_reviewable_conservative_hl_manifest,
    )
    from test_perp_financial_v2 import manifest as perp_fixture

    x = original_fresh_stage_c_model(monkeypatch)
    historical = deepcopy(perp_fixture())
    historical.update(
        schema="PAPER_EPOCH_PERP_OPERATIONAL_V1",
        release=RELEASE, provenance="ACCEPTED_PERP_PAPER_PARAMETERS_V1",
        opened_at=x.kw["clock"]() - 123,
        epoch="HYPERLIQUID_EPOCH",
    )
    historical["perp_policy"].update(
        maker_bps="1.5", taker_bps="4.5", slippage_bps="2",
        fee_schedule_id="PENDING_E1_VERIFIED_FEE_SCHEDULE",
    )
    x.draft["accounts"]["HYPERLIQUID"][
        "unaccepted_historical_parameters"] = deepcopy(historical)
    amended = derive_reviewable_conservative_hl_manifest(historical)
    x.kw["hl_cost_amendment"] = CONSERVATIVE_LOCAL_FEE_POLICY_ID
    x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = target.digest(
        {k: v for k, v in amended.items() if k != "opened_at"})
    return SimpleNamespace(x=x, historical=historical, amended=amended)


def test_original_stage_c_amended_fee_terms_keep_all_original_native_bindings(
        monkeypatch):
    review = conservative_stage_c_review(monkeypatch)
    x = review.x
    entries, admission = target.prepare_original_fresh_two_account_inceptions(
        **x.kw)
    hl = entries["HYPERLIQUID"]
    assert admission.release is x.kw["release"]
    assert hl["parameters"]["perp_policy"]["taker_bps"] == "10"
    assert hl["parameters"]["perp_policy"]["slippage_bps"] == "5"
    assert (hl["parameters"]["perp_policy"]["fee_schedule_id"]
            == x.kw["hl_cost_amendment"])
    assert (hl["native_enrollment"]["policy_digest"]
            == target.digest(hl["parameters"]["perp_policy"]))
    assert (hl["native_enrollment"]["inception_digest"]
            == target.digest(hl["parameters"]))
    assert (hl["report_scope"]["policy_digest"]
            == target.digest(hl["parameters"]))
    assert hl["parameters"]["release"] == RELEASE
    assert (hl["parameters"]["opened_at"] == x.kw["clock"]())
    assert (x.draft["accounts"]["HYPERLIQUID"][
        "unaccepted_historical_parameters"] == review.historical)
    assert entries["QUALITY_DIPS"]["parameters"]["fees_bps"] == "2"
    assert entries["QUALITY_DIPS"]["parameters"]["opening_cash"] == "1000"
    assert len(hl["native_enrollment"]["writers"]) == 7


@pytest.mark.parametrize("damage", [
    "missing_cost_amendment", "wrong_cost_amendment",
    "unapproved_historical_digest", "wrong_amended_digest",
    "mutated_draft_costs", "wrong_account_operator",
])
def test_original_stage_c_conservative_fee_amendment_must_be_exactly_reviewed(
        monkeypatch, damage):
    from copy import deepcopy
    from scripts.observation_runtime import (
        personal_current_selected_dual_account_draft as draft,
    )
    review = conservative_stage_c_review(monkeypatch)
    x = review.x
    if damage == "missing_cost_amendment":
        x.kw.pop("hl_cost_amendment")
    elif damage == "wrong_cost_amendment":
        x.kw["hl_cost_amendment"] = "FAKE_NO_WALLET_FEE"
    elif damage == "unapproved_historical_digest":
        x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = (
            target.digest({k: v for k, v in review.historical.items()
                           if k != "opened_at"}))
    elif damage == "wrong_amended_digest":
        x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = "f" * 64
    elif damage == "mutated_draft_costs":
        def foreign_original():
            source = deepcopy(x.draft)
            source["accounts"]["HYPERLIQUID"][
                "unaccepted_historical_parameters"
                ]["perp_policy"]["taker_bps"] = "2"
            return source
        monkeypatch.setattr(draft, "inspect", foreign_original)
    else:
        x.kw["operator_acceptance_ids"]["HYPERLIQUID"] = "UNACCEPTED"
    with pytest.raises(ValueError):
        target.prepare_original_fresh_two_account_inceptions(**x.kw)


def test_stage_c_uses_real_original_bound_drafts_and_actual_original_job(
        monkeypatch):
    x=original_fresh_stage_c_model(monkeypatch)
    before=x.draft["accounts"]["QUALITY_DIPS"]["unaccepted_historical_parameters"]
    old_stamp=before["opened_at"]
    accounts,admission=target.prepare_original_fresh_two_account_inceptions(**x.kw)
    assert set(accounts)==set(LANES)
    assert admission.release is x.kw["release"]
    assert x.draft["accounts"]["QUALITY_DIPS"]["unaccepted_historical_parameters"]["opened_at"]==old_stamp
    for lane in LANES:
        e=accounts[lane]
        assert e["lane"]==lane
        assert e["parameters"]["opened_at"]==x.kw["clock"]()
        assert e["native_enrollment"]["inception_digest"]==target.digest(e["parameters"])
        assert e["report_scope"]["policy_digest"]==target.digest(e["parameters"])
        assert e["native_enrollment"]["acceptance_id"]==x.kw["operator_acceptance_ids"][lane]
        assert set(e["native_enrollment"]["writers"])==(
            {"decision","source","projection","report","coordination"}
            if lane=="QUALITY_DIPS"
            else {"decision","source","projection","report","coordination","funding","mark"})
        assert all(row["pid"]==432 for row in e["native_enrollment"]["writers"].values())
        assert e["parameters"]["opening_cash"]=="1000"
        assert e["native_enrollment"]["release_digest"]==RELEASE


@pytest.mark.parametrize("fault",[
    "no_operator_ids","duplicate_ids","unaccepted_ids",
    "unreviewed_fee_digest","wrong_release","foreign_original",
    "nonempty_financial_roots","already_promoted_draft","missing_second_lane",
    "expired_new_stamp","unexpected_wrong_lane","wrong_native_id",
])
def test_stage_c_never_promotes_unaccepted_historic_draft_without_exact_scope(
        monkeypatch,fault):
    x=original_fresh_stage_c_model(monkeypatch)
    kw=x.kw
    if fault=="no_operator_ids":kw["operator_acceptance_ids"]={}
    elif fault=="duplicate_ids":kw["operator_acceptance_ids"]["HYPERLIQUID"]=kw["operator_acceptance_ids"]["QUALITY_DIPS"]
    elif fault=="unaccepted_ids":kw["operator_acceptance_ids"]["QUALITY_DIPS"]="UNACCEPTED_DRAFT"
    elif fault=="unreviewed_fee_digest":kw["approved_unstamped_manifest_digests"]["QUALITY_DIPS"]="f"*64
    elif fault=="wrong_release":kw["release"].artifact_digest="f"*64
    elif fault=="foreign_original":kw["self_job"]=object()
    elif fault=="nonempty_financial_roots":
        from scripts.observation_runtime import personal_existing_native_resource_evidence as native
        def bad_roots():
            value=__import__("copy").deepcopy(x.roots)
            value["all_twelve_distinct_and_empty"]=False
            return value
        monkeypatch.setattr(native,"inspect_two_lane_native_roots",bad_roots)
    elif fault=="already_promoted_draft":
        from scripts.observation_runtime import personal_current_selected_dual_account_draft as draft
        def bad_draft():
            value=__import__("copy").deepcopy(x.draft)
            value["accounts"]["QUALITY_DIPS"]["operational_market_rights_unaccepted"]=False
            return value
        monkeypatch.setattr(draft,"inspect",bad_draft)
    elif fault=="missing_second_lane":
        from scripts.observation_runtime import personal_current_selected_dual_account_draft as draft
        def incomplete():
            value=__import__("copy").deepcopy(x.draft)
            value["accounts"].pop("HYPERLIQUID")
            return value
        monkeypatch.setattr(draft,"inspect",incomplete)
    elif fault=="expired_new_stamp":
        class Expiring(type(kw["clock"])):
            def __call__(self):
                self.stamp+=3
                return self.stamp
        kw["clock"]=Expiring()
    elif fault=="unexpected_wrong_lane":
        from scripts.observation_runtime import personal_paper_inception as inception
        monkeypatch.setattr(inception,"validate_personal_inception",
            lambda e:("HYPERLIQUID" if e["lane"]=="QUALITY_DIPS" else e["lane"],
                     e["native_enrollment"],e["parameters"]))
    elif fault=="wrong_native_id":
        from scripts.observation_runtime import personal_current_selected_dual_account_draft as draft
        def wrong_root():
            value=__import__("copy").deepcopy(x.draft)
            value["accounts"]["QUALITY_DIPS"]["unaccepted_historical_enrollment"]["resources"]["report"]["native_id"]=[999,999,999]
            return value
        monkeypatch.setattr(draft,"inspect",wrong_root)
    with pytest.raises((ValueError,AssertionError,TypeError)):
        target.prepare_original_fresh_two_account_inceptions(**kw)


def _g_h_original_source_ports_fixture(monkeypatch):
    """Synthetic G->H composition only; original financial roots untouched."""
    x = configured(monkeypatch)
    activate_to_two_accounts(x)
    stub_original_data_operator_record(monkeypatch, x)
    original = x.obj.publish_postinception_data_activation_once(**postinit(x))
    assert original["status"] == "NATIVE_VERIFIED"

    from app.services import personal_paper_runtime
    from scripts.observation_runtime import personal_local_authority
    created = []
    record_actions = [["READ_ONLY", "CONNECT_APPROVED_DATA"]]
    failed_lane = [None]
    monkeypatch.setattr(personal_paper_runtime, "validate_policy",
                        lambda policy: policy)

    class OriginalDataOperator:
        def __init__(self, **kw):
            self.reader = kw["reader"]
            self.enrollment = kw["enrollment"]
            self.clock = kw["clock"]
            self.revoked = False
            self.lane = self.enrollment["lane"]
            assert kw["policy"] == {"synthetic": "G_POSTINCEPTION_DATA_ONLY"}
            assert type(self.reader) is x.Reader
            assert self.reader.root == postinit(x)["root"]
            assert self.reader.native_root == [1, 2, 3]
            assert self.reader.binding == {
                "id": [1, 2, 3], "sha256": "b" * 64,
            }
            assert self.clock is x.clock
            assert kw["runtime_id"] == "EXACT_LOCAL_PROCESS"
            assert kw["clock_profile"] == target.CLOCK_PROFILE
            assert kw["accounts"] == x.obj._digest
            if self.lane == "HYPERLIQUID":
                assert kw["postinception_owner"] is x.owner
                assert kw["qd_enrollment"] == x.enrollments["QUALITY_DIPS"]
            else:
                assert "postinception_owner" not in kw
                assert "qd_enrollment" not in kw
            if failed_lane[0] == self.lane:
                raise ValueError("SYNTHETIC_OPERATOR_G_BIND_FAILURE")
            created.append(self)

        def activation(self, action):
            assert action == "CONNECT_APPROVED_DATA"
            return {
                "actions": list(record_actions[0]), "origin": "LOCAL_OPERATOR",
                "release_digest": RELEASE, "accounts": x.obj._digest,
            }

        def revoke(self):
            self.revoked = True

    monkeypatch.setattr(personal_local_authority,
                        "NativePersonalOperatorAuthority", OriginalDataOperator)
    return SimpleNamespace(**locals())


def test_original_g_h_binds_both_data_operators_from_one_actual_native_g_ack(
        monkeypatch):
    s = _g_h_original_source_ports_fixture(monkeypatch)
    result = s.x.obj.bind_verified_postinception_data_operators_once(
        personal_policy={"synthetic": "G_POSTINCEPTION_DATA_ONLY"},
    )
    assert result["schema"] == (
        "ATLAS_PERSONAL_G_H_ORIGINAL_SOURCE_OPERATOR_PORTS_V1")
    assert result["source_provider_rights_accepted"] is False
    assert result["financial_paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert set(result["operators"]) == set(LANES)
    assert result["operators"]["QUALITY_DIPS"].reader is result["reader"]
    assert result["operators"]["HYPERLIQUID"].reader is result["reader"]
    assert [o.lane for o in s.created] == list(LANES)
    assert s.x.obj.phase == "POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED"
    assert s.x.events.count("accounts_publish") == 1
    assert s.x.events.count("activation_publish") == 2
    with pytest.raises(ValueError, match="ALREADY_BOUND"):
        s.x.obj.bind_verified_postinception_data_operators_once(
            personal_policy={"synthetic": "G_POSTINCEPTION_DATA_ONLY"},
        )
    for operator in result["operators"].values():
        operator.revoke()


@pytest.mark.parametrize("fault", [
    "postinit_native_root_tampered", "postinit_binding_missing",
    "operator_hl_refused", "operator_scope_auto_paper",
    "lost_native_job", "reentered_preinception",
])
def test_original_g_h_refuses_before_fake_financial_permission_or_replay(
        monkeypatch, fault):
    s = _g_h_original_source_ports_fixture(monkeypatch)
    x = s.x
    if fault == "postinit_native_root_tampered":
        x.obj._post_data_result["native_root"] = [-1, 2, 3]
    elif fault == "postinit_binding_missing":
        x.obj._post_data_result["binding"] = None
    elif fault == "operator_hl_refused":
        s.failed_lane[0] = "HYPERLIQUID"
    elif fault == "operator_scope_auto_paper":
        s.record_actions[0] = ["READ_ONLY", "AUTO_PAPER"]
    elif fault == "lost_native_job":
        x.owner.alive = False
    else:
        x.owner._phase = "PREINCEPTION"
    with pytest.raises((ValueError,AssertionError)):
        x.obj.bind_verified_postinception_data_operators_once(
            personal_policy={"synthetic": "G_POSTINCEPTION_DATA_ONLY"},
        )
    assert x.events.count("accounts_publish") == 1
    assert x.events.count("activation_publish") == 2
    assert not any(not o.revoked for o in s.created)
    assert x.obj.phase == "POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED"



def _pending_hl_source_review_fixture(monkeypatch):
    """Exact three original pending R25 terms in a disposable stage-C cohort."""
    from copy import deepcopy
    from app.services.hyperliquid_forward_flat_paper_policy import (
        derive_reviewable_conservative_hl_manifest,
    )
    review = conservative_stage_c_review(monkeypatch)
    x = review.x
    pending = {
        "market_source": "PENDING_E1_VERIFIED_BOOK_SOURCE",
        "instrument_cut": "PENDING_E1_VERIFIED_INSTRUMENT_CUT",
        "funding_source": "PENDING_E1_VERIFIED_FUNDING_SOURCE",
    }
    original = deepcopy(review.historical)
    original["perp_policy"].update(pending)
    x.draft["accounts"]["HYPERLIQUID"][
        "unaccepted_historical_parameters"] = deepcopy(original)
    x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = target.digest(
        {k: v for k, v in derive_reviewable_conservative_hl_manifest(
            original).items() if k != "opened_at"})
    return SimpleNamespace(
        review=review, x=x, original=original, pending=pending,
    )


def test_original_stage_c_refuses_permanent_pending_source_ids_until_review(
        monkeypatch):
    x = _pending_hl_source_review_fixture(monkeypatch)
    with pytest.raises(
        ValueError, match="HL_PENDING_SOURCE_IDS_MUST_BE_REVIEWED",
    ):
        target.prepare_original_fresh_two_account_inceptions(**x.x.kw)
    assert (x.x.draft["accounts"]["HYPERLIQUID"]
            ["unaccepted_historical_parameters"] == x.original)
    assert x.x.roots["all_twelve_distinct_and_empty"] is True


def test_original_stage_c_accepted_source_namespace_is_not_source_authority(
        monkeypatch):
    from copy import deepcopy
    from app.services.hyperliquid_forward_flat_paper_policy import (
        derive_reviewable_conservative_hl_manifest,
    )
    x = _pending_hl_source_review_fixture(monkeypatch)
    assert x.x.kw["operator_acceptance_ids"]["HYPERLIQUID"].startswith(
        "OPERATOR_REVIEWED_"
    )
    proposed = deepcopy(target.HL_ORIGINAL_PUBLIC_SOURCE_REVIEW)
    x.x.kw["hl_source_identifiers"] = proposed
    manifest = derive_reviewable_conservative_hl_manifest(x.original)
    for key in ("market_source", "instrument_cut", "funding_source"):
        manifest["perp_policy"][key] = proposed[key]
    x.x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = target.digest(
        {k: v for k, v in manifest.items() if k != "opened_at"})
    entries, admission = target.prepare_original_fresh_two_account_inceptions(
        **x.x.kw)
    assert admission.release is x.x.kw["release"]
    hl = entries["HYPERLIQUID"]
    assert hl["parameters"]["perp_policy"] == manifest["perp_policy"]
    assert all(
        not hl["parameters"]["perp_policy"][key].startswith("PENDING_")
        for key in ("market_source", "instrument_cut", "funding_source")
    )
    assert hl["native_enrollment"]["policy_digest"] == target.digest(
        hl["parameters"]["perp_policy"])
    assert hl["native_enrollment"]["inception_digest"] == target.digest(
        hl["parameters"])
    assert hl["parameters"]["opening_cash"] == "1000"
    assert hl["parameters"]["currency"] == "USDC"
    assert entries["QUALITY_DIPS"]["parameters"]["opening_cash"] == "1000"
    assert x.x.draft["accounts"]["HYPERLIQUID"][
        "unaccepted_historical_parameters"] == x.original
    # No source-authority, provider-connection, writer, account or PAPER
    # side effect exists in this original stage-C in-memory review.
    assert x.x.roots["all_twelve_distinct_and_empty"] is True


@pytest.mark.parametrize("damage", [
    "alternate_provider", "invented_market", "missing_source",
    "wrong_schema", "unreviewed_hl_digest", "changed_terms_after_review",
])
def test_original_stage_c_source_identity_binding_refuses_without_exact_review(
        monkeypatch, damage):
    from copy import deepcopy
    from app.services.hyperliquid_forward_flat_paper_policy import (
        derive_reviewable_conservative_hl_manifest,
    )
    x = _pending_hl_source_review_fixture(monkeypatch)
    source = deepcopy(target.HL_ORIGINAL_PUBLIC_SOURCE_REVIEW)
    proposed = derive_reviewable_conservative_hl_manifest(x.original)
    for key in ("market_source", "instrument_cut", "funding_source"):
        proposed["perp_policy"][key] = source[key]
    x.x.kw["hl_source_identifiers"] = source
    x.x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = target.digest(
        {k: v for k, v in proposed.items() if k != "opened_at"})
    if damage == "alternate_provider":
        source["provider_url"] = "https://localhost.invalid/info"
    elif damage == "invented_market":
        source["market_source"] = "FAKE_PROVIDER_PUBLIC_BOOK"
    elif damage == "missing_source":
        source.pop("funding_source")
    elif damage == "wrong_schema":
        source["schema"] = "PROVIDER_RIGHTS_ALREADY_ACCEPTED"
    elif damage == "unreviewed_hl_digest":
        x.x.kw["approved_unstamped_manifest_digests"]["HYPERLIQUID"] = "f" * 64
    else:
        x.x.draft["accounts"]["HYPERLIQUID"][
            "unaccepted_historical_parameters"]["perp_policy"][
                "max_notional"] = "300"
    with pytest.raises(ValueError):
        target.prepare_original_fresh_two_account_inceptions(**x.x.kw)
    assert x.x.roots["all_twelve_distinct_and_empty"] is True


@pytest.mark.parametrize("damage", ["none","forged_epoch","foreign_path","fake_scope"])
def test_c_d_successor_scope_routes_only_distinct_new_epoch_without_reusing_original(
        monkeypatch, damage):
    """Synthetic future selected issuer: old hardwired roots are never replaced."""
    from pathlib import Path
    from scripts.observation_runtime import personal_successor_native_root_scope
    x=configured_native_c_d(monkeypatch)
    x.kwargs["release"].root=Path("D:/AtlasRuntime/releases")/(RELEASE[:40])
    plan={"successor_release":RELEASE[:40],"lanes":{}}
    roles=("source","projection","report","control","coordination","custody")
    for lane in LANES:
        epoch="new-"+lane.lower()+"-selected"
        roots={}
        for role in roles:
            roots[role]=r"D:\AtlasPaper\REVIEWED_SUCCESSOR_ONLY"+"\\"+lane+"\\"+role
        plan["lanes"][lane]={"epoch":epoch,"roots":roots}
        e=x.candidates[lane]["native_enrollment"]
        e["epoch"]=epoch
        e["resources"]={
            role:{"path":path,"native_id":[j+1,7,9]}
            for j,(role,path) in enumerate(roots.items())
        }
    class RootScope:
        def __init__(self):
            self.plan=plan
        def exact_selected_release_bound(self,source,digest_value):
            if source!=RELEASE[:40] or digest_value!=RELEASE:
                raise ValueError('TEST_RELEASE_OR_DIGEST_CHANGED')
            return True
    monkeypatch.setattr(personal_successor_native_root_scope,
                        "NativeSelectedSuccessorEpochRoots",RootScope)
    scoped=RootScope()
    if damage=="fake_scope":
        scoped=object()
    elif damage=="forged_epoch":
        x.candidates["QUALITY_DIPS"]["native_enrollment"]["epoch"]="old-original-epoch"
    elif damage=="foreign_path":
        x.candidates["HYPERLIQUID"]["native_enrollment"]["resources"]["source"]["path"]=(
            r"D:\AtlasPaper\QualityDips\OLD_R26_ORIGINAL")
    x.kwargs["successor_root_scope"]=scoped
    if damage=="none":
        pair,images=target.bind_original_native_two_account_commissioner(**x.kwargs)
        assert pair.phase=="PREINCEPTION_READY"
        assert len(images)==2
        for item in images.values():
            item.close()
    else:
        with pytest.raises((ValueError,AttributeError)):
            target.bind_original_native_two_account_commissioner(**x.kwargs)
        assert x.created==[]


def test_successor_c_d_dispatch_uses_new_epoch_candidates_and_bind_scope(monkeypatch):
    """Composition of future scope; no real native roots/accounts in this test."""
    from scripts.observation_runtime import personal_successor_stage_c_candidates as fresh
    sentinel=object()
    checked=[]
    originals={
        "self_job":object(),"release":object(),"clock":object(),
        "runtime_id":"TEST_SELECTED_SUCCESSOR",
        "personal_policy":{"simulation_only":True},
        "operator_acceptance_ids":{"QUALITY_DIPS":"R27_REVIEWED_QD",
                                   "HYPERLIQUID":"R27_REVIEWED_HL"},
        "approved_unstamped_manifest_digests":{"QUALITY_DIPS":"a"*64,
                                               "HYPERLIQUID":"b"*64},
        "successor_root_scope":sentinel,
        "reviewed_successor_terms":{"new_epoch":True},
    }
    def fresh_stage(**kw):
        checked.append("fresh_scope")
        assert kw["successor_root_scope"] is sentinel
        assert kw["reviewed_successor_terms"]==originals["reviewed_successor_terms"]
        return {"QUALITY_DIPS":"NEW_QD","HYPERLIQUID":"NEW_HL"},"NEW_ADMISSION"
    def bind_stage(**kw):
        checked.append("native_bound")
        assert kw["successor_root_scope"] is sentinel
        assert kw["admission"]=="NEW_ADMISSION"
        assert kw["inceptions"]=={"QUALITY_DIPS":"NEW_QD","HYPERLIQUID":"NEW_HL"}
        return "NEW_COMMISSIONER","NO_FINANCIAL_IMAGE_WRITES"
    monkeypatch.setattr(fresh,"prepare_fresh_successor_account_candidates",fresh_stage)
    monkeypatch.setattr(target,"bind_original_native_two_account_commissioner",bind_stage)
    result=target.prepare_and_bind_reviewed_original_native_accounts(**originals)
    assert result==("NEW_COMMISSIONER","NO_FINANCIAL_IMAGE_WRITES")
    assert checked==["fresh_scope","native_bound"]


@pytest.mark.parametrize("change",[
    "terms_without_native_scope","old_hl_fee_amendment","old_hl_sources",
    "missing_new_review",
])
def test_successor_stage_c_cannot_bypass_original_vs_new_epoch_discriminator(
        monkeypatch,change):
    inputs={
        "self_job":object(),"release":object(),"clock":object(),
        "runtime_id":"NEW",
        "personal_policy":{"simulation_only":True},
        "operator_acceptance_ids":{"QUALITY_DIPS":"a","HYPERLIQUID":"b"},
        "approved_unstamped_manifest_digests":{"QUALITY_DIPS":"a"*64,
                                               "HYPERLIQUID":"b"*64},
        "successor_root_scope":object(),
        "reviewed_successor_terms":{},
    }
    if change=="terms_without_native_scope":inputs["successor_root_scope"]=None
    elif change=="old_hl_fee_amendment":inputs["hl_cost_amendment"]="SYNTHETIC_ORIGINAL_AMENDMENT"
    elif change=="old_hl_sources":inputs["hl_source_identifiers"]={}
    elif change=="missing_new_review":inputs["reviewed_successor_terms"]=None
    with pytest.raises(ValueError,match="PERSONAL_C_D_SUCCESSOR"):
        target.prepare_and_bind_reviewed_original_native_accounts(**inputs)
