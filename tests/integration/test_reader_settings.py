import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import create_access_token, hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def auth_user():
    user_id = uuid.uuid4()
    slug = f"st{uuid.uuid4().hex[:8]}"
    email = f"{slug}@x.z"
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=email,
                slug=slug,
                role="USER",
                password_hash=hash_password("pw"),
                is_active=True,
            )
        )
    yield user_id, slug, email
    with session_scope() as s:
        from app.models.refresh_token import RefreshToken

        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(user_id):
    t = create_access_token(subject=str(user_id), email="x@y.z", role="USER", scope="user")
    return {"Authorization": f"Bearer {t}"}


def test_settings_page_shows_user(client, auth_user):
    user_id, slug, email = auth_user
    r = client.get(f"/{slug}/settings", headers=_h(user_id))
    assert r.status_code == 200
    assert email in r.text
    assert slug in r.text
