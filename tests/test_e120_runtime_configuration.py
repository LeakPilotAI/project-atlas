from pathlib import Path

import pytest

from app.core.config import Settings

MAIN = Path("backend/app/main.py")
EXAMPLE = Path(".env.example")

def _settings(**overrides):
    values = {
        "secret_key": "local-test-secret-not-placeholder",
        "database_url": "postgresql+asyncpg://atlas:local-test-db-pass@localhost:5432/atlas",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)

def test_e120_valid_local_runtime_configuration_is_accepted():
    _settings().validate_runtime_configuration()

@pytest.mark.parametrize("secret", ["", "change-me", "change-me-in-production"])
def test_e120_placeholder_secret_is_rejected(secret):
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _settings(secret_key=secret).validate_runtime_configuration()

@pytest.mark.parametrize("database", [
    "postgresql+asyncpg://atlas:change-me@localhost:5432/atlas",
    "postgresql+asyncpg://atlas:atlas_secure_password_2026@localhost:5432/atlas",
])
def test_e120_placeholder_database_credentials_are_rejected(database):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _settings(database_url=database).validate_runtime_configuration()

def test_e120_optional_alert_integrations_may_remain_unconfigured():
    _settings(discord_token="", discord_channel_id="", telegram_token="", telegram_chat_id="").validate_runtime_configuration()

def test_e120_backend_lifespan_validates_before_runtime_services():
    text = MAIN.read_text(encoding="utf-8")
    assert "settings.validate_runtime_configuration()" in text
    assert text.index("settings.validate_runtime_configuration()") < text.index("await get_redis_client()")

def test_e120_example_file_keeps_explicit_placeholders_not_real_secrets():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "SECRET_KEY=change-me-in-production" in text
    assert "POSTGRES_PASSWORD=change-me" in text
    assert "DATABASE_URL=postgresql+asyncpg://atlas:change-me@localhost:5432/atlas" in text
