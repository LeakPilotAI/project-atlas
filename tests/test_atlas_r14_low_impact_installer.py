"""R14 new code-only adapter: strictly source/plan tests; never bulk-copy.

All test paths preserve selected R12, previous failed R13, and the empty R14
native destination. Only the final inspection reads pinned ~5MB source inputs.
"""
import json
import os

import pytest

from scripts import atlas_r14_low_impact_installer as r14


def test_r14_operator_approval_absent_refuses_before_any_native_io(monkeypatch):
    monkeypatch.setattr(r14, "APPROVAL_SHA256", None)
    monkeypatch.setattr(r14, "prepare_readonly",
                        lambda: pytest.fail("NO_SOURCE_HASH_BEFORE_CONSENT"))
    monkeypatch.setattr(r14, "_copy_prepared_code",
                        lambda **_: pytest.fail("NO_NATIVE_COPY_WITHOUT_CONSENT"))
    monkeypatch.setattr(r14, "write_new_json",
                        lambda *_: pytest.fail("NO_NATIVE_JOURNAL_WITHOUT_CONSENT"))
    with pytest.raises(ValueError, match="R14_EXPLICIT_CODE_INSTALL_EXECUTION_REQUIRED"):
        r14.install(execute_approved=False)
    with pytest.raises(ValueError, match="R14_SEPARATE_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_YET_GRANTED"):
        r14.install(execute_approved=True)


def test_r14_pinned_review_has_no_install_or_financial_scope():
    review = r14._review_pinned()
    assert review["frozen_source_commit"] == r14.SOURCE
    assert review["source_archive_sha256"] == r14.ARCHIVE_SHA256
    assert review["planned_native_files"] == 10519
    assert review["planned_native_bytes"] == 263456250
    for field in ("installation_authorized", "installed", "selection_allowed",
                  "financial_authority", "paper_orders_authorized",
                  "live_orders_authorized", "provider_access"):
        assert review[field] is False


def test_r14_review_digest_is_immutable(monkeypatch):
    monkeypatch.setattr(r14, "REVIEW_SHA256", "0"*64)
    with pytest.raises(ValueError, match="PINNED_SOURCE_DIGEST_MISMATCH"):
        r14._review_pinned()


def test_r14_failed_r13_journal_exactly_preserved():
    assert r14._old_r13_refusal_preserved() is None
    assert r14.PREVIOUS_R13.is_dir()
    assert not r14.PREVIOUS_R13_FINAL.exists()


def test_r14_failed_r13_journal_digest_is_not_optional(monkeypatch):
    monkeypatch.setattr(r14, "PREVIOUS_R13_JOURNAL_SHA256", "0"*64)
    with pytest.raises(ValueError, match="R13_PINNED_SOURCE_DIGEST_MISMATCH"):
        r14._old_r13_refusal_preserved()


def test_r14_occupied_destination_is_refused_not_reused(monkeypatch):
    # Point R14 proposed destination at the actual preserved R13 failure tree,
    # without opening, mutating, deleting or walking any of its file contents.
    monkeypatch.setattr(r14, "DESTINATION", r14.PREVIOUS_R13)
    with pytest.raises(ValueError, match="R14_CREATE_ONLY_TARGET_ALREADY_USED"):
        r14._require_empty_target()


def test_r14_preflight_requires_actual_fresh_target():
    if os.path.lexists(r14.DESTINATION) or os.path.lexists(r14.RECEIPT):
        # A completed or partial code copy permanently consumes this target;
        # a second install must not be attempted even with later consent.
        with pytest.raises(ValueError, match="R14_CREATE_ONLY_TARGET_ALREADY_USED"):
            r14._require_empty_target()
        return
    assert not r14.RECEIPT.with_suffix(".pending.jsonl").exists()
    assert r14._require_empty_target() is True


