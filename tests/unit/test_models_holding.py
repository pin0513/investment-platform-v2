from app.models.holding import Holding


def test_holding_table_columns():
    cols = {c.name for c in Holding.__table__.columns}
    expected = {
        "id",
        "user_id",
        "account_id",
        "instrument_id",
        "quantity",
        "avg_cost",
        "cost_currency",
        "opened_at",
        "last_txn_at",
        "notes",
        "metadata",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected.issubset(cols), expected - cols


def test_holding_unique_account_instrument():
    indexes = {ix.name for ix in Holding.__table__.indexes}
    # SQLAlchemy creates a partial unique index for (account_id, instrument_id)
    # where deleted_at IS NULL. Index name pattern check:
    assert any("account" in n and "instrument" in n for n in indexes)


def test_holding_has_timestamp_mixin():
    cols = {c.name for c in Holding.__table__.columns}
    assert "created_at" in cols
    assert "updated_at" in cols
    assert "deleted_at" in cols
