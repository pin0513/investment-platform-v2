from app.models.account import Account
from app.models.industry import Industry
from app.models.instrument import Instrument


def test_industry_columns():
    cols = {c.name for c in Industry.__table__.columns}
    assert {"id", "code", "name_zh", "name_en", "market_group"}.issubset(cols)


def test_instrument_unique_symbol_market():
    constraints = {c.name for c in Instrument.__table__.constraints if c.name}
    assert any("symbol" in name and "market" in name for name in constraints)


def test_account_belongs_to_user():
    fks = {fk.column.table.name for c in Account.__table__.columns for fk in c.foreign_keys}
    assert "users" in fks