def test_r14_future_approval_cannot_reuse_r13_scope(monkeypatch):
    # Even if an R13-style consent file appears in the new R14 location,
    # the R14 schema and precise source pins are required.
    r13_record = {
        "schema":"ATLAS_R13_CODE_ONLY_INSTALL_APPROVAL_V1",
        "decision":"APPROVE_ONE_UNSELECTED_CODE_COPY",
        "source":r14.SOURCE,
        "archive_sha256":r14.ARCHIVE_SHA256,
        "dependency_sha256":r14.DEPENDENCY_INVENTORY_SHA256,
        "operator_sid":"SYNTHETIC_TEST_ONLY","one_shot":True,
        "selection_allowed":False,"financial_authority":False,
        "provider_access":False,"startup_authorized":False,
    }
    monkeypatch.setattr(r14, "APPROVAL_SHA256", "a"*64)
    monkeypatch.setattr(r14, "_exact_bytes",
                        lambda *_args, **_kwargs: json.dumps(r13_record).encode())
    with pytest.raises(ValueError, match="R14_UNSELECTED_CODE_ONLY_APPROVAL_SCOPE_REFUSED"):
        r14._require_separate_consent()


@pytest.mark.parametrize("flag", ["financial_authority", "selection_allowed",
                                  "provider_access", "startup_authorized"])
def test_r14_future_approval_denies_expanded_scope(monkeypatch, flag):
    r14_record = {
        "schema":"ATLAS_R14_CODE_ONLY_INSTALL_APPROVAL_V1",
        "decision":"APPROVE_ONE_UNSELECTED_CODE_COPY",
        "source":r14.SOURCE,
        "archive_sha256":r14.ARCHIVE_SHA256,
        "dependency_sha256":r14.DEPENDENCY_INVENTORY_SHA256,
        "operator_sid":"SYNTHETIC_TEST_ONLY","one_shot":True,
        "selection_allowed":False,"financial_authority":False,
        "provider_access":False,"startup_authorized":False,
    }
    r14_record[flag] = True
    monkeypatch.setattr(r14, "APPROVAL_SHA256", "a"*64)
    monkeypatch.setattr(r14, "_exact_bytes",
                        lambda *_args, **_kwargs: json.dumps(r14_record).encode())
    with pytest.raises(ValueError, match="R14_UNSELECTED_CODE_ONLY_APPROVAL_SCOPE_REFUSED"):
        r14._require_separate_consent()


def test_r14_inspect_uses_idle_envelope_even_on_preflight_error(monkeypatch):
    calls=[]
    class SimulatedEnvelope:
        def __init__(self, **kwargs):
            assert kwargs["check_every"]==32 and kwargs["pace_every"]==128
        def __enter__(self):
            calls.append("enter")
            return self
        def tick(self):
            calls.append("tick")
        def __exit__(self, *_):
            calls.append("restore")
    def refuse():
        assert calls == ["enter"]
        raise ValueError("SYNTHETIC_SOURCE_REFUSAL")
    monkeypatch.setattr(r14, "LowImpactEnvelope", SimulatedEnvelope)
    monkeypatch.setattr(r14, "prepare_readonly", refuse)
    with pytest.raises(ValueError, match="SYNTHETIC_SOURCE_REFUSAL"):
        r14.inspect()
    assert calls == ["enter","restore"]


def test_r14_native_clock_admission_every_32_and_no_more_than_one_second(monkeypatch):
    monkeypatch.setattr(r14, "require_code_install_host_ready", lambda *_: True)
    clock_calls = []

    class Guard:
        def __init__(self):
            self.checks = 0
            self.now = 100.0
        def tick(self):
            self.checks += 1
            assert self.now < 600.0
        def monotonic(self):
            return self.now

    class Clock:
        def require_operational(self, identity):
            assert identity.startswith("r14-code-only-")
            clock_calls.append(guard.checks)

    guard = Guard()
    clock = Clock()
    identity = "r14-code-only-" + r14.SOURCE
    for _ in range(96):
        assert r14._native_admission(clock, identity, guard) is True
    assert clock_calls == [1, 32, 64, 96]
    # A stalled disk must not bypass clock continuity just because there
    # have been fewer than another 32 native I/O admissions.
    guard.now += 1.001
    assert r14._native_admission(clock, identity, guard) is True
    assert clock_calls == [1, 32, 64, 96, 97]


