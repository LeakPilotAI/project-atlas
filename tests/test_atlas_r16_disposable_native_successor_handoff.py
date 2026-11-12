"""R17 source-only handoff against genuine disposable native R16 FS1/FS3 files.

This tests native account file/ACK transitions with REAL Windows file handles
and disposable on-disk SQLite. Native original selected R16 executes Python,
but the R17 owner object is deliberately uninstantiated/unowned: only its
storage-state method is exercised. No genuine R17 owner/issuer acceptance.
Original personal PAPER roots never receive writes. No providers/orders.
"""
from __future__ import annotations

import copy
import json
import os
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_publication_custody import PersonalPublicationCustody
from test_atlas_r16_disposable_native_dual_inception import (
    exact_disposable_test_root,
    prepare_lane,
)

from scripts.observation_runtime import (
    personal_native_selected_owned_job_preflight as successor,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    RELEASE,
    selected_code,
)
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    inspect as draft_inspect,
)
from scripts.observation_runtime.atlas_r16_two_account_financial_arithmetic import (
    POLICY_PATH,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
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


class DisposableOnDiskLedger:
    """Real SQLite durable ACK in disposable diagnostics, never Atlas custody."""

    def __init__(self, path):
        self.path = Path(path)
        assert self.path.parent.is_dir() and not self.path.exists()
        with self.connect() as db:
            PersonalPublicationCustody.install_schema(db)

    @contextmanager
    def connect(self, readonly=False):
        connection = sqlite3.connect(str(self.path), timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def publish_durable_fixture(e, *, at, path):
    ledger = DisposableOnDiskLedger(path)
    custody = PersonalPublicationCustody(ledger)

    @contextmanager
    def nonfinancial_test_issuer(scope, stamp):
        assert stamp == at
        yield SimpleNamespace(
            check=lambda candidate, t: candidate == scope and t == at)

    @contextmanager
    def nonfinancial_test_owner(context, stamp):
        assert stamp == at
        yield SimpleNamespace(
            check=lambda candidate, t: candidate == context and t == at)

    bootstrap = PersonalInceptionBootstrap(
        enrollment=e, publication=custody,
        issuer=SimpleNamespace(lease=nonfinancial_test_issuer),
        clock=lambda: at, readback=NativePersonalInitialReadback(),
    )
    publisher = PersonalInceptionPublisher(
        bootstrap=bootstrap, custody=custody,
        ownership=SimpleNamespace(lease=nonfinancial_test_owner),
        observer=lambda: {"schema": "QD_OP_PROCESS_ID_V1", **observe_self()},
        files=NativePersonalInceptionFiles(),
    )
    ready = publisher.publish()
    assert ready["financial_startup_authorized"] is False
    assert bootstrap.verify_publication()["current"] == ready["current"]
    with pytest.raises(ValueError):
        publisher.publish()
    return bootstrap, ledger


def exact_disposable_readback(*, qd_base, hl_base):
    return inspect_two_lane_native_roots(
        qd_base=qd_base, qd_custody=qd_base/"custody",
        hl_base=hl_base, hl_custody=hl_base/"custody",
    )


@pytest.mark.skipif(
    sys.platform != "win32"
    or os.path.normcase(os.path.normpath(sys.executable)) !=
       os.path.normcase(os.path.normpath(str(RELEASE/"python/python.exe"))),
    reason="requires selected R16 installed D: Python and native Windows handles",
)
def test_real_disposable_native_publisher_acknowledged_two_lane_successor_transition(
        monkeypatch):
    original_before = inspect_two_lane_native_roots()
    assert original_before["native_root_total"] == 12
    assert original_before["all_twelve_distinct_and_empty"] is True
    assert selected_code()["selected_revision"] == 15
    parent = Path(__file__).resolve().parents[1]/"logs/diagnostics"
    assert parent.is_dir() and not parent.is_symlink()
    with tempfile.TemporaryDirectory(
            prefix="atlas-r16-native-disposable-", dir=parent) as disposable:
        root = exact_disposable_test_root(disposable)
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8-sig"))
        proposal = draft_inspect()
        native = native_primitives()
        e, bases = {}, {}
        for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
            parent_lane = root/lane
            parent_lane.mkdir()
            original = proposal["accounts"][lane]
            epoch = original["provisional_r16_enrollment_unaccepted"]["epoch"]
            base = parent_lane/epoch
            e[lane], _ = prepare_lane(
                lane, base=base, original=original,
                policy=policy, native=native,
            )
            bases[lane] = base
        q, h = (e[k]["native_enrollment"] for k in ("QUALITY_DIPS", "HYPERLIQUID"))
        qd_base = bases["QUALITY_DIPS"]
        hl_base = bases["HYPERLIQUID"]
        evidence = exact_disposable_readback(qd_base=qd_base, hl_base=hl_base)
        assert evidence["all_twelve_distinct_and_empty"] is True
        binding = require_exact_r15_preinception_roots(q, h, evidence)
        at = int(time.time())
        q_boot, q_ledger = publish_durable_fixture(
            e["QUALITY_DIPS"], at=at, path=root/"qd-ack.sqlite")
        h_boot, h_ledger = publish_durable_fixture(
            e["HYPERLIQUID"], at=at, path=root/"hl-ack.sqlite")
        assert q_ledger.path.is_file() and h_ledger.path.is_file()
        after = exact_disposable_readback(qd_base=qd_base, hl_base=hl_base)
        assert after["native_root_ids_verified"] == 12
        assert after["all_twelve_distinct_and_empty"] is False
        assert after["existing_empty_root_namespaces"] < 12

        # Synthetic in-process preflight owner only; NO original Job claim.
        # Genuine selected R17 must separately provide held Job/PROCESS proof.
        owner = object.__new__(successor.RetainedSelectedNativeOwnerPreflight)
        owner._phase = "PREINCEPTION"
        owner._initial_cuts = None
        owner._initial_bootstraps = None
        owner._original_qd, owner._original_perp = copy.deepcopy(q), copy.deepcopy(h)
        owner._qd, owner._perp = digest(q), digest(h)
        owner._native_binding = binding
        monkeypatch.setattr(owner, "_verify_original_job", lambda: True)
        monkeypatch.setattr(successor, "inspect_two_lane_native_roots",
                            lambda: exact_disposable_readback(
                                qd_base=qd_base, hl_base=hl_base))
        admitted = owner.observe_verified_initial_inceptions(
            qd_bootstrap=q_boot, hl_bootstrap=h_boot)
        assert admitted["both_initial_fs1_fs3_readbacks_verified"] is True
        assert admitted["financial_writer_lease_issued"] is False
        assert admitted["paper_start_authorized"] is False
        assert owner.verify_still_running() is True

        # Real durable ACK lost: the same held owner must refuse even though
        # untouched FS1/FS3 initial files still look correct on disk.
        with h_ledger.connect() as db:
            db.execute("UPDATE personal_publications SET state='UNKNOWN'")
        with pytest.raises(ValueError, match="PERSONAL_PUBLICATION_NOT_ACKNOWLEDGED"):
            owner.verify_still_running()
        assert original_before == inspect_two_lane_native_roots()
        assert not hasattr(owner, "lease")
