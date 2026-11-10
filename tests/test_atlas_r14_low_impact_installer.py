"""R14 new code-only adapter: strictly source/plan tests; never bulk-copy.

All test paths preserve selected R12, previous failed R13, and the empty R14
native destination. Only the final inspection reads pinned ~5MB source inputs.
"""
import json
import os

import pytest

from scripts import atlas_r14_low_impact_installer as r14


def test_r14_operator_approval_absent_refuses_before_any_native_io(monkeypatch):
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
    assert not r14.DESTINATION.exists()
    assert not r14.RECEIPT.exists()
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


def test_r14_native_clock_admission_every_32_and_no_more_than_one_second():
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


def test_r14_clock_refusal_fails_next_bounded_checkpoint():
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


def test_r14_rechecks_clock_after_monotonic_backwards_step():
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
    assert r14.APPROVAL_SHA256 is None
    assert not os.path.lexists(r14.DESTINATION)
    assert not os.path.lexists(r14.RECEIPT)
    assert not os.path.lexists(r14.RECEIPT.with_suffix(".pending.jsonl"))
