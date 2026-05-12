import os
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.audit import AuditWriter
from app.db import session_scope
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate
from app.services.transaction import (
    TransactionNotFoundError,
    TransactionService,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def fixture_user_account(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=f"svc-{uuid.uuid4().hex[:8]}@x.z",
                slug=f"svc{uuid.uuid4().hex[:8]}",
                role="USER",
                is_active=True,
            )
        )
        s.flush()
        s.add(
            Account(id=account_id, user_id=user_id, name="A", account_type="BANK", currency="TWD")
        )
    yield user_id, account_id
    with session_scope() as s:
        s.query(Transaction).filter(Transaction.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _audit(s, user_id):
    return AuditWriter(s, request_id=None, actor_user_id=user_id)


def test_create_deposit(fixture_user_account):
    user_id, account_id = fixture_user_account
    with session_scope() as s:
        svc = TransactionService(s, _audit(s, user_id))
        out = svc.create(
            user_id,
            TransactionCreate(
                account_id=account_id,
                txn_type="DEPOSIT",
                occurred_at=datetime(2026, 5, 13),
                amount=Decimal("10000"),
                currency="TWD",
            ),
        )
        assert out.amount == Decimal("10000")


def test_reverse_creates_mirror_row(fixture_user_account):
    user_id, account_id = fixture_user_account
    with session_scope() as s:
        svc = TransactionService(s, _audit(s, user_id))
        original = svc.create(
            user_id,
            TransactionCreate(
                account_id=account_id,
                txn_type="DEPOSIT",
                occurred_at=datetime(2026, 5, 13),
                amount=Decimal("10000"),
                currency="TWD",
            ),
        )
        original_id = original.id

    with session_scope() as s:
        svc = TransactionService(s, _audit(s, user_id))
        svc.reverse(user_id, original_id, reason="wrong account")

    with session_scope() as s:
        rows = s.query(Transaction).filter(Transaction.user_id == user_id).all()
        assert len(rows) == 2
        types = {r.txn_type for r in rows}
        assert types == {"DEPOSIT", "REVERSAL"}
        rev = next(r for r in rows if r.txn_type == "REVERSAL")
        assert rev.reversed_by == original_id
        assert rev.amount == Decimal("10000")
        assert rev.notes == "wrong account"


def test_reverse_other_users_txn_raises(fixture_user_account):
    user_id, account_id = fixture_user_account
    with session_scope() as s:
        svc = TransactionService(s, _audit(s, user_id))
        original = svc.create(
            user_id,
            TransactionCreate(
                account_id=account_id,
                txn_type="DEPOSIT",
                occurred_at=datetime(2026, 5, 13),
                amount=Decimal("10000"),
                currency="TWD",
            ),
        )
        original_id = original.id

    other = uuid.uuid4()
    with session_scope() as s:
        svc = TransactionService(s, _audit(s, other))
        with pytest.raises(TransactionNotFoundError):
            svc.reverse(other, original_id, reason="x")
