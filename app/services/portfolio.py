from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date as date_t, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.account import Account
from app.models.instrument import Instrument
from app.repositories.holding import HoldingRepository
from app.repositories.quote import QuoteRepository
from app.schemas.portfolio import (
    GroupValue,
    HoldingValuation,
    PortfolioSummary,
)
from app.services.exchange_rate import ExchangeRateService

STALE_THRESHOLD_DAYS = 7


class PortfolioService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.holdings = HoldingRepository(session)
        self.quotes = QuoteRepository(session)
        self.fx = ExchangeRateService(session, audit)
        self.audit = audit

    def summary(self, user_id: uuid.UUID, base_ccy: str) -> PortfolioSummary:
        base_ccy = base_ccy.upper()
        now = datetime.now(UTC)
        today = now.date()

        holdings = self.holdings.list_for_user(user_id)
        if not holdings:
            return PortfolioSummary(
                base_currency=base_ccy, total_value=Decimal("0"), as_of=now,
                by_asset_class=[], by_account=[], by_industry=[],
                holdings=[], stale_count=0,
            )

        instrument_ids = [h.instrument_id for h in holdings]
        instruments_map = {
            i.id: i for i in self.s.execute(
                select(Instrument).where(Instrument.id.in_(instrument_ids))
            ).scalars()
        }
        account_ids = list({h.account_id for h in holdings})
        accounts_map = {
            a.id: a for a in self.s.execute(
                select(Account).where(Account.id.in_(account_ids))
            ).scalars()
        }
        quotes_map = {
            q.instrument_id: q
            for q in self.quotes.list_by_instruments(instrument_ids)
        }

        valuations: list[HoldingValuation] = []
        for h in holdings:
            inst = instruments_map.get(h.instrument_id)
            acc = accounts_map.get(h.account_id)
            if inst is None or acc is None:
                continue

            q = quotes_map.get(h.instrument_id)
            if q is not None:
                age_days = (now - q.as_of).days
                stale = age_days > STALE_THRESHOLD_DAYS
                last_price = q.price
            else:
                stale = True
                last_price = h.avg_cost

            value_in_native = (h.quantity * last_price) if last_price is not None else None

            fx_rate = self.fx.get_rate(inst.currency, base_ccy, today)
            if value_in_native is not None and fx_rate is not None:
                value_in_base = (value_in_native * fx_rate).quantize(Decimal("0.0001"))
            else:
                value_in_base = None

            if value_in_base is not None and h.avg_cost is not None and last_price is not None:
                cost_native = h.quantity * h.avg_cost
                cost_base_rate = fx_rate or Decimal("1")
                cost_in_base = (cost_native * cost_base_rate).quantize(Decimal("0.0001"))
                unrealized = (value_in_base - cost_in_base).quantize(Decimal("0.0001"))
            else:
                unrealized = None

            valuations.append(HoldingValuation(
                account_id=acc.id, account_name=acc.name,
                instrument_id=inst.id, symbol=inst.symbol,
                instrument_name=inst.name, asset_class=inst.asset_class,
                industry_id=inst.industry_id, currency=inst.currency,
                quantity=h.quantity, avg_cost=h.avg_cost,
                last_price=last_price, value_in_native=value_in_native,
                value_in_base=value_in_base,
                unrealized_pnl_in_base=unrealized,
                stale=stale,
            ))

        total = sum(
            (v.value_in_base for v in valuations if v.value_in_base is not None),
            Decimal("0"),
        )
        stale_count = sum(1 for v in valuations if v.stale)

        def _group(key_fn) -> list[GroupValue]:
            agg: dict[str, dict] = defaultdict(lambda: {"value": Decimal("0"), "count": 0})
            for v in valuations:
                if v.value_in_base is None:
                    continue
                key = key_fn(v)
                agg[key]["value"] += v.value_in_base
                agg[key]["count"] += 1
            groups = []
            for label, data in agg.items():
                pct = float(data["value"] / total * 100) if total > 0 else 0.0
                groups.append(GroupValue(
                    label=label, value=data["value"], pct=round(pct, 2),
                    count=data["count"],
                ))
            return sorted(groups, key=lambda g: g.value, reverse=True)

        by_class = _group(lambda v: v.asset_class)
        by_account = _group(lambda v: v.account_name)
        by_industry = _group(lambda v: str(v.industry_id) if v.industry_id else "UNCLASSIFIED")

        return PortfolioSummary(
            base_currency=base_ccy,
            total_value=total,
            as_of=now,
            by_asset_class=by_class,
            by_account=by_account,
            by_industry=by_industry,
            holdings=valuations,
            stale_count=stale_count,
        )
