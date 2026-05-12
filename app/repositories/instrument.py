from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.instrument import Instrument


class InstrumentRepository:
    def __init__(self, session: Session):
        self.s = session

    def search(
        self,
        q: Optional[str] = None,
        asset_class: Optional[str] = None,
        limit: int = 50,
    ) -> list[Instrument]:
        stmt = select(Instrument).where(Instrument.is_active.is_(True))
        if asset_class:
            stmt = stmt.where(Instrument.asset_class == asset_class)
        if q:
            like = f"%{q.upper()}%"
            stmt = stmt.where((Instrument.symbol.ilike(like)) | (Instrument.name.ilike(like)))
        stmt = stmt.limit(limit)
        return list(self.s.execute(stmt).scalars())

    def get_by_symbol_market(self, symbol: str, market: Optional[str]) -> Optional[Instrument]:
        stmt = select(Instrument).where(Instrument.symbol == symbol)
        if market is not None:
            stmt = stmt.where(Instrument.market == market)
        return self.s.execute(stmt).scalar_one_or_none()

    def get_by_id(self, instrument_id: uuid.UUID) -> Optional[Instrument]:
        return self.s.get(Instrument, instrument_id)

    def create(self, inst: Instrument) -> Instrument:
        self.s.add(inst)
        self.s.flush()
        return inst
