"""R17 source successor: actual Windows FS1/FS3 for both disposable PAPER lanes.

Runs workspace source using the installed R17 Python executable, not the immutable
R17 source image. Original D:/AtlasCustody account directories are read ONLY.
Every actual native financial write targets a fresh diagnostics-only test root.
Synthetic test issuer is NOT a native financial Job, activation or authorization.
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
from app.services.perp_operational_contract import WRITERS as HL_WRITERS
from app.services.personal_publication_custody import PersonalPublicationCustody
from app.services.quality_dips_autonomous_enrollment import WRITERS as QD_WRITERS
from test_personal_session_reservation_integrity import Memory

from scripts.observation_runtime.atlas_r16_two_account_financial_arithmetic import (
    POLICY_PATH,
    POLICY_SHA256,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_SOURCE,
)
from scripts.observation_runtime.atlas_r17_two_account_inception_handoff import (
    inspect as inspect_r17_handoff,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES,
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
    native_primitives,
    validate_personal_inception,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

SELECTED_PYTHON = Path("D:/AtlasRuntime/releases") / R17_SOURCE / "python/python.exe"


def _disposable_inception(lane, *, base, draft, native, stamp):
    assert lane in ("QUALITY_DIPS", "HYPERLIQUID")
    assert not base.exists() and base.parent.name.startswith("atlas-r17-inception-")
    base.mkdir()
    manifest = copy.deepcopy(draft["provisional_parameters_historical_open_time"])
    enrollment = copy.deepcopy(draft["provisional_enrollment_unaccepted"])
    scope = copy.deepcopy(draft["provisional_report_scope_unaccepted"])
    assert manifest["release"] == enrollment["release_digest"]
    assert manifest["opening_cash"] == "1000"
    assert enrollment["writers"] is None
    assert enrollment["acceptance_id"] is None
    assert stamp > manifest["opened_at"]

    # All test output roots are newly created in the private disposable tree.
    for role in ROLES:
        original = copy.deepcopy(enrollment["resources"][role])
        with native.w.WindowsOutput.create_root(str(base / role)) as output:
            replacement = {
                "path": str(output.root),
                "native_id": native.native.file_identity(output.root_handle),
            }
        assert replacement["path"] != original["path"]
        assert replacement["native_id"] != original["native_id"]
        enrollment["resources"][role].update(replacement)

    observed = observe_self()
    assert os.path.normcase(observed["image"]) == os.path.normcase(str(SELECTED_PYTHON))
    process = {"schema": "QD_OP_PROCESS_ID_V1", **observed}
    roles = QD_WRITERS if lane == "QUALITY_DIPS" else HL_WRITERS
    enrollment["writers"] = {role: copy.deepcopy(process) for role in roles}
    enrollment["acceptance_id"] = "DISPOSABLE_R17_TEST_NOT_OPERATOR_" + lane
    inception = {
        "profile": "PERSONAL_PAPER_ONLY_V1",
        "personal_policy": copy.deepcopy(draft["personal_policy"]) if "personal_policy" in draft else None,
        "lane": lane,
        "native_enrollment": enrollment,
        "parameters": manifest,
        "report_scope": scope,
    }
    return inception


def _publish_with_test_only_issuer(inception, *, stamp):
    memory = Memory()
    PersonalPublicationCustody.install_schema(memory.db)
    memory.db.commit()
    custody = PersonalPublicationCustody(memory)

    @contextmanager
    def fake_issuer(scope, now):
        assert now == stamp
        yield SimpleNamespace(check=lambda candidate, value: candidate == scope and value == stamp)

    @contextmanager
    def fake_owner(context, now):
        assert now == stamp
        yield SimpleNamespace(check=lambda candidate, value: candidate == context and value == stamp)

    bootstrap = PersonalInceptionBootstrap(
        enrollment=inception, publication=custody,
        issuer=SimpleNamespace(lease=fake_issuer),
        clock=lambda: stamp, readback=NativePersonalInitialReadback(),
    )
    publisher = PersonalInceptionPublisher(
        bootstrap=bootstrap, custody=custody,
        ownership=SimpleNamespace(lease=fake_owner),
        observer=lambda: {"schema": "QD_OP_PROCESS_ID_V1", **observe_self()},
        files=NativePersonalInceptionFiles(),
    )
    try:
        result = publisher.publish()
        assert result["financial_startup_authorized"] is False
        assert result["current"]["status"] == "ACKNOWLEDGED"
        assert result["current"]["source"]["entries"] == []
        assert NativePersonalInitialReadback().verify(inception, result["current"]) is True
        with pytest.raises(ValueError):
            publisher.publish()
        assert bootstrap.verify_publication()["current"] == result["current"]
        return digest(result["current"])
    finally:
        memory.db.close()


@pytest.mark.skipif(
    sys.platform != "win32"
    or os.path.normcase(os.path.normpath(sys.executable))
    != os.path.normcase(os.path.normpath(str(SELECTED_PYTHON))),
    reason="requires real selected R17 Windows Python image; disposable only",
)
def test_r17_source_both_lanes_publish_real_disposable_native_fs1_fs3():
    before = inspect_two_lane_native_roots()
    assert before["native_root_total"] == 12
    assert before["all_twelve_distinct_and_empty"] is True
    handoff = inspect_r17_handoff()
    assert handoff["financial_issuer_present"] is False
    assert handoff["native_account_fs1_fs3_inceptions_published"] == 0
    assert set(handoff["accounts"]) == {"QUALITY_DIPS", "HYPERLIQUID"}
    parent = Path(__file__).resolve().parents[1] / "logs/diagnostics"
    assert parent.is_dir() and not parent.is_symlink() and not parent.is_junction()
    with tempfile.TemporaryDirectory(prefix="atlas-r17-inception-", dir=parent) as folder:
        root = Path(folder).resolve(strict=True)
        assert root.parent == parent.resolve(strict=True)
        native = native_primitives()
        # Preserve the existing immutable reviewed policy bytes; never
        # invent accepted financial parameters for a simulated exercise.
        raw = POLICY_PATH.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == POLICY_SHA256
        policy = json.loads(raw)
        for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
            draft = copy.deepcopy(handoff["accounts"][lane])
            draft["personal_policy"] = copy.deepcopy(policy)
            stamp = max(int(time.time()), int(
                draft["provisional_parameters_historical_open_time"]["opened_at"]) + 40)
            inception = _disposable_inception(
                lane, base=root / lane.lower(), draft=draft,
                native=native, stamp=stamp)
            validate_personal_inception(inception)
            assert len(_publish_with_test_only_issuer(inception, stamp=stamp)) == 64
    after = inspect_two_lane_native_roots()
    assert after == before
    assert after["all_twelve_distinct_and_empty"] is True
