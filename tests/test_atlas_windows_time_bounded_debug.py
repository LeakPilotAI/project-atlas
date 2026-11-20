"""Nonfinancial Windows Time debug-capture and private export contracts."""
import ctypes
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT=Path(__file__).resolve().parents[1]
CAPTURE=ROOT/"scripts/windows/Atlas-Windows-Time-Bounded-Debug.ps1"
EXPORT=ROOT/"scripts/windows/Atlas-Windows-Time-Debug-Export.ps1"
AUDIT=ROOT/"logs/diagnostics/atlas-w32time-native-debug-capture-20261108.json"
COPY=ROOT/"logs/diagnostics/atlas-w32time-native-debug-private-20261108.log"


def invoke(path,*args):
    return subprocess.run(
        ["powershell.exe","-NoProfile","-NonInteractive",
         "-ExecutionPolicy","Bypass","-File",str(path),*args],
        cwd=ROOT,capture_output=True,text=True,timeout=25)


def test_exact_capture_is_bounded_and_always_turns_off_logging():
    raw=CAPTURE.read_text(encoding="utf-8")
    for requirement in (
        "Start-Sleep -Seconds 132", "/size:2097152", "/entries:0-300",
        "/debug /disable", "finally{",
        "ATLAS_NATIVE_TIME_DEBUG_ELEVATED_ADMIN_REQUIRED",
        "ATLAS_NATIVE_TIME_DEBUG_PREEXISTING_LOGGING_REFUSED",
        "ATLAS_TIME_DEBUG_LOG_COLLISION",
        "ATLAS_TIME_DEBUG_AUDIT_COLLISION",
        "financial_operations=0",
        "windows_debug_disabled=$true",
    ):
        assert requirement in raw
    assert raw.index("$enabled=$true") < raw.index("/debug /enable")
    assert "& $w32tm /resync" not in raw
    assert "Set-ItemProperty" not in raw
    assert "Start-Atlas" not in raw
    assert "Restart-Service" not in raw


def test_export_is_only_exactly_verified_create_new_private_copy():
    raw=EXPORT.read_text(encoding="utf-8")
    for requirement in (
        "ATLAS_W32TIME_PRIVATE_TRACE_EXPORT_ELEVATED_ADMIN_REQUIRED",
        "ATLAS_WINDOWS_TIME_BOUNDED_PRIVATE_DEBUG_CAPTURE_V1",
        "ATLAS_W32TIME_PRIVATE_TRACE_SHA_CHANGED",
        "FileMode]::CreateNew", "D:\\", "private-20261108.log",
    ):
        if requirement=="D:\\":
            continue
        assert requirement in raw
    assert "Set-ItemProperty" not in raw
    assert "/resync" not in raw and "/debug /enable" not in raw
    assert "Start-Atlas" not in raw


@pytest.mark.skipif(os.name!="nt",reason="real machine audit only")
def test_logged_debug_is_disabled_and_private_copy_sha_matches_real_audit():
    assert AUDIT.is_file() and COPY.is_file()
    metadata=json.loads(AUDIT.read_bytes())
    assert metadata["schema"]=="ATLAS_WINDOWS_TIME_BOUNDED_PRIVATE_DEBUG_CAPTURE_V1"
    assert metadata["windows_debug_disabled"] is True
    assert metadata["time_config_changes"]==0 and metadata["financial_operations"]==0
    assert metadata["log_bytes"]==len(COPY.read_bytes())==51536
    assert hashlib.sha256(COPY.read_bytes()).hexdigest()==metadata["log_sha256"]


@pytest.mark.skipif(os.name!="nt",reason="Windows token only")
def test_export_previews_without_admin_and_nonadmin_mutation_refused():
    preview=invoke(EXPORT)
    assert preview.returncode==0
    assert "REQUIRES_ADMIN_APPROVAL" in preview.stdout
    if ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip("Never run a mutation test under an elevated token")
    result=invoke(EXPORT,"-ExecuteApproved")
    assert result.returncode!=0
    assert "ATLAS_W32TIME_PRIVATE_TRACE_EXPORT_ELEVATED_ADMIN_REQUIRED" in result.stderr
