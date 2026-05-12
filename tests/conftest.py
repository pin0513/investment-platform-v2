import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    os.environ.setdefault("DB_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    os.environ.setdefault("JWT_SECRET", "x" * 64)
    os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test.apps.googleusercontent.com")
    os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
