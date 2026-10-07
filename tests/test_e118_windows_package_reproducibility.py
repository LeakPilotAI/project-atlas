from pathlib import Path

SETUP=Path("scripts/windows/Fresh-Setup.ps1")
PACKAGE=Path("frontend/package.json")
LOCK=Path("frontend/package-lock.json")
PYPROJECT=Path("backend/pyproject.toml")
COMPOSE=Path("docker-compose.yml")

def test_e118_fresh_setup_uses_committed_frontend_lock():
    text=SETUP.read_text(encoding="utf-8")
    assert 'Test-Path (Join-Path $Frontend "package-lock.json")' in text
    assert "& npm.cmd ci" in text
    assert "& npm.cmd install" not in text

def test_e118_fresh_setup_fails_closed_if_locked_install_fails():
    text=SETUP.read_text(encoding="utf-8")
    assert "refusing non-deterministic frontend install" in text
    assert "npm ci failed; committed frontend dependency lock is not installable." in text
    assert "exit $LASTEXITCODE" in text

def test_e118_frontend_manifest_and_lock_are_tracked_contracts():
    package=PACKAGE.read_text(encoding="utf-8")
    lock=LOCK.read_text(encoding="utf-8")
    assert '"next": "16.4.0"' in package
    assert '"lockfileVersion"' in lock

def test_e118_backend_setup_still_uses_tracked_pyproject():
    setup=SETUP.read_text(encoding="utf-8")
    pyproject=PYPROJECT.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in setup
    assert 'requires-python = ">=3.12"' in pyproject
    assert '"fastapi>=0.115.0"' in pyproject

def test_e118_local_runtime_topology_remains_postgres_redis_only():
    compose=COMPOSE.read_text(encoding="utf-8")
    assert "atlas-postgres" in compose and "atlas-redis" in compose
    assert "# Backend will be added later once the FastAPI app is ready" in compose
