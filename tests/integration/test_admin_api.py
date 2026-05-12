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
def admin_token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"admin-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"admin{uuid.uuid4().hex[:8]}",
            role="ADMIN",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email
    return client.post("/auth/login", json={"email": email, "password": "good-password"}).json()[
        "access_token"
    ]


@pytest.fixture
def user_token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"u-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"u{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email
    return client.post("/auth/login", json={"email": email, "password": "good-password"}).json()[
        "access_token"
    ]


def test_admin_invite(client, admin_token):
    r = client.post(
        "/api/v1/admin/invite",
        json={"email": f"new-{uuid.uuid4().hex[:8]}@x.z"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "invited"


def test_invite_requires_admin(client, user_token):
    r = client.post(
        "/api/v1/admin/invite",
        json={"email": "x@y.z"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 403


def test_mint_service_token(client, admin_token):
    r = client.post(
        "/api/v1/admin/service-tokens",
        json={"name": "scheduler-test", "expires_in_minutes": 60},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["name"] == "scheduler-test"
