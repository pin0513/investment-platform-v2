import os
import uuid

import pytest

from app.db import session_scope
from app.models.instrument import Instrument
from app.models.user import User
from app.security import create_access_token, hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def auth_user_with_instrument():
    user_id = uuid.uuid4()
    slug = f"inst{uuid.uuid4().hex[:8]}"
    sym = f"RDR{uuid.uuid4().hex[:6].upper()}"
    inst_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=f"{slug}@x.z",
                slug=slug,
                role="USER",
                password_hash=hash_password("pw"),
                is_active=True,
            )
        )
        s.add(
            Instrument(
                id=inst_id,
                symbol=sym,
                asset_class="EQUITY",
                currency="USD",
                market="NASDAQ",
                name="Test Co.",
            )
        )
    yield user_id, slug, sym, inst_id
    with session_scope() as s:
        from app.models.refresh_token import RefreshToken

        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(Instrument).filter(Instrument.id == inst_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(user_id):
    t = create_access_token(subject=str(user_id), email="x@y.z", role="USER", scope="user")
    return {"Authorization": f"Bearer {t}"}


def test_instrument_detail_renders(client, auth_user_with_instrument):
    user_id, slug, sym, _ = auth_user_with_instrument
    r = client.get(f"/{slug}/instruments/{sym}", headers=_h(user_id))
    assert r.status_code == 200
    assert sym in r.text
    assert "Test Co." in r.text


def test_instrument_detail_unknown_returns_404(client, auth_user_with_instrument):
    user_id, slug, _, _ = auth_user_with_instrument
    r = client.get(f"/{slug}/instruments/NOSUCH", headers=_h(user_id))
    assert r.status_code == 404