def test_r14_clock_refusal_fails_next_bounded_checkpoint(monkeypatch):
    monkeypatch.setattr(r14, "require_code_install_host_ready", lambda *_: True)
    clock_calls = []
    class Guard:
        checks = 0
        def tick(self):
            self.checks += 1
        def monotonic(self):
            return 1.0
    class Clock:
        def require_operational(self, identity):
            clock_calls.append(guard.checks)
            if len(clock_calls) == 2:
                raise ValueError("NTP_CAPABILITY_REVOKED")
    guard = Guard()
    for _ in range(31):
        assert r14._native_admission(Clock(), "r14-code-only-x", guard)
    with pytest.raises(ValueError, match="NTP_CAPABILITY_REVOKED"):
        r14._native_admission(Clock(), "r14-code-only-x", guard)
    assert clock_calls == [1, 32]


def test_r14_readback_child_timeout_never_exceeds_work_deadline():
    class Guard:
        started = 100.0
        max_seconds = 500
        now = 100.0
        checks = 0
        def tick(self):
            self.checks += 1
            if self.now - self.started >= self.max_seconds:
                raise ValueError("R14_WORK_DEADLINE")
        def monotonic(self):
            return self.now
    guard = Guard()
    assert r14._remaining_installed_readback_timeout(guard) == 120
    guard.now = 550.0  # 50 seconds left before hard 500s gate.
    assert r14._remaining_installed_readback_timeout(guard) == 45
    guard.now = 565.0  # 35 seconds cannot justify a new child readback.
    with pytest.raises(ValueError, match="R14_INSTALLED_READBACK_TIME_BUDGET_REFUSED"):
        r14._remaining_installed_readback_timeout(guard)
    guard.now = 600.0  # Hard deadline must still refuse.
    with pytest.raises(ValueError, match="R14_WORK_DEADLINE"):
        r14._remaining_installed_readback_timeout(guard)


def test_r14_rechecks_clock_after_monotonic_backwards_step(monkeypatch):
    monkeypatch.setattr(r14, "require_code_install_host_ready", lambda *_: True)
    class Guard:
        checks = 0
        now = 2.0
        def tick(self):
            self.checks += 1
        def monotonic(self):
            return self.now
    class Clock:
        def __init__(self):
            self.calls = 0
        def require_operational(self, identity):
            self.calls += 1
    guard, clock = Guard(), Clock()
    r14._native_admission(clock, "r14-code-only-x", guard)
    guard.now = 1.0
    r14._native_admission(clock, "r14-code-only-x", guard)
    assert clock.calls == 2


def test_r14_exact_source_plan_and_readonly_preview():
    if os.path.lexists(r14.DESTINATION) or os.path.lexists(r14.RECEIPT):
        # The release was already installed or attempted. The read-only
        # preinstall preview must refuse rather than re-admit occupied space.
        with pytest.raises(ValueError, match="R14_CREATE_ONLY_TARGET_ALREADY_USED"):
            r14.inspect()
        return
    report = r14.inspect()
    assert report["status"] == "NATIVE_LAYOUT_AND_INPUTS_VERIFIED_NOT_INSTALL_APPROVAL"
    assert report["source_files"] == 953
    assert report["dependency_files"] == 9566
    assert report["planned_files"] == 10519
    assert report["planned_bytes"] == 263456250
    assert report["idle_priority_required"] is True
    assert (report["check_every"], report["pace_every"]) == (32,128)
    assert not any(report[k] for k in (
        "installation_authorized", "installed","selection_allowed",
        "paper_orders_authorized","live_orders_authorized"))
    # Inspection has no authority even when a separately pinned one-shot
    # install approval exists for a single future attempt.
    assert report["installation_authorized"] is False
    assert not os.path.lexists(r14.DESTINATION)
    assert not os.path.lexists(r14.RECEIPT)
    assert not os.path.lexists(r14.RECEIPT.with_suffix(".pending.jsonl"))


