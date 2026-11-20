"""Read-only R14 native clock ancestry plus future single-release extension.

These checks bind ONLY source to selected native code; no independent NTP,
financial authority, provider connection, account/ledger mutation or selection.
"""
import copy
from pathlib import Path

import pytest

from scripts.observation_runtime import personal_version_safe_release_clock as binding
from scripts.release_selection import digest
from scripts.release_selection_store import NativeSelectionStore


def selected_records():
    store=NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection",native_root=list(binding.SELECTOR_NATIVE))
    try:
        with store.locked():
            return store.records()
    finally:
        store.close()


@pytest.fixture(scope="module")
def current():
    rows=selected_records()
    assert len(rows)==13
    assert digest(rows[10])==binding.V7_R11_HEAD
    assert digest(rows[11])==binding.R12_R12_HEAD
    assert digest(rows[12])==binding.R14_R13_HEAD
    return rows


def source(release):
    return binding.RELEASE_PARENT/release/binding.CLOCK_RELATIVE


def next_selected_row(rows):
    future="f"*40
    row=copy.deepcopy(rows[-1])
    row["revision"]=14
    row["previous"]=digest(rows[-1])
    row["operation"]="0123456789abcdef0123456789abcdef"
    row["selected"]["release"]=future
    row["selected"]["root"]=str(binding.RELEASE_PARENT/future)
    row["selected"]["receipt"]=str(
        Path("D:/Work/Project Atlas/logs/diagnostics")/
        ("qd-unselected-release-"+future+".json"))
    return row


def test_real_r14_13_record_chain_pure_native_source_admission(current):
    head, spec=binding.admit_version_safe_clock_source(
        source_file=source(binding.R14_RELEASE),records=current)
    assert head==binding.R14_R13_HEAD
    assert spec["release"]==binding.R14_RELEASE
    assert spec["artifact_digest"]==current[-1]["selected"]["artifact_digest"]


def test_pre_r14_r12_historical_clock_contract_remains_compatible(current):
    rows=copy.deepcopy(current[:12])
    head, spec=binding.admit_version_safe_clock_source(
        source_file=source(binding.R12_RELEASE),records=rows)
    assert head==binding.R12_R12_HEAD
    assert spec["release"]==binding.R12_RELEASE


def test_future_code_release_must_extend_real_r14_selected_head(current):
    future=next_selected_row(current)
    rows=copy.deepcopy(current)+[future]
    head, spec=binding.admit_version_safe_clock_source(
        source_file=source(future["selected"]["release"]),records=rows)
    assert head==digest(future)
    assert spec["release"]=="f"*40
    assert spec["artifact_digest"]==current[-1]["selected"]["artifact_digest"]


@pytest.mark.parametrize("damage",[
    "v7_anchor","r12_head","r12_selected_release","r13_head",
    "r13_previous","r13_release","r13_restore","r13_operation",
    "r13_revision","r13_tampered_previous","missing_r13",
])
def test_r14_ancestry_mutation_cannot_be_admitted(current,damage):
    rows=copy.deepcopy(current)
    if damage=="v7_anchor":
        rows[10]["operation"]="a"*32
    elif damage=="r12_head":
        rows[11]["operation"]="a"*32
    elif damage=="r12_selected_release":
        rows[11]["selected"]["release"]="a"*40
    elif damage=="r13_head":
        rows[12]["operation"]="b"*32
    elif damage=="r13_previous":
        rows[12]["previous"]="0"*64
    elif damage=="r13_release":
        rows[12]["selected"]["release"]="f"*40
    elif damage=="r13_restore":
        rows[12]["action"]="RESTORE"
    elif damage=="r13_operation":
        rows[12]["operation"]="a"*32
    elif damage=="r13_revision":
        rows[12]["revision"]=12
    elif damage=="r13_tampered_previous":
        rows[12]["previous"]=binding.V7_R11_HEAD
    else:
        rows.pop()
    with pytest.raises(ValueError):
        binding.admit_version_safe_clock_source(
            source_file=source(binding.R14_RELEASE),records=rows)


@pytest.mark.parametrize("damage",[
    "previous","revision","restore","action","release","root","bad_receipt",
])
def test_future_release_must_extend_real_r14_with_one_exact_select(current,damage):
    rows=copy.deepcopy(current)
    row=next_selected_row(rows)
    if damage=="previous":
        row["previous"]=binding.R12_R12_HEAD
    elif damage=="revision":
        row["revision"]=13
    elif damage=="restore":
        row["restores"]=12
    elif damage=="action":
        row["action"]="RESTORE"
    elif damage=="release":
        row["selected"]["release"]=binding.R14_RELEASE
    elif damage=="root":
        row["selected"]["root"]=str(binding.RELEASE_PARENT/binding.R14_RELEASE)
    else:
        row["selected"]["receipt"]="D:/outside/receipt.json"
    rows.append(row)
    with pytest.raises(ValueError):
        binding.admit_version_safe_clock_source(
            source_file=source("f"*40),records=rows)


def test_active_r14_source_refuses_stale_r12_code_after_selection(current):
    with pytest.raises(ValueError,match="SELECTED_CODE_MISMATCH"):
        binding.admit_version_safe_clock_source(
            source_file=source(binding.R12_RELEASE),records=current)


def test_workspace_clock_source_cannot_gain_native_or_network_authority(monkeypatch,current):
    with pytest.raises(ValueError,match="OWN_RELEASE_REQUIRED"):
        binding.admit_version_safe_clock_source(
            source_file=Path(__file__).resolve().parents[1]/binding.CLOCK_RELATIVE,
            records=current)
    monkeypatch.setattr(binding,"IndependentNtpClock",
                        lambda **_:pytest.fail("NETWORK_TIME_NOT_AUTHORIZED"))
    with pytest.raises(ValueError,match="INSTALLED_SOURCE_REQUIRED"):
        binding.NativeVersionSafePaperOperatorClock(runtime_id="synthetic-disallowed")


def test_anchored_chain_has_explicit_bounded_depth(current):
    rows=copy.deepcopy(current)
    future=next_selected_row(rows)
    rows.append(future)
    for n in range(15,66):
        child=copy.deepcopy(rows[-1])
        child["revision"]=n
        child["previous"]=digest(rows[-1])
        rows.append(child)
    with pytest.raises(ValueError,match="V7_PREDECESSOR_REQUIRED"):
        binding.admit_version_safe_clock_source(
            source_file=source("f"*40),records=rows)
