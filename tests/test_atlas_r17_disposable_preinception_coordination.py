"""R17 two native coordination images -> preinception acceptance (disposable).

Both actual Windows coordination journals are first initialized under an
explicitly SYNTHETIC test authorization. The original twelve Atlas accounts
stay empty and untouched; no activation or financial writer is granted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalPublicationCustody
from test_atlas_r17_disposable_native_dual_inception import _disposable_inception

from scripts.observation_runtime.atlas_r16_two_account_financial_arithmetic import (
    POLICY_PATH,
    POLICY_SHA256,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_SOURCE,
)
from scripts.observation_runtime.atlas_r17_two_account_inception_handoff import (
    inspect as r17_handoff,
)
from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
    native_primitives,
)
from scripts.observation_runtime.personal_r15_owned_job_activation import (
    require_exact_r15_preinception_roots,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

SELECTED_IMAGE = Path("D:/AtlasRuntime/releases") / R17_SOURCE / "python/python.exe"


def only_initial_journal_publication(enrollment, manifest):
    output = enrollment["resources"]["coordination"]
    images = NativePersonalCoordinationImages(
        root=output["path"], native_root=output["native_id"],
        enrollment_digest=digest(enrollment))
    ledger = PersonalNativeCoordination(
        manifest=manifest, images=images, path=output["path"])
    @contextmanager
    def test_only_authorization(request):
        yield SimpleNamespace(check=lambda candidate: candidate == request)
    images.initialize(
        PersonalNativeCoordination.initial_image(manifest),
        authorization=SimpleNamespace(lease=test_only_authorization))
    return ledger


def publish_disposable_initial_account(inception, ledger, *, at):
    """Real native FS1/FS3 + real native SQLite, TEST-ONLY issuer/owner."""
    publication = PersonalPublicationCustody(ledger)

    @contextmanager
    def fake_issuer(scope, now):
        assert now == at
        yield SimpleNamespace(
            check=lambda candidate, stamp:
            candidate == scope and at <= stamp <= at + 30)

    @contextmanager
    def fake_owner(context, now):
        assert now == at
        yield SimpleNamespace(
            check=lambda candidate, stamp:
            candidate == context and at <= stamp <= at + 30)

    bootstrap = PersonalInceptionBootstrap(
        enrollment=inception, publication=publication,
        issuer=SimpleNamespace(lease=fake_issuer),
        clock=lambda: at, readback=NativePersonalInitialReadback())
    publisher = PersonalInceptionPublisher(
        bootstrap=bootstrap, custody=publication,
        ownership=SimpleNamespace(lease=fake_owner),
        observer=lambda: {"schema": "QD_OP_PROCESS_ID_V1", **observe_self()},
        files=NativePersonalInceptionFiles())
    result = publisher.publish()
    assert result["financial_startup_authorized"] is False
    assert bootstrap.verify_publication()["current"] == result["current"]
    with pytest.raises(ValueError):
        publisher.publish()
    return bootstrap


@pytest.mark.skipif(
    sys.platform != "win32"
    or os.path.normcase(os.path.normpath(sys.executable))
    != os.path.normcase(os.path.normpath(str(SELECTED_IMAGE))),
    reason="requires installed R17 Python and real disposable Windows roots",
)
@pytest.mark.parametrize("case", ["valid", "full_pair", "only_first_image", "foreign_image", "source_file_created"])
def test_two_initial_native_coordination_journals_staged_before_activation(
        monkeypatch, case):
    real_before = inspect_two_lane_native_roots()
    assert real_before["all_twelve_distinct_and_empty"] is True
    initial = r17_handoff()
    assert initial["financial_issuer_present"] is False
    assert set(initial["accounts"]) == {"QUALITY_DIPS", "HYPERLIQUID"}
    raw = POLICY_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == POLICY_SHA256
    policy = json.loads(raw)
    parent = Path(__file__).resolve().parents[1] / "logs" / "diagnostics"
    with tempfile.TemporaryDirectory(prefix="atlas-r17-journals-", dir=parent) as temporary:
        base = Path(temporary).resolve(strict=True)
        native = native_primitives()
        rows, paths = {}, {}
        for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
            parent_lane = base / ("atlas-r17-inception-" + lane.lower())
            parent_lane.mkdir()
            draft = copy.deepcopy(initial["accounts"][lane])
            draft["personal_policy"] = copy.deepcopy(policy)
            epoch = draft["provisional_enrollment_unaccepted"]["epoch"]
            path = parent_lane / epoch
            inception = _disposable_inception(
                lane, base=path, draft=draft, native=native,
                stamp=max(
                    int(time.time()),
                    int(draft["provisional_parameters_historical_open_time"]["opened_at"]) + 40))
            rows[lane] = inception
            paths[lane] = path

        def roots():
            return inspect_two_lane_native_roots(
                qd_base=paths["QUALITY_DIPS"],
                qd_custody=paths["QUALITY_DIPS"] / "custody",
                hl_base=paths["HYPERLIQUID"],
                hl_custody=paths["HYPERLIQUID"] / "custody")

        before = roots()
        assert before["native_root_total"] == 12
        assert before["all_twelve_distinct_and_empty"] is True
        qd, hl = (rows[lane]["native_enrollment"]
                  for lane in ("QUALITY_DIPS", "HYPERLIQUID"))
        owner = object.__new__(RetainedSelectedNativeOwnerPreflight)
        owner.release_digest = qd["release_digest"]
        owner._original_qd, owner._original_perp = copy.deepcopy(qd), copy.deepcopy(hl)
        owner._qd, owner._perp = digest(qd), digest(hl)
        owner._native_binding = require_exact_r15_preinception_roots(qd, hl, before)
        owner._roots, owner._phase = before, "PREINCEPTION"
        owner._initial_coordination = None
        owner._initial_cuts = None
        owner._initial_bootstraps = None
        monkeypatch.setattr(owner, "_verify_original_job", lambda: True)
        from scripts.observation_runtime import (
            personal_native_selected_owned_job_preflight as native_owner,
        )
        monkeypatch.setattr(native_owner, "inspect_two_lane_native_roots", roots)
        ledgers = []
        try:
            for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
                if case == "only_first_image" and lane == "HYPERLIQUID":
                    ledgers.append(None)
                    continue
                e = rows[lane]
                ledger = only_initial_journal_publication(
                    e["native_enrollment"], e["parameters"])
                ledgers.append(ledger)
            after = roots()
            assert after["existing_empty_root_namespaces"] == (
                11 if case == "only_first_image" else 10)
            if case == "source_file_created":
                target = paths["QUALITY_DIPS"] / "source" / "forbidden.json"
                target.write_text("NOT AN ACCOUNT", encoding="utf-8")
            if case == "foreign_image":
                ledgers[1].manifest["release"] = "f" * 64
            if case in ("valid", "full_pair"):
                receipt = owner.observe_preinception_coordination(
                    qd_ledger=ledgers[0], hl_ledger=ledgers[1])
                assert receipt["initial_native_coordination_journals_verified"] == 2
                assert receipt["other_original_financial_roots_empty"] == 10
                assert receipt["financial_writer_lease_issued"] is False
                assert receipt["paper_start_authorized"] is False
                assert owner._phase == "PREINCEPTION_COORDINATION_READY"
                assert owner.verify_still_running() is True
                if case == "full_pair":
                    at = int(time.time())
                    q_bootstrap = publish_disposable_initial_account(
                        rows["QUALITY_DIPS"], ledgers[0], at=at)
                    h_bootstrap = publish_disposable_initial_account(
                        rows["HYPERLIQUID"], ledgers[1], at=at)
                    admitted = owner.observe_verified_initial_inceptions(
                        qd_bootstrap=q_bootstrap, hl_bootstrap=h_bootstrap)
                    assert admitted["both_initial_fs1_fs3_readbacks_verified"] is True
                    assert admitted["paper_start_authorized"] is False
                    assert owner._phase == "INITIAL_READBACK_ONLY"
                    assert owner.verify_still_running() is True
                with pytest.raises(ValueError, match="ALREADY_ATTEMPTED"):
                    owner.observe_preinception_coordination(
                        qd_ledger=ledgers[0], hl_ledger=ledgers[1])
            else:
                with pytest.raises((ValueError, TypeError)):
                    owner.observe_preinception_coordination(
                        qd_ledger=ledgers[0], hl_ledger=ledgers[1])
                assert owner._phase == "PREINCEPTION_COORDINATION_PENDING"
                with pytest.raises(ValueError, match="INCEPTION_UNKNOWN"):
                    owner.verify_still_running()
        finally:
            for ledger in ledgers:
                if ledger is not None:
                    ledger.images.close()
    assert inspect_two_lane_native_roots() == real_before
