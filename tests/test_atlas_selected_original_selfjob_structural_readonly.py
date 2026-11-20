"""No real Job inside pytest: only pure shape and fail-closed CLI tests."""
import copy
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import (
    atlas_selected_original_selfjob_structural_readonly as observer,
)


def source_roots():
    return {
        "epoch": "QD_PURE_STRUCTURAL_ONLY",
        "roots": {
            role: {
                "path": rf"D:\AtlasPaper\DISPOSABLE_TEST\{role}",
                "native_id": [1, i + 1, 100 + i],
            }
            for i, role in enumerate(
                ("source", "projection", "report", "control", "coordination", "custody")
            )
        },
    }


def source_identity():
    return {
        "pid": 1234,
        "creation_filetime": 1000,
        "image": r"D:\AtlasRuntime\releases\DISPOSABLE\python\python.exe",
    }


@pytest.mark.parametrize("lane,schema,roles", [
    (
        "QUALITY_DIPS", "QD_AUTO_NATIVE_ENROLLMENT_V4",
        ("decision", "source", "projection", "report", "coordination"),
    ),
    (
        "HYPERLIQUID", "PERP_AUTO_NATIVE_ENROLLMENT_V1",
        (
            "decision", "source", "projection", "report", "coordination",
            "funding", "mark",
        ),
    ),
])
def test_only_synthetic_structural_rosters_are_built(lane, schema, roles):
    sources = source_roots()
    frozen = copy.deepcopy(sources)
    result = observer._synthetic_structural_enrollment(
        lane, roles, schema, "a" * 64, sources, source_identity(),
    )
    assert result["schema"] == schema
    assert result["release_digest"] == "a" * 64
    assert result["profile"] == "AUTONOMOUS_PAPER_ONLY_V1"
    assert result["account_id"].startswith("UNENROLLED_STRUCTURAL_")
    assert result["acceptance_id"].startswith("UNACCEPTED_STRUCTURAL_")
    assert set(result["writers"]) == set(roles)
    assert len(result["resources"]) == 6
    assert all(identity["schema"] == "QD_OP_PROCESS_ID_V1"
               for identity in result["writers"].values())
    assert sources == frozen


@pytest.mark.parametrize("tamper", ["duplicate_native_root", "invalid_d_path"])
def test_structural_roster_rejects_invalid_native_root_shapes(tamper):
    roots = source_roots()
    if tamper == "duplicate_native_root":
        roots["roots"]["custody"]["native_id"] = roots["roots"]["control"]["native_id"]
    else:
        roots["roots"]["custody"]["path"] = r"C:\WRONG_ROOT"
    with pytest.raises(ValueError):
        observer._synthetic_structural_enrollment(
            "QUALITY_DIPS",
            ("decision", "source", "projection", "report", "coordination"),
            "QD_AUTO_NATIVE_ENROLLMENT_V4",
            "a" * 64,
            roots,
            source_identity(),
        )


def test_unsafe_import_never_self_assigns_windows_job():
    assert observer.SCHEMA.endswith("READONLY_V1")
    assert callable(observer.run_isolated_readonly)


def test_source_only_job_probe_requires_explicit_isolated_flag():
    with pytest.raises(SystemExit) as caught:
        observer.main([])
    assert caught.value.code == 2


@pytest.mark.skipif(sys.platform != "win32", reason="Exact Windows installed source path check")
def test_unselected_workspace_source_refuses_before_self_job_assignment():
    import inspect

    from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
        RetainedSelectedNativeOwnerPreflight,
    )

    current = Path(inspect.getfile(RetainedSelectedNativeOwnerPreflight)).resolve()
    expected = (
        Path(sys.executable).resolve().parent.parent
        / "scripts/observation_runtime/personal_native_selected_owned_job_preflight.py"
    ).resolve()
    assert current != expected, "TEST MUST IMPORT UNSELECTED SOURCE AND REFUSE"
    with pytest.raises(ValueError, match="ISOLATED_SELECTED_NATIVE"):
        observer.run_isolated_readonly()


