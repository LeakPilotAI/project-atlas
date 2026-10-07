from pathlib import Path

WINDOWS=Path("docs/WINDOWS.md")
INSTALLER=Path("scripts/windows/Install-DesktopShortcut.ps1")
STOP=Path("scripts/windows/Atlas-Stop.ps1")
LAUNCH=Path("scripts/windows/Atlas-Launch.ps1")
READY=Path("scripts/windows/Atlas-Ready.ps1")

def test_e117_windows_docs_match_two_shortcut_contract():
    docs=WINDOWS.read_text(encoding="utf-8")
    installer=INSTALLER.read_text(encoding="utf-8")
    assert "**Project Atlas** -> `ATLAS.bat`" in docs
    assert "**Stop Atlas** -> `ATLAS-STOP.bat`" in docs
    assert '"Project Atlas.lnk"' in installer
    assert '"Stop Atlas.lnk"' in installer

def test_e117_windows_docs_preserve_other_projects_and_docker():
    docs=WINDOWS.read_text(encoding="utf-8")
    stop=STOP.read_text(encoding="utf-8")
    assert "Docker Desktop and other projects such as Genesis stay running." in docs
    assert "Never quits Docker Desktop or Genesis." in stop

def test_e117_windows_docs_use_scoped_stop_not_generic_process_kill():
    docs=WINDOWS.read_text(encoding="utf-8")
    assert "Atlas-Stop.ps1" in docs
    assert "Get-Process python, node" not in docs
    assert "It does not use generic Python/Node termination as part of normal operation." in docs

def test_e117_windows_docs_keep_environment_backups_distinct():
    docs=WINDOWS.read_text(encoding="utf-8")
    assert "root.env" in docs and "backend.env" in docs
    assert "Copy-Item D:\\Work\\atlas-backup\\root.env .\\.env" in docs
    assert "Copy-Item D:\\Work\\atlas-backup\\backend.env .\\backend\\.env" in docs

def test_e117_windows_docs_preserve_readiness_and_authority_boundaries():
    docs=WINDOWS.read_text(encoding="utf-8")
    launch=LAUNCH.read_text(encoding="utf-8")
    ready=READY.read_text(encoding="utf-8")
    assert "A failed readiness gate is a failed startup, not permission to bypass the gate." in docs
    assert "live-capital permissions" in docs
    assert "Atlas-Ready.ps1" in launch
    assert "launcher-ready.json" in ready
