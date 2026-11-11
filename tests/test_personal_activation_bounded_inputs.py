"""Bounded inputs for genuine native PersonalPaper activation, not authorization.

Only disposable local JSON files; no installed activation record created,
native account roots touched, provider connection, or financial clock acquired.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import personal_activation_commission as act
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.personal_version_safe_release_clock import PROFILE


@pytest.fixture
def file(tmp_path):
    def saved(raw=b'{"schema":"OFFLINE_DATA_ONLY"}', name="record.json"):
        path = tmp_path / name
        if type(raw) is str:
            raw = raw.encode("utf-8")
        path.write_bytes(raw)
        return str(path)
    return saved


def read(path, role="record"):
    return act.read_bounded_activation_input(path, role=role)


def test_existing_ordinary_nested_object_read_with_utf8_bom(file):
    raw = b'\xef\xbb\xbf{"x":{"a":1,"b":2},"arrays":[1,2,3]}'
    assert read(file(raw)) == {"x": {"a": 1, "b": 2}, "arrays": [1, 2, 3]}


@pytest.mark.parametrize("role", sorted(act.INPUT_MAX_BYTES))
def test_exact_input_byte_caps_enforced_without_truncation(file, role):
    limit = act.INPUT_MAX_BYTES[role]
    valid = b'{"data":"' + b'x' * (limit - 11) + b'"}'
    assert len(valid) == limit
    assert read(file(valid), role=role)["data"] == 'x' * (limit - 11)
    oversized = valid + b' '
    with pytest.raises(ValueError, match="ACTIVATION_BOUNDED_JSON_INPUT_REQUIRED"):
        read(file(oversized, name="oversized.json"), role=role)


@pytest.mark.parametrize("raw,reason", [
    (b'', "BOUNDED_JSON_INPUT"),
    (b'{"x":1,"x":2}', "STRICT_JSON_INPUT"),
    (b'{"nested":{"a":1,"a":2}}', "STRICT_JSON_INPUT"),
    (b'{"x":NaN}', "STRICT_JSON_INPUT"),
    (b'{"x":Infinity}', "STRICT_JSON_INPUT"),
    (b'{"x":-Infinity}', "STRICT_JSON_INPUT"),
    (b'{"x":2e+99999}', "STRICT_JSON_INPUT"),
    (b'\xff\xff', "STRICT_JSON_INPUT"),
    (b'{"x":1', "STRICT_JSON_INPUT"),
    (b'[1,2]', "JSON_OBJECT_REQUIRED"),
    (b'null', "JSON_OBJECT_REQUIRED"),
    (b'"string"', "JSON_OBJECT_REQUIRED"),
    (b'{} garbage', "STRICT_JSON_INPUT"),
])
def test_malformed_duplicate_or_nonobject_rejected(file, raw, reason):
    with pytest.raises(ValueError, match="ACTIVATION_" + reason):
        read(file(raw))


def test_quoted_brackets_and_escaped_quote_are_not_nesting(file):
    raw = json.dumps({'brackets': '[' * 1000 + '\\"' + '}' * 1000})
    assert read(file(raw))['brackets'] == '[' * 1000 + '\\"' + '}' * 1000


def test_deeply_nested_json_rejected_as_finite_input(file):
    raw = b'{"deep":' + b'['*1250 + b'1' + b']'*1250 + b'}'
    with pytest.raises(ValueError, match="ACTIVATION_STRICT_JSON_INPUT"):
        read(file(raw))


@pytest.mark.parametrize("bad,role", [
    ("", "record"), (None, "record"),
    (False, "record"), ("here", "NO_SUCH_ROLE"),
    ("x" + "\x00" + "y", "record"),
])
def test_invalid_paths_and_role_refuse(bad, role):
    with pytest.raises(ValueError, match="ACTIVATION_EXPLICIT_JSON_INPUT_PATH_REQUIRED"):
        read(bad, role=role)


def test_nonexistent_and_directory_input_refused(tmp_path):
    with pytest.raises(ValueError, match="ACTIVATION_ORDINARY_JSON_INPUT"):
        read("missing")
    with pytest.raises(ValueError, match="ACTIVATION_ORDINARY_JSON_INPUT"):
        read(str(tmp_path / "missing.json"))
    with pytest.raises(ValueError, match="ACTIVATION_ORDINARY_JSON_INPUT"):
        read(str(tmp_path))


def test_symlink_input_never_adopted(file, tmp_path):
    source = file()
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(source)
    except OSError as exc:
        pytest.skip(f"Windows symlink privilege unavailable: {type(exc).__name__}")
    with pytest.raises(ValueError, match="ACTIVATION_ORDINARY_JSON_INPUT"):
        read(str(alias))


def test_fstat_mutation_during_open_refuses_even_unchanged_size(file, monkeypatch):
    path = file()
    original = act.os.fstat
    samples = []

    def changed(fd):
        before = original(fd)
        samples.append(before)
        if len(samples) == 1:
            return before
        return SimpleNamespace(
            st_mode=before.st_mode, st_size=before.st_size,
            st_mtime_ns=before.st_mtime_ns + 12345)
    monkeypatch.setattr(act.os, "fstat", changed)
    with pytest.raises(ValueError, match="ACTIVATION_JSON_INPUT_CHANGED_DURING_READ"):
        read(path)
    assert len(samples) == 2


def test_empty_account_docs_cannot_advance_to_activation_clock(
        file, tmp_path, monkeypatch):
    record = file(
        '{"schema":"ATLAS_PERSONAL_ACTIVATION_V1",'
        '"origin":"LOCAL_OPERATOR","origin":"OTHER","actions":["READ_ONLY"]}')
    policy = file('{}', name="policy.json")
    accounts = file('{}', name="accounts.json")
    root = r"D:\AtlasCustody\PersonalPaper\not-created-test-input-admission"
    assert not Path(root).exists()
    monkeypatch.setattr(act, "NativeVersionSafePaperOperatorClock",
                        lambda **kwargs: pytest.fail("MUST_NOT_START_FINANCIAL_CLOCK"))
    monkeypatch.setattr(act, "publish_personal_activation",
                        lambda **kwargs: pytest.fail("MUST_NOT_CREATE_ACTIVATION"))
    with pytest.raises(ValueError, match="ACTIVATION_STRICT_JSON_INPUT_REFUSED:record"):
        act.commission(
            root=root, record_path=record, policy_path=policy,
            release_digest="a" * 64, accounts_path=accounts,
            expected_clock_source=SOURCE, runtime_id="OFFLINE_TEST",
            qd_enrollment_path="missing-qd",
            perp_enrollment_path="missing-perp", clock_profile=PROFILE)
    assert not Path(root).exists()


def test_strict_document_reader_no_execution_or_credential_access(file, monkeypatch):
    path = file('{"status":"NOT_AN_APPROVED_OPERATOR_RECORD"}')
    monkeypatch.setattr(act, "publish_personal_activation",
                        lambda **kwargs: pytest.fail("MUST_NOT_PUBLISH"))
    assert read(path) == {"status": "NOT_AN_APPROVED_OPERATOR_RECORD"}
