import os
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.transaction import TransactionRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def fixture_user_account(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    with session_scope() as s:
        u = User(
            id=user_id,
            email=f"txnrepo-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"txnrepo{uuid.uuid4().hex[:8]}",
            role="USER",
            is_active=True,
        )
        s.add(u)
        s.flush()
        a = Account(
            id=account_id,
            user_id=user_id,
            name="TestAcct",
            account_type="BROKER_STOCK",
            currency="TWD",
        )
        s.add(a)
    yield user_id, account_id
    with session_scope() as s:
        s.query(Transaction).filter(Transaction.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def test_create_and_fetch_transaction(fixture_user_account):
    user_id, account_id = fixture_user_account
    with session_scope() as s:
        repo = TransactionRepository(s)
        t = repo.create(
            Transaction(
                user_id=user_id,
                account_id=account_id,
                txn_type="DEPOSIT",
                occurred_at=datetime(2026, 5, 13),
                amount=Decimal("10000"),
                currency="TWD",
            )
        )
        txn_id = t.id

    with session_scope() as s:
        repo = TransactionRepository(s)
        fetched = repo.get_for_user(user_id, txn_id)
        assert fetched is not None
        assert fetched.txn_type == "DEPOSIT"
        assert fetched.amount == Decimal("10000")


def test_list_filters_by_account_and_dates(fixture_user_account):
    user_id, account_id = fixture_user_account
    with session_scope() as s:
        repo = TransactionRepository(s)
        for i, day in enumerate([1, 5, 10, 15, 20]):
            repo.create(
                Transaction(
                    user_id=user_id,
                    account_id=account_id,
                    txn_type="DEPOSIT",
                    occurred_at=datetime(2026, 5, day),
                    amount=Decimal(f"{100 + i}"),
                    currency="TWD",
                )
            )

    with session_scope() as s:
        repo = TransactionRepository(s)
        rows = repo.list_for_user(
            user_id,
            account_id=account_id,
            from_=datetime(2026, 5, 4),
            to=datetime(2026, 5, 16),
        )
        assert len(rows) == 3  # days 5, 10, 15


def test_get_for_user_rejects_other_users_txn(fixture_user_account):
    user_id, account_id = fixture_user_account
    with session_scope() as s:
        repo = TransactionRepository(s)
        t = repo.create(
            Transaction(
                user_id=user_id,
                account_id=account_id,
                txn_type="DEPOSIT",
                occurred_at=datetime(2026, 5, 13),
                amount=Decimal("10000"),
                currency="TWD",
            )
        )
        txn_id = t.id

    other_user = uuid.uuid4()
    with session_scope() as s:
        repo = TransactionRepository(s)
        assert repo.get_for_user(other_user, txn_id) is None
