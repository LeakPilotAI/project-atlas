from pathlib import Path

COMPOSE = Path("docker-compose.yml")


def _compose():
    return COMPOSE.read_text(encoding="utf-8-sig")


def test_e123_postgres_password_has_no_baked_in_fallback():
    text = _compose()
    assert "atlas_secure_password_2026" not in text
    assert "POSTGRES_PASSWORD: \"${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}\"" in text


def test_e123_compose_requires_external_postgres_password():
    text = _compose()
    line = next(line.strip() for line in text.splitlines() if line.strip().startswith("POSTGRES_PASSWORD:"))
    assert ":-" not in line
    assert ":?" in line
    assert "must be set in .env" in line
