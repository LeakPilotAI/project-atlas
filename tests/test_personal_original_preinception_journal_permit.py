"""Original preactivation coordination journals: strict local-authority scope.

All successful accounts are synthetic in-memory stubs. Actual production
classes are never monkeypatched outside pytest. No original Windows file is
opened or published by this suite.
"""
from __future__ import annotations

from hashlib import sha256

import pytest

from scripts.observation_runtime import (
    personal_original_preinception_journal_permit as target,
)

T = 1794488500
RELEASE = "a" * 64


def system(monkeypatch):
    state = {"QUALITY_DIPS": False, "HYPERLIQUID": False}
    written = []
    stopped = []

    def parameters(lane):
        return {"release": RELEASE, "lane": lane,
                "opened_at": T-1, "opening_cash": "1000",
                "currency": "USD" if lane == "QUALITY_DIPS" else "USDC"}

    class Job:
        _phase = "PREINCEPTION"
        release_digest = RELEASE
        _native_binding = ("original-native-12-binding",)

        def __init__(self):
            self._original_qd = native("QUALITY_DIPS")
            self._original_perp = native("HYPERLIQUID")

        def verify_still_running(self):
            return True

        def _verify_original_job(self):
            return True

        def observe_preinception_coordination(self, *, qd_ledger, hl_ledger):
            assert state["QUALITY_DIPS"] and state["HYPERLIQUID"]
            self._phase = "PREINCEPTION_COORDINATION_READY"
            return {
                "initial_native_coordination_journals_verified": 2,
                "paper_start_authorized": False,
            }

    class Clock:
        def __call__(self):
            return T
        def require_operational(self, runtime_id):
            assert runtime_id == "EXACT_ORIGINAL_PROCESS"

    class Images:
        def __init__(self, lane, enrollment):
            self.root_id = [1, 2, 3] if lane == "QUALITY_DIPS" else [4, 5, 6]
            self.enrollment = target.digest(enrollment)
            self.lane = lane
            self.value = None

        def initialize(self, image, *, authorization):
            req = {
                "schema": "PERSONAL_COORDINATION_INSTALL_V1",
                "root": self.root_id,
                "enrollment": self.enrollment,
                "image_digest": sha256(image).hexdigest(),
            }
            with authorization.lease(req) as lease:
                assert lease.check(req)
                assert not state[self.lane]
                state[self.lane] = True
                self.value = image
                written.append(self.lane)
                if self.lane == "HYPERLIQUID" and stopped:
                    raise OSError("TEST_PARTIAL_SECOND_IMAGE")
                assert lease.check(req)

        def _load(self):
            return self.value, {"revision": 1}

    class Ledger:
        @staticmethod
        def initial_image(manifest):
            return ("INITIAL_NATIVE_IMAGE:"+manifest["lane"]).encode()

        def __init__(self, lane, enrollment):
            self.manifest = parameters(lane)
            self.images = Images(lane, enrollment)

    def native(lane):
        return {
            "epoch": lane + "_TEST",
            "inception_digest": target.digest(parameters(lane)),
            "resources": {
                "coordination": {"native_id": (
                    [1, 2, 3] if lane == "QUALITY_DIPS" else [4, 5, 6]
                )}
            },
        }

    def native_roots():
        entries = {}
        for lane in target.LANES:
            entries[lane] = {
                "epoch": lane + "_TEST",
                "roots": {
                    role: {"existing_empty_namespace_verified": (
                        role != "coordination" or not state[lane])}
                    for role in (
                        "source", "projection", "report",
                        "control", "coordination", "custody")
                },
            }
        count = 12-sum(state.values())
        return {
            "native_root_total": 12,
            "native_root_ids_verified": 12,
            "existing_empty_root_namespaces": count,
            "all_twelve_distinct_and_empty": count == 12,
            "lanes": entries,
        }

    def validate_roots(*args):
        evidence = args[2]
        original_binding = args[3]
        assert original_binding == Job._native_binding
        assert evidence["native_root_total"] == 12
        assert evidence["native_root_ids_verified"] == 12
        return Job._native_binding

    monkeypatch.setattr(target, "RetainedSelectedNativeOwnerPreflight", Job)
    monkeypatch.setattr(target, "NativeVersionSafePaperOperatorClock", Clock)
    monkeypatch.setattr(target, "PersonalNativeCoordination", Ledger)
    monkeypatch.setattr(target, "NativePersonalCoordinationImages", Images)
    monkeypatch.setattr(target, "inspect_two_lane_native_roots", native_roots)
    monkeypatch.setattr(
        target, "require_exact_r15_populated_root_identities",
        validate_roots,
    )
    monkeypatch.setattr(target, "current_sid", lambda: "S-1-5-21-SIMULATED")
    monkeypatch.setattr(
        target, "require_version_safe_release_digest",
        lambda *, clock, runtime_id, release_digest:
        type(clock) is Clock and runtime_id == "EXACT_ORIGINAL_PROCESS"
        and release_digest == RELEASE,
    )
    job = Job()
    ledgers = {
        lane: Ledger(lane, job._original_qd if lane == target.LANES[0]
                     else job._original_perp)
        for lane in target.LANES
    }
    approval = {
        "schema": target.SCHEMA,
        "action": target.ACTION,
        "operator_sid": "S-1-5-21-SIMULATED",
        "release_digest": RELEASE,
        "account_digests": {
            "QUALITY_DIPS": target.digest(job._original_qd),
            "HYPERLIQUID": target.digest(job._original_perp),
        },
        "image_sha256": {
            lane: sha256(("INITIAL_NATIVE_IMAGE:"+lane).encode()).hexdigest()
            for lane in target.LANES
        },
        "issued_at": T-1, "expires_at": T+90,
    }
    args = {
        "job": job, "clock": Clock(),
        "runtime_id": "EXACT_ORIGINAL_PROCESS",
        "ledgers": ledgers, "operator_scope": approval,
    }
    return args, state, written, stopped


