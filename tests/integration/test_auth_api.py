import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def user_with_pw():
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"api-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"api{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        yield u


def test_login_endpoint(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "Bearer"


def test_me_endpoint(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    access = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["email"] == user_with_pw.email


def test_refresh_endpoint(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    refresh = r.json()["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_logout_revokes(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    refresh = r.json()["refresh_token"]

    r = client.post("/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 204

    # Reuse should now fail
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_login_page_renders_html(client):
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    assert "登入" in body
    assert "g_id_onload" in body
    assert "data-client_id" in body  # google oauth client id injected into template
