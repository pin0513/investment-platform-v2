from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.instrument import Instrument
from app.repositories.instrument import InstrumentRepository
from app.schemas.instrument import InstrumentCreate


class DuplicateInstrumentError(Exception):
    pass


class InstrumentService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = InstrumentRepository(session)
        self.audit = audit

    def search(
        self,
        q: Optional[str] = None,
        asset_class: Optional[str] = None,
        limit: int = 50,
    ) -> List[Instrument]:
        return self.repo.search(q=q, asset_class=asset_class, limit=limit)

    def get(self, instrument_id: uuid.UUID) -> Optional[Instrument]:
        return self.repo.get_by_id(instrument_id)

    def get_by_symbol(
        self, symbol: str, market: Optional[str] = None
    ) -> Optional[Instrument]:
        return self.repo.get_by_symbol_market(symbol, market)

    def create(self, payload: InstrumentCreate) -> Instrument:
        existing = self.repo.get_by_symbol_market(payload.symbol, payload.market)
        if existing:
            raise DuplicateInstrumentError(
                f"Instrument {payload.symbol} on {payload.market} already exists"
            )

        inst = Instrument(
            id=uuid.uuid4(),
            symbol=payload.symbol,
            asset_class=payload.asset_class,
            name=payload.name,
            currency=payload.currency,
            market=payload.market,
            industry_id=payload.industry_id,
            metadata_json=payload.metadata,
            is_active=True,
        )
        self.repo.create(inst)
        self.audit.record(
            action="INSERT",
            target_table="instruments",
            target_id=inst.id,
            after={
                "symbol": inst.symbol,
                "asset_class": inst.asset_class,
                "currency": inst.currency,
                "market": inst.market,
            },
        )
        return inst
