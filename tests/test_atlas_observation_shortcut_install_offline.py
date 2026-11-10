"""Observation-only desktop shortcut installer must never replace finance links."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
INSTALLER=ROOT/"scripts/windows/Install-AtlasObservationShortcuts.ps1"
START=ROOT/"scripts/windows/Atlas-Observation-Shortcut.ps1"
STOP=ROOT/"scripts/windows/Atlas-Observation-Stop.ps1"


def test_source_only_new_desktop_shortcuts_are_distinct_from_financial_links():
    source=INSTALLER.read_text(encoding="utf-8-sig")
    assert "Atlas Observation (No Trading).lnk" in source
    assert "Stop Atlas Observation (No Trading).lnk" in source
    assert "$shortcut.TargetPath=$powershell" in source
    assert "Atlas-Observation-Shortcut.ps1" in source
    assert "Atlas-Observation-Stop.ps1" in source
    assert "ATLAS_OBSERVATION_SHORTCUTS_EXIST_REFUSE_OVERWRITE" in source
    assert "ATLAS_OBSERVATION_SHORTCUT_EXPLICIT_EXECUTION_REQUIRED" in source
    assert "FINANCIAL_PAPER_AND_LIVE_TRADING_NOT_STARTED" in source
    executable="\n".join(line for line in source.splitlines()
                         if line.strip() and not line.lstrip().startswith("#"))
    for prohibited in ("ATLAS.bat","ATLAS-STOP.bat","Atlas-Stop.ps1",
                       "Atlas-Launch.ps1","docker.exe","Start-Process",
                       "Stop-Process","taskkill","Get-Process","Invoke-RestMethod",
                       "Project Atlas.lnk","Stop Atlas.lnk"):
        assert prohibited.lower() not in executable.lower()
    assert START.is_file() and STOP.is_file()


@pytest.mark.skipif(sys.platform!="win32",reason="Windows PowerShell only")
def test_installer_missing_explicit_permission_never_writes_desktop_shortcuts():
    result=subprocess.run(
        ["powershell.exe","-NoProfile","-NonInteractive",
         "-ExecutionPolicy","Bypass","-File",str(INSTALLER)],
        cwd=ROOT,capture_output=True,text=True,timeout=8,
    )
    assert result.returncode!=0
    assert "ATLAS_OBSERVATION_SHORTCUT_EXPLICIT_EXECUTION_REQUIRED" in result.stderr