def _disposable_install_harness(monkeypatch, tmp_path, *, copy_fails=False):
    """Exercise the true R14 coordinator, replacing ALL native I/O/clock.

    No real release directory, market account, NTP socket or child is touched.
    """
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    from scripts import install_version_safe_candidate as clock_gate

    events = []
    class SyntheticClock:
        def require_operational(self, identity):
            assert identity == "r14-code-only-" + r14.SOURCE
            events.append("clock")
            return self

    class SyntheticGuard:
        def __init__(self, **kwargs):
            assert kwargs["check_every"] == 32
            assert kwargs["pace_every"] == 128
            self.started, self.max_seconds, self.checks = None, 500, 0
        def __enter__(self):
            self.started = 100.0
            events.append("idle_enter")
            return self
        def __exit__(self, *_):
            events.append("idle_restore")
        def monotonic(self):
            return 100.0
        def tick(self):
            self.checks += 1
            return True

    monkeypatch.setattr(ntp, "IndependentNtpClock", SyntheticClock)
    monkeypatch.setattr(clock_gate, "_qualify_native_clock_180s",
                        lambda *_: events.append("clock_180s_synthetic"))
    monkeypatch.setattr(r14, "_require_separate_consent",
                        lambda: events.append("consent"))
    monkeypatch.setattr(r14, "require_code_install_host_ready",
                        lambda *_: events.append("synthetic_host_ready") or True)
    monkeypatch.setattr(r14, "LowImpactEnvelope", SyntheticGuard)
    monkeypatch.setattr(r14, "prepare_readonly", lambda: {"started": 100.0})
    monkeypatch.setattr(r14, "_selector_unchanged", lambda: events.append("selector") or True)
    monkeypatch.setattr(r14, "DESTINATION", tmp_path / "never_native_copy_here")
    monkeypatch.setattr(r14, "RECEIPT", tmp_path / "synthetic-final-receipt.json")

    def copy(*, destination, archive_sha256, source_commit,
             prepared, observer, admission):
        assert destination == tmp_path / "never_native_copy_here"
        assert archive_sha256 == r14.ARCHIVE_SHA256
        assert source_commit == r14.SOURCE
        assert observer is None
        assert r14.RECEIPT.with_suffix(".pending.jsonl").exists()
        events.append("copy_stub")
        admission()
        if copy_fails:
            raise ValueError("SYNTHETIC_NATIVE_COPY_REFUSAL")
        return {"files": [{"path": "mock.py", "bytes": 0,
                           "sha256": "0"*64, "id": [1, 2, 3]}],
                "directories": [{"path": ".", "id": [1, 2, 4]}]}

    def installed_readback(destination, receipt, digest, *, timeout):
        assert destination == tmp_path / "never_native_copy_here"
        assert receipt["selected"] is False
        assert receipt["financial_effects"] is False
        assert receipt["provider_connections"] is False
        assert timeout <= 120 and timeout > 0
        events.append("installed_readback_stub")
        return {"layout": {"synthetic": "readback_mock_only"}}

    monkeypatch.setattr(r14, "_copy_prepared_code", copy)
    monkeypatch.setattr(r14, "installed_readback", installed_readback)
    return SyntheticClock(), events


def test_r14_synthetic_authorized_flow_writes_only_disposable_proof(monkeypatch, tmp_path):
    clock, events = _disposable_install_harness(monkeypatch, tmp_path)
    receipt = r14.install(execute_approved=True, clock=clock)
    assert receipt["selected"] is False
    assert receipt["provider_connections"] is False
    assert receipt["financial_effects"] is False
    assert receipt["operational_acceptance"] is False
    assert receipt["source_commit"] == r14.SOURCE
    assert r14.RECEIPT.is_file()
    journal = r14.RECEIPT.with_suffix(".pending.jsonl").read_text().splitlines()
    assert len(journal) == 2
    assert json.loads(journal[0])["selection_allowed"] is False
    assert json.loads(journal[-1])["stage"] == "NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING"
    assert json.loads(journal[-1])["financial_authority"] is False
    assert json.loads(journal[-1])["artifact_digest"] == receipt["artifact_digest"]
    assert "copy_stub" in events and "installed_readback_stub" in events
    assert events[-1] == "idle_restore"
    assert not r14.DESTINATION.exists()


