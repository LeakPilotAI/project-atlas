from pathlib import Path

COMPOSE = Path("docker-compose.yml")
LAUNCH = Path("scripts/windows/Atlas-Launch.ps1")


def _compose():
    return COMPOSE.read_text(encoding="utf-8-sig")


def _launch():
    return LAUNCH.read_text(encoding="utf-8-sig")


def test_e124_dependency_images_are_digest_pinned():
    text = _compose()
    assert "timescale/timescaledb@sha256:" in text
    assert "redis@sha256:" in text
    assert "latest-pg16" not in text
    assert "redis:7-alpine" not in text


def test_e124_postgres_healthcheck_uses_configured_database_identity():
    text = _compose()
    assert 'pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB' in text
    assert "pg_isready -U atlas" not in text


def test_e124_named_persistent_volumes_remain_owned():
    text = _compose()
    assert "atlas_pgdata:/var/lib/postgresql/data" in text
    assert "atlas_redis:/data" in text
    assert "\nvolumes:\n  atlas_pgdata:\n  atlas_redis:" in text


def test_e124_launcher_does_not_destroy_dependencies_before_start():
    text = _launch()
    assert "docker rm -f atlas-postgres atlas-redis" not in text
    assert "docker compose down --remove-orphans" not in text
    assert "docker compose up -d --no-recreate postgres redis" in text


def test_e124_localhost_runtime_ports_remain_stable():
    text = _compose()
    assert '"5432:5432"' in text
    assert '"6379:6379"' in text
