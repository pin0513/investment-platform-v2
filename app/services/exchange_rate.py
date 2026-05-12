from datetime import date as date_t
from decimal import Decimal

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.exchange_rate import ExchangeRate
from app.repositories.exchange_rate import ExchangeRateRepository


class ExchangeRateService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = ExchangeRateRepository(session)
        self.audit = audit

    def upsert(
        self, base: str, quote: str, on_date: date_t, rate: Decimal, source: str
    ) -> ExchangeRate:
        if base == quote:
            raise ValueError("base and quote currencies must differ")
        if len(base) != 3 or len(quote) != 3:
            raise ValueError("currency codes must be ISO 4217 (3 letters)")
        r = self.repo.upsert(base.upper(), quote.upper(), on_date, rate, source)
        self.audit.record(
            action="UPSERT",
            target_table="exchange_rates",
            after={
                "base": base,
                "quote": quote,
                "date": on_date.isoformat(),
                "rate": str(rate),
            },
        )
        return r

    def get_rate(self, base: str, quote: str, on_date: date_t) -> Decimal | None:
        if base == quote:
            return Decimal("1")
        direct = self.repo.latest_at_or_before(base.upper(), quote.upper(), on_date)
        if direct is not None:
            return direct.rate
        # Try inverse
        inverse = self.repo.latest_at_or_before(quote.upper(), base.upper(), on_date)
        if inverse is not None and inverse.rate > 0:
            return Decimal("1") / inverse.rate
        return None
