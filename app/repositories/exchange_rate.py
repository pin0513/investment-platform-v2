from datetime import date as date_t
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate


class ExchangeRateRepository:
    def __init__(self, session: Session):
        self.s = session

    def get(self, base: str, quote: str, on_date: date_t) -> ExchangeRate | None:
        return self.s.get(ExchangeRate, (base, quote, on_date))

    def latest_at_or_before(self, base: str, quote: str, on_date: date_t) -> ExchangeRate | None:
        stmt = (
            select(ExchangeRate)
            .where(
                ExchangeRate.base_currency == base,
                ExchangeRate.quote_currency == quote,
                ExchangeRate.date <= on_date,
            )
            .order_by(ExchangeRate.date.desc())
            .limit(1)
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def upsert(
        self, base: str, quote: str, on_date: date_t, rate: Decimal, source: str
    ) -> ExchangeRate:
        existing = self.get(base, quote, on_date)
        if existing is None:
            existing = ExchangeRate(
                base_currency=base,
                quote_currency=quote,
                date=on_date,
                rate=rate,
                source=source,
            )
            self.s.add(existing)
        else:
            existing.rate = rate
            existing.source = source
        self.s.flush()
        return existing
