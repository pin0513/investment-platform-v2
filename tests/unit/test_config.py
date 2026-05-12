from app.config import Settings


def test_settings_loads_required_fields(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client.apps.googleusercontent.com")

    settings = Settings()

    assert settings.db_url == "postgresql+psycopg://u:p@h/d"
    assert settings.jwt_secret == "a" * 32
    assert settings.google_oauth_client_id == "client.apps.googleusercontent.com"
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_minutes == 15
    assert settings.refresh_token_days == 30


def test_settings_rejects_short_jwt_secret(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("JWT_SECRET", "too-short")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "x")

    import pytest

    with pytest.raises(ValueError):
        Settings()
