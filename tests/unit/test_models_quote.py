from app.models.quote import Quote


def test_quote_columns():
    cols = {c.name for c in Quote.__table__.columns}
    expected = {"instrument_id", "price", "as_of", "source", "updated_at"}
    assert expected.issubset(cols)


def test_quote_pk_is_instrument():
    pk = [c.name for c in Quote.__table__.primary_key.columns]
    assert pk == ["instrument_id"]
