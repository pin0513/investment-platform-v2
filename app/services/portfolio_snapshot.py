from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.account import Account
from app.models.instrument import Instrument
from app.models.portfolio_snapshot import HoldingSnapshot, PortfolioSnapshot
from app.schemas.portfolio import HoldingSnapshotCreate, PortfolioSnapshotCreate
from app.services.exchange_rate import ExchangeRateService
from app.services.portfolio import PortfolioService

VALUATION_QUANT = Decimal("0.0001")


class PortfolioSnapshotError(Exception):
    pass


class PortfolioSnapshotService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.audit = audit
        self.fx = ExchangeRateService(session, audit)

    def list(
        self,
        user_id: uuid.UUID,
        *,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 200,
    ) -> list[PortfolioSnapshot]:
        stmt = select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == user_id)
        if from_ is not None:
            stmt = stmt.where(PortfolioSnapshot.as_of >= from_)
        if to is not None:
            stmt = stmt.where(PortfolioSnapshot.as_of <= to)
        stmt = stmt.order_by(
            PortfolioSnapshot.as_of.desc(), PortfolioSnapshot.created_at.desc()
        ).limit(limit)
        return list(self.s.execute(stmt).scalars())

    def latest(self, user_id: uuid.UUID) -> PortfolioSnapshot | None:
        stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(PortfolioSnapshot.as_of.desc(), PortfolioSnapshot.created_at.desc())
            .limit(1)
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def get(self, user_id: uuid.UUID, snapshot_id: uuid.UUID) -> PortfolioSnapshot | None:
        stmt = select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.id == snapshot_id,
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def holdings_for_snapshot(
        self, user_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> list[HoldingSnapshot]:
        stmt = (
            select(HoldingSnapshot)
            .where(
                HoldingSnapshot.user_id == user_id,
                HoldingSnapshot.snapshot_id == snapshot_id,
            )
            .order_by(HoldingSnapshot.market_value_base.desc().nullslast(), HoldingSnapshot.symbol)
        )
        return list(self.s.execute(stmt).scalars())

    def create_from_current(
        self,
        user_id: uuid.UUID,
        *,
        base_currency: str,
        source: str = "DB_SNAPSHOT",
        source_status: str = "OK",
        source_message: str | None = None,
        as_of: datetime | None = None,
    ) -> tuple[PortfolioSnapshot, list[HoldingSnapshot]]:
        summary = PortfolioService(self.s, self.audit).summary(user_id, base_currency.upper())
        snapshot_as_of = as_of or summary.data_as_of or summary.as_of
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            as_of=snapshot_as_of,
            base_currency=summary.base_currency,
            total_value=summary.total_value,
            source=source,
            source_status=source_status,
            source_message=source_message or summary.data_notice,
            metadata_json={
                "stale_count": summary.stale_count,
                "group_count": {
                    "asset_class": len(summary.by_asset_class),
                    "account": len(summary.by_account),
                    "industry": len(summary.by_industry),
                },
            },
        )
        self.s.add(snapshot)
        self.s.flush()

        rows: list[HoldingSnapshot] = []
        for item in summary.holdings:
            row = HoldingSnapshot(
                snapshot_id=snapshot.id,
                user_id=user_id,
                account_id=item.account_id,
                account_name=item.account_name,
                instrument_id=item.instrument_id,
                symbol=item.symbol,
                instrument_name=item.instrument_name,
                asset_class=item.asset_class,
                industry_id=item.industry_id,
                currency=item.currency.upper(),
                quantity=item.quantity,
                avg_cost=item.avg_cost,
                last_price=item.last_price,
                market_value_native=item.value_in_native,
                market_value_base=item.value_in_base,
                metadata_json={"stale": item.stale},
            )
            self.s.add(row)
            rows.append(row)

        self._audit_snapshot(snapshot, len(rows))
        return snapshot, rows

    def import_snapshot(
        self, user_id: uuid.UUID, payload: PortfolioSnapshotCreate, default_base_currency: str
    ) -> tuple[PortfolioSnapshot, list[HoldingSnapshot]]:
        as_of = payload.as_of or datetime.now(UTC)
        base_currency = (payload.base_currency or default_base_currency).upper()
        account_ids = {item.account_id for item in payload.holdings}
        instrument_ids = {item.instrument_id for item in payload.holdings}

        accounts = self._load_accounts(user_id, account_ids)
        instruments = self._load_instruments(instrument_ids)
        rows = [
            self._build_import_holding(
                user_id,
                item,
                account=accounts[item.account_id],
                instrument=instruments[item.instrument_id],
                base_currency=base_currency,
                as_of=as_of,
            )
            for item in payload.holdings
        ]
        total = payload.total_value
        if total is None:
            total = sum(
                (row.market_value_base for row in rows if row.market_value_base is not None),
                Decimal("0"),
            )

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            as_of=as_of,
            base_currency=base_currency,
            total_value=total,
            source=payload.source,
            source_status=payload.source_status,
            source_message=payload.source_message,
            metadata_json=payload.metadata,
        )
        self.s.add(snapshot)
        self.s.flush()

        for row in rows:
            row.snapshot_id = snapshot.id
            self.s.add(row)

        self._audit_snapshot(snapshot, len(rows))
        return snapshot, rows

    def _load_accounts(
        self, user_id: uuid.UUID, account_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Account]:
        if not account_ids:
            return {}
        accounts = {
            row.id: row
            for row in self.s.execute(
                select(Account).where(Account.user_id == user_id, Account.id.in_(account_ids))
            ).scalars()
        }
        missing = account_ids - set(accounts)
        if missing:
            missing_ids = ", ".join(sorted(str(item) for item in missing))
            raise PortfolioSnapshotError(f"Unknown or inaccessible account_id: {missing_ids}")
        return accounts

    def _load_instruments(self, instrument_ids: set[uuid.UUID]) -> dict[uuid.UUID, Instrument]:
        if not instrument_ids:
            return {}
        instruments = {
            row.id: row
            for row in self.s.execute(
                select(Instrument).where(Instrument.id.in_(instrument_ids))
            ).scalars()
        }
        missing = instrument_ids - set(instruments)
        if missing:
            missing_ids = ", ".join(sorted(str(item) for item in missing))
            raise PortfolioSnapshotError(f"Unknown instrument_id: {missing_ids}")
        return instruments

    def _build_import_holding(
        self,
        user_id: uuid.UUID,
        item: HoldingSnapshotCreate,
        *,
        account: Account,
        instrument: Instrument,
        base_currency: str,
        as_of: datetime,
    ) -> HoldingSnapshot:
        currency = (item.currency or instrument.currency).upper()
        market_value_native = item.market_value_native
        if market_value_native is None and item.last_price is not None:
            market_value_native = (item.quantity * item.last_price).quantize(VALUATION_QUANT)

        market_value_base = item.market_value_base
        if market_value_base is None and market_value_native is not None:
            rate = self.fx.get_rate(currency, base_currency, as_of.date())
            if rate is not None:
                market_value_base = (market_value_native * rate).quantize(VALUATION_QUANT)

        return HoldingSnapshot(
            snapshot_id=uuid.uuid4(),
            user_id=user_id,
            account_id=account.id,
            account_name=account.name,
            instrument_id=instrument.id,
            symbol=instrument.symbol,
            instrument_name=instrument.name,
            asset_class=instrument.asset_class,
            industry_id=instrument.industry_id,
            currency=currency,
            quantity=item.quantity,
            avg_cost=item.avg_cost,
            last_price=item.last_price,
            market_value_native=market_value_native,
            market_value_base=market_value_base,
            metadata_json=item.metadata,
        )

    def _audit_snapshot(self, snapshot: PortfolioSnapshot, holding_count: int) -> None:
        self.audit.record(
            action="INSERT",
            target_table="portfolio_snapshots",
            target_id=snapshot.id,
            after={
                "as_of": snapshot.as_of.isoformat(),
                "source": snapshot.source,
                "source_status": snapshot.source_status,
                "base_currency": snapshot.base_currency,
                "total_value": str(snapshot.total_value),
                "holding_count": holding_count,
            },
        )
