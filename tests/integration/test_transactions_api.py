import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.account import Account
from app.models.refresh_token import RefreshToken
from app.models.transaction import Transaction
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def auth_setup(client):
    """Returns (access_token, account_id) for a freshly-created user+account."""
    email = f"txnapi-{uuid.uuid4().hex[:8]}@x.z"
    slug = f"txnapi{uuid.uuid4().hex[:8]}"
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=email,
            slug=slug,
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.flush()
        a = Account(
            id=uuid.uuid4(),
            user_id=u.id,
            name="API-Test-Acct",
            account_type="BANK",
            currency="TWD",
        )
        s.add(a)
        user_id = u.id
        account_id = a.id

    token = client.post("/auth/login", json={"email": email, "password": "good-password"}).json()[
        "access_token"
    ]

    yield token, account_id, user_id

    with session_scope() as s:
        s.query(Transaction).filter(Transaction.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_post_transaction_creates_row(client, auth_setup):
    token, account_id, _ = auth_setup
    r = client.post(
        "/api/v1/transactions",
        json={
            "account_id": str(account_id),
            "txn_type": "DEPOSIT",
            "occurred_at": datetime(2026, 5, 13, 10, 0, tzinfo=UTC).isoformat(),
            "amount": "10000",
            "currency": "TWD",
        },
        headers=_h(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["txn_type"] == "DEPOSIT"
    assert Decimal(body["amount"]) == Decimal("10000")


def test_get_transaction(client, auth_setup):
    token, account_id, _ = auth_setup
    txn_id = client.post(
        "/api/v1/transactions",
        json={
            "account_id": str(account_id),
            "txn_type": "DEPOSIT",
            "occurred_at": datetime(2026, 5, 13, tzinfo=UTC).isoformat(),
            "amount": "500",
            "currency": "TWD",
        },
        headers=_h(token),
    ).json()["id"]

    r = client.get(f"/api/v1/transactions/{txn_id}", headers=_h(token))
    assert r.status_code == 200
    assert r.json()["id"] == txn_id


def test_list_transactions(client, auth_setup):
    token, account_id, _ = auth_setup
    for amount in ["100", "200", "300"]:
        client.post(
            "/api/v1/transactions",
            json={
                "account_id": str(account_id),
                "txn_type": "DEPOSIT",
                "occurred_at": datetime(2026, 5, 13, tzinfo=UTC).isoformat(),
                "amount": amount,
                "currency": "TWD",
            },
            headers=_h(token),
        )
    r = client.get("/api/v1/transactions", headers=_h(token))
    assert r.status_code == 200
    assert len(r.json()) >= 3


def test_reverse_transaction(client, auth_setup):
    token, account_id, _ = auth_setup
    txn_id = client.post(
        "/api/v1/transactions",
        json={
            "account_id": str(account_id),
            "txn_type": "DEPOSIT",
            "occurred_at": datetime(2026, 5, 13, tzinfo=UTC).isoformat(),
            "amount": "999",
            "currency": "TWD",
        },
        headers=_h(token),
    ).json()["id"]

    r = client.post(
        f"/api/v1/transactions/{txn_id}/reverse",
        json={"reason": "test reversal"},
        headers=_h(token),
    )
    assert r.status_code == 201
    rev = r.json()
    assert rev["txn_type"] == "REVERSAL"
    assert rev["reversed_by"] == txn_id


def test_batch_transactions(client, auth_setup):
    token, account_id, _ = auth_setup
    r = client.post(
        "/api/v1/transactions/batch",
        json={
            "items": [
                {
                    "account_id": str(account_id),
                    "txn_type": "DEPOSIT",
                    "occurred_at": datetime(2026, 5, 13, tzinfo=UTC).isoformat(),
                    "amount": "111",
                    "currency": "TWD",
                },
                {
                    "account_id": str(account_id),
                    "txn_type": "DEPOSIT",
                    "occurred_at": datetime(2026, 5, 14, tzinfo=UTC).isoformat(),
                    "amount": "222",
                    "currency": "TWD",
                },
            ]
        },
        headers=_h(token),
    )
    assert r.status_code == 201
    assert len(r.json()) == 2


def test_unauthorized_returns_401(client):
    r = client.get("/api/v1/transactions")
    assert r.status_code == 401
