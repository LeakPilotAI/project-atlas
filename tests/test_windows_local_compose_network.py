"""Compose configuration only: never inspect, connect to, or start containers."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
EXPECTED = {"postgres": 5432, "redis": 6379}


@pytest.mark.parametrize("service,port", EXPECTED.items())
def test_source_ports_explicit_ipv4_loopback_without_interpolation(service, port):
    source = yaml.safe_load(COMPOSE.read_text(encoding="utf-8-sig"))
    assert source["services"][service]["ports"] == [f"127.0.0.1:{port}:{port}"]
    assert source["services"][service].get("network_mode") != "host"


def test_only_reviewed_compose_file_and_owned_resources():
    candidates = {p.name for p in ROOT.iterdir() if p.is_file()
                  and "compose" in p.name.casefold() and p.suffix.casefold() in {".yml", ".yaml"}}
    assert candidates == {"docker-compose.yml"}, "Review any new Compose file/automatic override before use"
    source = yaml.safe_load(COMPOSE.read_text(encoding="utf-8-sig"))
    assert set(source) == {"services", "volumes"}  # No implicit include or external-network adoption.
    assert set(source["services"]) == set(EXPECTED)
    assert set(source["volumes"]) == {"atlas_pgdata", "atlas_redis"}
    for service in EXPECTED:
        assert source["services"][service]["container_name"] == f"atlas-{service}"
        assert "extends" not in source["services"][service]


@pytest.fixture(scope="module")
def resolved(tmp_path_factory):
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("NOT EXECUTED: Docker Compose CLI unavailable; no fallback acceptance")
    empty_env = tmp_path_factory.mktemp("compose-config-only") / "empty.env"
    empty_env.write_bytes(b"")
    # Exclude inherited credentials, selectors and .env. Only synthetic database
    # values are resolved; config --format json does not contact Docker Engine.
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE",
        "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA"}}
    env.update(POSTGRES_USER="atlas_syntax_fixture", POSTGRES_DB="atlas_syntax_fixture",
               POSTGRES_PASSWORD="SYNTHETIC_CONFIG_ONLY_NOT_A_CREDENTIAL", COMPOSE_DISABLE_ENV_FILE="1")
    result = subprocess.run([docker, "compose", "--project-name", "atlas", "--project-directory", str(ROOT),
                             "--env-file", str(empty_env), "--file", str(COMPOSE), "config", "--format", "json"],
                            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
    assert result.returncode == 0, "Compose config-only validation failed: " + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("service,port", EXPECTED.items())
def test_resolved_ports_never_default_to_wildcard(resolved, service, port):
    ports = resolved["services"][service]["ports"]
    assert len(ports) == 1
    assert ports[0]["host_ip"] == "127.0.0.1"
    assert str(ports[0]["published"]) == str(port)
    assert ports[0]["target"] == port
    assert ports[0]["protocol"] == "tcp"


def test_resolved_configuration_preserves_local_ownership(resolved):
    assert set(resolved["services"]) == set(EXPECTED)
    assert set(resolved["volumes"]) == {"atlas_pgdata", "atlas_redis"}
    assert resolved["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"] == "SYNTHETIC_CONFIG_ONLY_NOT_A_CREDENTIAL"
    for service in EXPECTED:
        assert resolved["services"][service]["container_name"] == f"atlas-{service}"
        assert resolved["services"][service].get("network_mode") != "host"
        assert all(port["host_ip"] == "127.0.0.1" for port in resolved["services"][service]["ports"])


def test_local_policy_and_manager_select_explicit_atlas_compose():
    policy = json.loads((ROOT / "docs/ATLAS_DEPLOYMENT_POLICY.json").read_text())
    assert policy["deployment"] == "SINGLE_USER_WINDOWS_LOCAL"
    assert policy["paper_startup_authorized"] is False
    manager = (ROOT / "scripts/windows/Atlas-Background.ps1").read_text()
    assert '$ComposePath = Join-Path $Root "docker-compose.yml"' in manager
    assert "docker compose --project-name atlas --file $ComposePath" in manager
