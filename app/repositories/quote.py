import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quote import Quote


class QuoteRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, instrument_id: uuid.UUID) -> Quote | None:
        return self.s.get(Quote, instrument_id)

    def upsert(self, instrument_id: uuid.UUID, price, as_of, source) -> Quote:
        existing = self.get(instrument_id)
        if existing is None:
            existing = Quote(
                instrument_id=instrument_id,
                price=price,
                as_of=as_of,
                source=source,
            )
            self.s.add(existing)
        else:
            existing.price = price
            existing.as_of = as_of
            existing.source = source
        self.s.flush()
        return existing

    def list_by_instruments(self, instrument_ids: list[uuid.UUID]) -> list[Quote]:
        if not instrument_ids:
            return []
        stmt = select(Quote).where(Quote.instrument_id.in_(instrument_ids))
        return list(self.s.execute(stmt).scalars())
