"""Smoke tests: MCP server is mounted at /mcp and JWT-gated.

The FastMCP sub-app uses streamable-http transport with the endpoint at
POST /mcp/ (sub-app path "/" mounted under /mcp in main.py).

Test cases:
  1. POST /mcp/ without Bearer → 401  (McpJwtMiddleware rejects)
  2. POST /mcp/ with valid Bearer JWT → NOT 401 (auth passes; actual status
     may be 4xx for JSON-RPC protocol reasons, but not an auth failure)
"""

import os
import uuid

import pytest

from app.db import session_scope
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def token(client):
    email = f"mcp-{uuid.uuid4().hex[:8]}@x.z"
    user_id = uuid.uuid4()
    slug = f"mcp{uuid.uuid4().hex[:8]}"
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=email,
                slug=slug,
                role="USER",
                password_hash=hash_password("good-password"),
                is_active=True,
            )
        )
    t = client.post(
        "/auth/login",
        json={"email": email, "password": "good-password"},
    ).json()["access_token"]
    yield t
    with session_scope() as s:
        # Delete refresh tokens first to satisfy FK constraint
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def test_mcp_root_unauthorized(client):
    """Without Bearer, the MCP sub-app should return 401."""
    r = client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
    )
    assert r.status_code == 401


def test_mcp_root_with_token_does_not_401(client, token):
    """With Bearer JWT, we get past auth.

    Response may be 4xx for JSON-RPC protocol reasons (e.g. the test client
    doesn't speak MCP's streamable-http framing) but must NOT be 401.
    """
    r = client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code != 401