def test_two_journals_acknowledged_not_trading_or_account_inception(monkeypatch):
    args, state, written, _ = system(monkeypatch)
    permit = target.NativeOriginalTwoJournalPreinceptionPermit(**args)
    result = permit.publish_both_original_journals_once()
    assert written == list(target.LANES)
    assert all(state.values())
    assert args["job"]._phase == "PREINCEPTION_COORDINATION_READY"
    assert result["native_initial_journal_count"] == 2
    assert result["native_account_inceptions_published"] == 0
    assert result["financial_writer_lease_issued"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    with pytest.raises(ValueError, match="REPLAY"):
        permit.publish_both_original_journals_once()


@pytest.mark.parametrize("tamper", [
    "job_missing", "clock_missing", "wrong_phase", "writer_release",
    "clock_runtime", "missing_lane", "missing_scope", "wrong_scope_schema",
    "different_action", "wrong_sid", "wrong_release",
    "changed_account_binding", "changed_image_binding",
    "expired", "future_issue", "overlong_scope", "noninteger_scope",
    "already_first_image", "wrong_ledger_manifest", "wrong_root",
    "foreign_enrollment_digest", "stale_manifest", "future_manifest",
    "bad_opening_cash",
])
def test_absent_original_journal_preconditions_never_write(monkeypatch, tamper):
    args, state, written, _ = system(monkeypatch)
    if tamper == "job_missing":
        args["job"] = object()
    elif tamper == "clock_missing":
        args["clock"] = object()
    elif tamper == "wrong_phase":
        args["job"]._phase = "PREINCEPTION_COORDINATION_READY"
    elif tamper == "writer_release":
        args["job"].release_digest = "f"*64
    elif tamper == "clock_runtime":
        args["runtime_id"] = "FOREIGN_PROCESS"
    elif tamper == "missing_lane":
        args["ledgers"].pop("HYPERLIQUID")
    elif tamper == "missing_scope":
        args["operator_scope"] = None
    elif tamper == "wrong_scope_schema":
        args["operator_scope"]["schema"] = "OTHER"
    elif tamper == "different_action":
        args["operator_scope"]["action"] = "AUTO_PAPER"
    elif tamper == "wrong_sid":
        args["operator_scope"]["operator_sid"] = "FOREIGN"
    elif tamper == "wrong_release":
        args["operator_scope"]["release_digest"] = "f"*64
    elif tamper == "changed_account_binding":
        args["operator_scope"]["account_digests"]["QUALITY_DIPS"] = "f"*64
    elif tamper == "changed_image_binding":
        args["operator_scope"]["image_sha256"]["QUALITY_DIPS"] = "f"*64
    elif tamper == "expired":
        args["operator_scope"]["expires_at"] = T
    elif tamper == "future_issue":
        args["operator_scope"]["issued_at"] = T+1
    elif tamper == "overlong_scope":
        args["operator_scope"]["expires_at"] = T+1000
    elif tamper == "noninteger_scope":
        args["operator_scope"]["issued_at"] = str(T)
    elif tamper == "already_first_image":
        state["QUALITY_DIPS"] = True
    elif tamper == "wrong_ledger_manifest":
        args["ledgers"]["QUALITY_DIPS"].manifest["release"] = "f"*64
    elif tamper == "wrong_root":
        args["ledgers"]["QUALITY_DIPS"].images.root_id = [99, 88, 77]
    elif tamper == "foreign_enrollment_digest":
        args["ledgers"]["HYPERLIQUID"].images.enrollment = "f"*64
    elif tamper == "stale_manifest":
        args["ledgers"]["QUALITY_DIPS"].manifest["opened_at"] = T-90
    elif tamper == "future_manifest":
        args["ledgers"]["QUALITY_DIPS"].manifest["opened_at"] = T+5
    elif tamper == "bad_opening_cash":
        args["ledgers"]["QUALITY_DIPS"].manifest["opening_cash"] = "10000"
    with pytest.raises((ValueError, KeyError, TypeError)):
        target.NativeOriginalTwoJournalPreinceptionPermit(**args)
    assert written == []


def test_partial_second_write_is_terminal_and_cannot_retry(monkeypatch):
    args, state, written, stopped = system(monkeypatch)
    stopped.append(True)
    permit = target.NativeOriginalTwoJournalPreinceptionPermit(**args)
    with pytest.raises(OSError, match="PARTIAL_SECOND"):
        permit.publish_both_original_journals_once()
    assert written == ["QUALITY_DIPS", "HYPERLIQUID"]
    assert all(state.values())
    assert args["job"]._phase == "PREINCEPTION_COORDINATION_PENDING"
    with pytest.raises(ValueError, match="REPLAY"):
        permit.publish_both_original_journals_once()


def test_explicit_context_refuses_out_of_order_namespace_request(monkeypatch):
    args, state, written, _ = system(monkeypatch)
    permit = target.NativeOriginalTwoJournalPreinceptionPermit(**args)
    hl = args["ledgers"]["HYPERLIQUID"]
    req = {
        "schema": "PERSONAL_COORDINATION_INSTALL_V1",
        "root": hl.images.root_id,
        "enrollment": hl.images.enrollment,
        "image_digest": sha256(permit.expected_images["HYPERLIQUID"]).hexdigest(),
    }
    with pytest.raises(ValueError, match="EXACT_ORIGINAL_JOURNAL_REQUEST"), permit.lease(req):
        pass
    assert written == []
    assert not any(state.values())


def test_genuine_factory_refuses_any_synthetic_or_missing_native_port():
    # No fixture patches. A source-only synthetic operator cannot open
    # original Windows filesystem via this class.
    with pytest.raises(ValueError, match="EXACT_NATIVE_JOB_CLOCK_SCOPE"):
        target.NativeOriginalTwoJournalPreinceptionPermit(
            job=None, clock=None, runtime_id="NA", ledgers={}, operator_scope={})


@pytest.mark.skipif(__import__("sys").platform != "win32",
                    reason="actual disposable Windows-native journal verification")
def test_genuine_windows_native_two_coordination_image_roundtrip_disposable_only(
        monkeypatch):
    """Real two native immutable images + genuine owner ACK; fake operator only.

    Exact-original account roots are never opened for writing. Native issuer
    and original Windows Job are deliberately replaced IN TEST ONLY.
    """
    import os
    import tempfile
    import time
    from copy import deepcopy
    from pathlib import Path

    from app.services.personal_native_coordination import PersonalNativeCoordination

    from scripts.observation_runtime.personal_coordination_store import (
        NativePersonalCoordinationImages,
    )
    from scripts.observation_runtime.personal_current_selected_dual_account_draft import (
        inspect as original_draft,
    )
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        ROLES,
        inspect_two_lane_native_roots,
    )
    from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
        RetainedSelectedNativeOwnerPreflight,
    )
    from scripts.observation_runtime.personal_paper_inception import native_primitives
    from scripts.observation_runtime.personal_r15_owned_job_activation import (
        require_exact_r15_preinception_roots,
    )
    from scripts.volume_inspector.windows_output import current_sid

    native_before = inspect_two_lane_native_roots()
    if native_before["all_twelve_distinct_and_empty"] is not True:
        # This optional disposable-native fixture requires the ORIGINAL
        # pre-journal state. Never alter or reset real immutable journals just
        # to recreate an empty-root test condition after commissioning.
        pytest.skip("original native journals already exist; preinception-only fixture")
    original = original_draft()
    assert original["native_account_inceptions_published"] == 0
    selected = original["selected_artifact_digest"]
    diag = Path(__file__).resolve().parents[1] / "logs" / "diagnostics"
    assert diag.is_dir() and not diag.is_symlink() and not diag.is_junction()
    images = {}
    with tempfile.TemporaryDirectory(prefix="aj-", dir=diag) as temp:
        tempdir = Path(temp).resolve(strict=True)
        native = native_primitives()
        rows, locations = {}, {}
        for lane in target.LANES:
            source = original["accounts"][lane]
            manifest = deepcopy(source["unaccepted_historical_parameters"])
            enrollment = deepcopy(source["unaccepted_historical_enrollment"])
            base = tempdir / lane.lower() / enrollment["epoch"]
            base.mkdir(parents=True)
            locations[lane] = base
            for role in ROLES:
                path = base / role
                with native.w.WindowsOutput.create_root(str(path)) as out:
                    assert not os.listdir(out.root)
                    enrollment["resources"][role].update(
                        path=str(path),
                        native_id=native.native.file_identity(out.root_handle),
                    )
            rows[lane] = (manifest, enrollment)

        def disposable_roots():
            return inspect_two_lane_native_roots(
                qd_base=locations["QUALITY_DIPS"],
                qd_custody=locations["QUALITY_DIPS"] / "custody",
                hl_base=locations["HYPERLIQUID"],
                hl_custody=locations["HYPERLIQUID"] / "custody",
            )

        original_roots = disposable_roots()
        assert original_roots["all_twelve_distinct_and_empty"] is True
        # Disposable-only fresh opening timestamps; do NOT transplant
        # historical R15/R17 stale time into a real once-only journal.
        fresh_stamp = int(time.time())
        for lane in target.LANES:
            manifest, enrollment = rows[lane]
            manifest["opened_at"] = fresh_stamp
            enrollment["inception_digest"] = target.digest(manifest)
        qd, perp = (rows[lane][1] for lane in target.LANES)
        owner = object.__new__(RetainedSelectedNativeOwnerPreflight)
        owner.release_digest = selected
        owner._original_qd, owner._original_perp = deepcopy(qd), deepcopy(perp)
        owner._qd, owner._perp = target.digest(qd), target.digest(perp)
        owner._native_binding = require_exact_r15_preinception_roots(
            qd, perp, original_roots)
        owner._roots = original_roots
        owner._phase = "PREINCEPTION"
        owner._initial_coordination = None
        owner._initial_cuts = None
        owner._initial_bootstraps = None
        monkeypatch.setattr(owner, "verify_still_running", lambda: True)
        monkeypatch.setattr(owner, "_verify_original_job", lambda: True)

        class TestOnlyClock:
            def __call__(self):
                return int(time.time())

            def require_operational(self, runtime_id):
                assert runtime_id == "DISPOSABLE_JOURNALS_ONLY"

        monkeypatch.setattr(target, "NativeVersionSafePaperOperatorClock",
                            TestOnlyClock)
        monkeypatch.setattr(
            target, "require_version_safe_release_digest",
            lambda *, clock, runtime_id, release_digest:
            type(clock) is TestOnlyClock
            and runtime_id == "DISPOSABLE_JOURNALS_ONLY"
            and release_digest == selected,
        )
        monkeypatch.setattr(target, "inspect_two_lane_native_roots",
                            disposable_roots)
        from scripts.observation_runtime import (
            personal_native_selected_owned_job_preflight as job_module,
        )
        monkeypatch.setattr(job_module, "inspect_two_lane_native_roots",
                            disposable_roots)
        ledgers = {}
        try:
            for lane in target.LANES:
                manifest, enrollment = rows[lane]
                root = enrollment["resources"]["coordination"]
                image = NativePersonalCoordinationImages(
                    root=root["path"], native_root=root["native_id"],
                    enrollment_digest=target.digest(enrollment))
                images[lane] = image
                ledgers[lane] = PersonalNativeCoordination(
                    manifest=manifest, images=image, path=root["path"])
            stamp = int(time.time())
            approval = {
                "schema": target.SCHEMA,
                "action": target.ACTION,
                "operator_sid": current_sid(),
                "release_digest": selected,
                "account_digests": {
                    lane: target.digest(rows[lane][1]) for lane in target.LANES
                },
                "image_sha256": {
                    lane: sha256(PersonalNativeCoordination.initial_image(
                        rows[lane][0])).hexdigest() for lane in target.LANES
                },
                "issued_at": stamp-1,
                "expires_at": stamp+90,
            }
            permit = target.NativeOriginalTwoJournalPreinceptionPermit(
                job=owner, clock=TestOnlyClock(),
                runtime_id="DISPOSABLE_JOURNALS_ONLY",
                ledgers=ledgers, operator_scope=approval)
            result = permit.publish_both_original_journals_once()
            assert result["native_initial_journal_count"] == 2
            assert owner._phase == "PREINCEPTION_COORDINATION_READY"
            assert disposable_roots()["existing_empty_root_namespaces"] == 10
            for lane in target.LANES:
                raw, pin = images[lane]._load()
                assert raw == PersonalNativeCoordination.initial_image(rows[lane][0])
                assert pin["revision"] == 1
                with ledgers[lane].connect(readonly=True) as db:
                    assert db.execute(
                        "SELECT COUNT(*) FROM personal_publications").fetchone()[0] == 0
            with pytest.raises(ValueError, match="REPLAY"):
                permit.publish_both_original_journals_once()
        finally:
            for image in images.values():
                image.close()
    assert inspect_two_lane_native_roots() == native_before
