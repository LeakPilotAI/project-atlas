"""Offline tests; no real selector write, NTP request, or financial call."""
import copy
from pathlib import Path

import pytest

from scripts.observation_runtime import personal_version_safe_release_clock as binding
from scripts.release_selection import digest


RELEASE = "a" * 40
SOURCE = Path("D:/AtlasRuntime/releases") / RELEASE / binding.CLOCK_RELATIVE


def chain(monkeypatch):
    prior = {"revision": 11, "selected": {"release": binding.V7_RELEASE}}
    monkeypatch.setattr(binding, "V7_R11_HEAD", digest(prior))
    spec = {
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        "release": RELEASE,
        "root": str(Path("D:/AtlasRuntime/releases") / RELEASE),
        "receipt": str(Path("D:/Work/Project Atlas/logs/diagnostics") / ("qd-unselected-release-" + RELEASE + ".json")),
        "receipt_sha256": "b" * 64,
        "artifact_digest": "c" * 64,
    }
    row = {"revision": 12, "action": "SELECT", "previous": binding.V7_R11_HEAD,
           "restores": None, "selected": spec}
    return [{"revision": i} for i in range(1, 11)] + [prior, row]


def test_future_release_can_use_own_installed_clock_source(monkeypatch):
    records = chain(monkeypatch)
    head, spec = binding.admit_version_safe_clock_source(source_file=SOURCE, records=records)
    assert head == digest(records[-1])
    assert spec["release"] == RELEASE
    assert "APP_RECEIPT" not in SOURCE.name  # no embedded self-referential receipt


@pytest.mark.parametrize("change", ["no_r12", "wrong_previous", "wrong_release", "wrong_receipt",
                                   "extra_revision", "v7_head_changed", "action_restore"])
def test_fail_closed_chain_or_receipt_reference(monkeypatch, change):
    records = chain(monkeypatch)
    if change == "no_r12": records.pop()
    elif change == "wrong_previous": records[-1]["previous"] = "f" * 64
    elif change == "wrong_release": records[-1]["selected"]["release"] = "d" * 40
    elif change == "wrong_receipt": records[-1]["selected"]["receipt"] = "D:/bad.json"
    elif change == "extra_revision": records.append(copy.deepcopy(records[-1]))
    elif change == "v7_head_changed": records[-2]["revision"] = 9
    elif change == "action_restore": records[-1]["action"] = "RESTORE"
    with pytest.raises(ValueError):
        binding.admit_version_safe_clock_source(source_file=SOURCE, records=records)


def test_workspace_source_is_never_native_candidate(monkeypatch):
    records = chain(monkeypatch)
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_OWN_RELEASE_REQUIRED"):
        binding.admit_version_safe_clock_source(
            source_file=Path(__file__).resolve().parents[1] / binding.CLOCK_RELATIVE,
            records=records)
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_INSTALLED_SOURCE_REQUIRED"):
        binding.require_native_version_safe_clock_source()


def test_old_v8_code_cannot_claim_future_candidate(monkeypatch):
    records = chain(monkeypatch)
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_SELECTED_CODE_MISMATCH"):
        binding.admit_version_safe_clock_source(source_file=Path("D:/AtlasRuntime/releases") / ("d" * 40) / binding.CLOCK_RELATIVE, records=records)
