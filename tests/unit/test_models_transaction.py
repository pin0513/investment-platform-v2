from app.models.transaction import Transaction


def test_transaction_table_columns():
    cols = {c.name for c in Transaction.__table__.columns}
    expected = {
        "id", "user_id", "account_id", "instrument_id", "txn_type",
        "occurred_at", "quantity", "price", "amount", "fee", "tax",
        "currency", "fx_rate_to_base", "counter_account_id", "external_ref",
        "notes", "metadata", "created_at", "reversed_by",
    }
    assert expected.issubset(cols), expected - cols


def test_transaction_user_fk():
    fks = {fk.column.table.name for c in Transaction.__table__.columns for fk in c.foreign_keys}
    assert "users" in fks
    assert "accounts" in fks
    assert "instruments" in fks


def test_transaction_self_referential_reversed_by():
    col = Transaction.__table__.columns["reversed_by"]
    fk = next(iter(col.foreign_keys))
    assert fk.column.table.name == "transactions"
