import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.transaction import (
    BatchTransactionCreate,
    TransactionCreate,
    TransactionOut,
)


def test_transaction_create_minimal_buy():
    body = TransactionCreate(
        account_id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        txn_type="BUY",
        occurred_at=datetime(2026, 5, 13, 10, 0, 0),
        quantity=Decimal("100"),
        price=Decimal("635.5"),
        amount=Decimal("63550"),
        currency="TWD",
    )
    assert body.txn_type == "BUY"
    assert body.fee == Decimal("0")
    assert body.tax == Decimal("0")


def test_transaction_create_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        TransactionCreate(
            account_id=uuid.uuid4(),
            instrument_id=uuid.uuid4(),
            txn_type="BUY",
            occurred_at=datetime(2026, 5, 13),
            quantity=Decimal("-10"),
            amount=Decimal("100"),
            currency="USD",
        )


def test_transaction_create_rejects_unknown_type():
    with pytest.raises(ValidationError):
        TransactionCreate(
            account_id=uuid.uuid4(),
            txn_type="GIBBERISH",
            occurred_at=datetime(2026, 5, 13),
            amount=Decimal("100"),
            currency="USD",
        )


def test_transaction_create_cash_no_instrument():
    """DEPOSIT/WITHDRAW for cash-only doesn't require instrument_id."""
    body = TransactionCreate(
        account_id=uuid.uuid4(),
        instrument_id=None,
        txn_type="DEPOSIT",
        occurred_at=datetime(2026, 5, 13),
        amount=Decimal("10000"),
        currency="TWD",
    )
    assert body.instrument_id is None


def test_batch_transaction_create():
    body = BatchTransactionCreate(
        items=[
            TransactionCreate(
                account_id=uuid.uuid4(),
                txn_type="DEPOSIT",
                occurred_at=datetime(2026, 5, 13),
                amount=Decimal("1000"),
                currency="USD",
            )
        ]
    )
    assert len(body.items) == 1


def test_transaction_out_from_orm():
    """ConfigDict(from_attributes=True) lets us build from SQLAlchemy obj."""

    class _Stub:
        id = uuid.uuid4()
        user_id = uuid.uuid4()
        account_id = uuid.uuid4()
        instrument_id = None
        txn_type = "DEPOSIT"
        occurred_at = datetime(2026, 5, 13)
        quantity = None
        price = None
        amount = Decimal("1000")
        fee = Decimal("0")
        tax = Decimal("0")
        currency = "TWD"
        fx_rate_to_base = None
        counter_account_id = None
        external_ref = None
        notes = None
        metadata_json: dict = {}  # noqa: RUF012
        created_at = datetime(2026, 5, 13)
        reversed_by = None

    out = TransactionOut.model_validate(_Stub())
    assert out.txn_type == "DEPOSIT"
    assert out.metadata == {}  # alias from metadata_json
