import uuid

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.quote import Quote
from app.repositories.instrument import InstrumentRepository
from app.repositories.quote import QuoteRepository
from app.schemas.quote import QuoteUpsert


class InstrumentNotFoundError(Exception):
    pass


class QuoteService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = QuoteRepository(session)
        self.instruments = InstrumentRepository(session)
        self.audit = audit

    def upsert_by_symbol(
        self, symbol: str, market: str | None, payload: QuoteUpsert
    ) -> Quote:
        inst = self.instruments.get_by_symbol_market(symbol, market)
        if inst is None:
            raise InstrumentNotFoundError(f"{symbol} ({market})")
        q = self.repo.upsert(
            instrument_id=inst.id,
            price=payload.price,
            as_of=payload.as_of,
            source=payload.source,
        )
        self.audit.record(
            action="UPSERT",
            target_table="quotes",
            target_id=inst.id,
            after={"price": str(payload.price), "as_of": payload.as_of.isoformat()},
        )
        return q

    def get_by_symbol(self, symbol: str, market: str | None) -> Quote | None:
        inst = self.instruments.get_by_symbol_market(symbol, market)
        if inst is None:
            return None
        return self.repo.get(inst.id)
