from app.models.exchange_rate import ExchangeRate


def test_exchange_rate_columns():
    cols = {c.name for c in ExchangeRate.__table__.columns}
    expected = {"base_currency", "quote_currency", "date", "rate", "source"}
    assert expected.issubset(cols)


def test_exchange_rate_pk_is_composite():
    pk = [c.name for c in ExchangeRate.__table__.primary_key.columns]
    assert set(pk) == {"base_currency", "quote_currency", "date"}