def test_r14_synthetic_copy_refusal_keeps_journal_without_final_receipt(monkeypatch, tmp_path):
    clock, events = _disposable_install_harness(monkeypatch, tmp_path, copy_fails=True)
    with pytest.raises(ValueError, match="SYNTHETIC_NATIVE_COPY_REFUSAL"):
        r14.install(execute_approved=True, clock=clock)
    assert not r14.RECEIPT.exists()
    journal = r14.RECEIPT.with_suffix(".pending.jsonl").read_text().splitlines()
    assert len(journal) == 2
    assert json.loads(journal[-1])["stage"] == "REFUSED_PRESERVE_PARTIAL_NO_RETRY"
    assert "installed_readback_stub" not in events
    assert events[-1] == "idle_restore"


def test_r14_disposable_final_receipt_write_failure_retains_refusal(monkeypatch, tmp_path):
    """Never claim durable acceptance if create-only final receipt cannot land."""
    clock, events = _disposable_install_harness(monkeypatch, tmp_path)
    original_writer = r14.write_new_json
    def refuse_final(path, value):
        if path == r14.RECEIPT:
            raise OSError("SYNTHETIC_FINAL_CREATE_ONLY_WRITE_REFUSAL")
        return original_writer(path, value)
    monkeypatch.setattr(r14, "write_new_json", refuse_final)
    with pytest.raises(OSError, match="SYNTHETIC_FINAL_CREATE_ONLY_WRITE_REFUSAL"):
        r14.install(execute_approved=True, clock=clock)
    assert not r14.RECEIPT.exists()
    journal = [json.loads(line) for line in
               r14.RECEIPT.with_suffix(".pending.jsonl").read_text().splitlines()]
    assert [row["stage"] for row in journal[1:]] == [
        "NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING",
        "REFUSED_PRESERVE_PARTIAL_NO_RETRY"]
    assert events[-1] == "idle_restore"
    assert not r14.DESTINATION.exists()


def test_r14_disposable_before_final_journal_failure_never_publishes_receipt(monkeypatch, tmp_path):
    """The journal is write-ahead: no final receipt on journal fsync failure."""
    clock, events = _disposable_install_harness(monkeypatch, tmp_path)
    original_open = type(r14.RECEIPT).open
    journal = r14.RECEIPT.with_suffix(".pending.jsonl")
    # This tests the terminal journal's *second* append in a confined mock
    # without changing real on-disk installation state.
    calls = []
    def refuse_prepublication(path, *args, **kwargs):
        if path == journal and args and args[0] == "ab":
            calls.append("journal_append")
            if len(calls) == 1:
                raise OSError("SYNTHETIC_PREPUBLICATION_JOURNAL_FAILURE")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(type(r14.RECEIPT), "open", refuse_prepublication)
    with pytest.raises(OSError, match="SYNTHETIC_PREPUBLICATION_JOURNAL_FAILURE"):
        r14.install(execute_approved=True, clock=clock)
    assert not r14.RECEIPT.exists()
    entries = [json.loads(line) for line in journal.read_text().splitlines()]
    assert entries[-1]["stage"] == "REFUSED_PRESERVE_PARTIAL_NO_RETRY"
    assert events[-1] == "idle_restore"


def test_r14_disposable_final_permission_revocation_prevents_publication(monkeypatch, tmp_path):
    """Consent loss after durable prepublication journal cannot issue receipt."""
    clock, events = _disposable_install_harness(monkeypatch, tmp_path)
    consents = [0]
    def consent_may_revoke():
        consents[0] += 1
        events.append("consent")
        if consents[0] >= 4:
            raise ValueError("SYNTHETIC_APPROVAL_REVOKED_BEFORE_FINAL_RECEIPT")
    monkeypatch.setattr(r14, "_require_separate_consent", consent_may_revoke)
    with pytest.raises(ValueError, match="SYNTHETIC_APPROVAL_REVOKED_BEFORE_FINAL_RECEIPT"):
        r14.install(execute_approved=True, clock=clock)
    assert consents[0] == 4
    assert not r14.RECEIPT.exists()
    journal = [json.loads(line) for line in
               r14.RECEIPT.with_suffix(".pending.jsonl").read_text().splitlines()]
    assert [row["stage"] for row in journal[1:]] == [
        "NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING",
        "REFUSED_PRESERVE_PARTIAL_NO_RETRY"]
    assert "installed_readback_stub" in events
    assert events[-1] == "idle_restore"