@pytest.mark.parametrize("bad", [0, 1, None, "yes", [], {}])
def test_live_peer_check_never_coerces_untrusted_flag_to_enabled(bad):
    with pytest.raises(ValueError, match="EXPLICIT_NTP_CHECK_BOOLEAN"):
        observer.run_isolated_readonly(check_independent_ntp=bad)


def test_in_process_ntp_cannot_borrow_source_from_workspace():
    class Owner:
        def verify_still_running(self):
            raise AssertionError("Unselected path must refuse before Job access")

    # The imported real class comes from workspace, never the selected root.
    with pytest.raises(ValueError, match="SELECTED_NATIVE_CLOCK_AND_JOB"):
        observer._selected_original_job_clock(
            owner=Owner(),
            release=Path("D:/AtlasRuntime/releases/" + "a" * 40),
            release_digest="f" * 64,
        )


def test_ntp_without_explicit_isolated_job_execution_is_refused():
    with pytest.raises(SystemExit) as result:
        observer.main(["--check-independent-ntp"])
    assert result.value.code == 2


@pytest.mark.parametrize("flags", [
    {"verify_ntp_refresh": True},
    {"verify_ntp_refresh": 1, "check_independent_ntp": True},
    {"verify_ntp_refresh": "true", "check_independent_ntp": True},
])
def test_refresh_never_runs_without_explicit_original_two_peer_clock(flags):
    with pytest.raises(ValueError, match="NTP_REFRESH_REQUIRES_NTP_CHECK"):
        observer.run_isolated_readonly(**flags)


def test_cli_refresh_flag_cannot_escape_original_job_preflight():
    with pytest.raises(SystemExit) as result:
        observer.main(["--verify-ntp-refresh", "--check-independent-ntp"])
    assert result.value.code == 2



@pytest.mark.parametrize("kwargs", [
    {"check_alpaca_iex_rest": True},
    {"check_alpaca_iex_rest": 1, "check_independent_ntp": True},
    {"check_alpaca_iex_rest": "true", "check_independent_ntp": True},
])
def test_iex_rest_requires_explicit_original_job_and_native_ntp(kwargs):
    with pytest.raises(ValueError, match="IEX_REQUIRES_ORIGINAL_JOB_NTP_CHECK"):
        observer.run_isolated_readonly(**kwargs)


def test_iex_cli_cannot_escape_isolated_original_job():
    with pytest.raises(SystemExit) as result:
        observer.main(["--check-alpaca-iex-rest", "--check-independent-ntp"])
    assert result.value.code == 2



@pytest.mark.parametrize("reason,expected", [
    ("IEX_NATIVE_HTTP_AUTH_OR_ENTITLEMENT_REFUSED",
     "IEX_NATIVE_HTTP_AUTH_OR_ENTITLEMENT_REFUSED"),
    ("IEX_NATIVE_IEX_EXCHANGE_AND_SHARES_REQUIRED",
     "IEX_NATIVE_IEX_EXCHANGE_AND_SHARES_REQUIRED"),
    ("secret=ALPACA_SECRET_1234",
     "ORIGINAL_NATIVE_BOUNDARY_OR_SOURCE_REFUSED"),
])
def test_selected_native_cli_never_prints_secret_or_raw_provider_error(
    monkeypatch, capsys, reason, expected,
):
    def refuse(**kwargs):
        raise ValueError(reason)
    monkeypatch.setattr(observer, "run_isolated_readonly", refuse)
    assert observer.main(["--execute-isolated-readonly"]) == 2
    output = capsys.readouterr().out
    assert expected in output
    if "secret=" in reason:
        assert reason not in output
    assert '"paper_startup_authorized": false' in output
    assert '"live_trading_authorized": false' in output
