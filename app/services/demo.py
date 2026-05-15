from __future__ import annotations

import copy
import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.analysis import Analysis
from app.models.holding import Holding
from app.models.refresh_token import RefreshToken
from app.models.report import Report
from app.models.transaction import Transaction
from app.models.user import User

DEMO_EMAIL = "demo@invest.paulfun.net"
DEMO_SLUG = "demo"
DEMO_SCALE = Decimal("0.01")


class DemoSourceNotFoundError(Exception):
    pass


class DemoUserService:
    def __init__(self, session: Session):
        self.s = session

    def reset_from_source_email(self, source_email: str) -> User:
        source = self.s.execute(
            select(User).where(User.email == source_email, User.deleted_at.is_(None))
        ).scalar_one_or_none()
        if source is None:
            raise DemoSourceNotFoundError(source_email)

        demo = self._ensure_demo_user(source)
        self._clear_demo_data(demo.id)
        account_map = self._copy_accounts(source.id, demo.id)
        self._copy_holdings(source.id, demo.id, account_map)
        self._copy_transactions(source.id, demo.id, account_map)
        self._copy_analyses(source.id, demo.id)
        self._copy_reports(source.id, demo.id)
        self.s.flush()
        return demo

    def _ensure_demo_user(self, source: User) -> User:
        demo = self.s.execute(
            select(User).where(User.email == DEMO_EMAIL, User.deleted_at.is_(None))
        ).scalar_one_or_none()
        if demo is None:
            demo = User(id=uuid.uuid4(), email=DEMO_EMAIL, slug=DEMO_SLUG)
            self.s.add(demo)
            self.s.flush()

        demo.google_sub = None
        demo.display_name = "Demo Portfolio"
        demo.slug = DEMO_SLUG
        demo.base_currency = source.base_currency
        demo.role = "USER"
        demo.password_hash = None
        demo.is_active = True
        demo.timezone = source.timezone
        demo.metadata_json = {
            "demo": True,
            "source_user_slug": source.slug,
            "scale": str(DEMO_SCALE),
        }
        return demo

    def _clear_demo_data(self, demo_user_id: uuid.UUID) -> None:
        self.s.execute(delete(RefreshToken).where(RefreshToken.user_id == demo_user_id))
        self.s.execute(delete(Report).where(Report.user_id == demo_user_id))
        self.s.execute(delete(Analysis).where(Analysis.user_id == demo_user_id))
        self.s.execute(delete(Transaction).where(Transaction.user_id == demo_user_id))
        self.s.execute(delete(Holding).where(Holding.user_id == demo_user_id))
        self.s.execute(delete(Account).where(Account.user_id == demo_user_id))

    def _copy_accounts(
        self, source_user_id: uuid.UUID, demo_user_id: uuid.UUID
    ) -> dict[uuid.UUID, uuid.UUID]:
        account_map: dict[uuid.UUID, uuid.UUID] = {}
        accounts = self.s.execute(
            select(Account).where(Account.user_id == source_user_id, Account.deleted_at.is_(None))
        ).scalars()
        for account in accounts:
            new_id = uuid.uuid4()
            account_map[account.id] = new_id
            metadata = copy.deepcopy(account.metadata_json or {})
            metadata["demo_scaled_from_account_id"] = str(account.id)
            self.s.add(
                Account(
                    id=new_id,
                    user_id=demo_user_id,
                    name=account.name,
                    account_type=account.account_type,
                    provider=account.provider,
                    currency=account.currency,
                    external_account_no_last4="0000" if account.external_account_no_last4 else None,
                    is_active=account.is_active,
                    metadata_json=metadata,
                )
            )
        self.s.flush()
        return account_map

    def _copy_holdings(
        self,
        source_user_id: uuid.UUID,
        demo_user_id: uuid.UUID,
        account_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        holdings = self.s.execute(
            select(Holding).where(Holding.user_id == source_user_id, Holding.deleted_at.is_(None))
        ).scalars()
        for holding in holdings:
            account_id = account_map.get(holding.account_id)
            if account_id is None:
                continue
            metadata = copy.deepcopy(holding.metadata_json or {})
            metadata["demo_scaled_from_holding_id"] = str(holding.id)
            self.s.add(
                Holding(
                    id=uuid.uuid4(),
                    user_id=demo_user_id,
                    account_id=account_id,
                    instrument_id=holding.instrument_id,
                    quantity=(holding.quantity * DEMO_SCALE).quantize(Decimal("0.00000001")),
                    avg_cost=holding.avg_cost,
                    cost_currency=holding.cost_currency,
                    opened_at=holding.opened_at,
                    last_txn_at=holding.last_txn_at,
                    notes=holding.notes,
                    metadata_json=metadata,
                )
            )

    def _copy_transactions(
        self,
        source_user_id: uuid.UUID,
        demo_user_id: uuid.UUID,
        account_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        transactions = self.s.execute(
            select(Transaction).where(Transaction.user_id == source_user_id)
        ).scalars()
        txn_map: dict[uuid.UUID, uuid.UUID] = {}
        copied: list[tuple[Transaction, Transaction]] = []
        for txn in transactions:
            account_id = account_map.get(txn.account_id)
            if account_id is None:
                continue
            new_id = uuid.uuid4()
            txn_map[txn.id] = new_id
            metadata = copy.deepcopy(txn.metadata_json or {})
            metadata["demo_scaled_from_transaction_id"] = str(txn.id)
            new_txn = Transaction(
                id=new_id,
                user_id=demo_user_id,
                account_id=account_id,
                instrument_id=txn.instrument_id,
                txn_type=txn.txn_type,
                occurred_at=txn.occurred_at,
                quantity=_scale_optional(txn.quantity),
                price=txn.price,
                amount=(txn.amount * DEMO_SCALE).quantize(Decimal("0.00000001")),
                fee=(txn.fee * DEMO_SCALE).quantize(Decimal("0.00000001")),
                tax=(txn.tax * DEMO_SCALE).quantize(Decimal("0.00000001")),
                currency=txn.currency,
                fx_rate_to_base=txn.fx_rate_to_base,
                counter_account_id=account_map.get(txn.counter_account_id)
                if txn.counter_account_id
                else None,
                external_ref=f"demo:{txn.external_ref}" if txn.external_ref else None,
                notes=txn.notes,
                metadata_json=metadata,
            )
            self.s.add(new_txn)
            copied.append((txn, new_txn))
        self.s.flush()
        for source_txn, new_txn in copied:
            if source_txn.reversed_by:
                new_txn.reversed_by = txn_map.get(source_txn.reversed_by)

    def _copy_analyses(self, source_user_id: uuid.UUID, demo_user_id: uuid.UUID) -> None:
        analyses = self.s.execute(
            select(Analysis).where(
                Analysis.user_id == source_user_id, Analysis.deleted_at.is_(None)
            )
        ).scalars()
        for analysis in analyses:
            metadata = copy.deepcopy(analysis.metadata_json or {})
            metadata["demo_scaled_from_analysis_id"] = str(analysis.id)
            self.s.add(
                Analysis(
                    id=uuid.uuid4(),
                    user_id=demo_user_id,
                    instrument_id=analysis.instrument_id,
                    analysis_type=analysis.analysis_type,
                    angle=analysis.angle,
                    as_of_date=analysis.as_of_date,
                    generated_at=analysis.generated_at,
                    title=analysis.title,
                    summary_md=analysis.summary_md,
                    content_md=analysis.content_md,
                    metrics=copy.deepcopy(analysis.metrics or {}),
                    sources=copy.deepcopy(analysis.sources or []),
                    llm_model=analysis.llm_model,
                    confidence=analysis.confidence,
                    is_superseded=analysis.is_superseded,
                    metadata_json=metadata,
                )
            )

    def _copy_reports(self, source_user_id: uuid.UUID, demo_user_id: uuid.UUID) -> None:
        reports = self.s.execute(
            select(Report).where(Report.user_id == source_user_id, Report.deleted_at.is_(None))
        ).scalars()
        report_map: dict[uuid.UUID, uuid.UUID] = {}
        copied: list[tuple[Report, Report]] = []
        for report in reports:
            new_id = uuid.uuid4()
            report_map[report.id] = new_id
            metrics = copy.deepcopy(report.metrics or {})
            metrics["demo_scaled"] = True
            metrics["demo_scale"] = str(DEMO_SCALE)
            new_report = Report(
                id=new_id,
                user_id=demo_user_id,
                report_type=report.report_type,
                period_start=report.period_start,
                period_end=report.period_end,
                generated_at=report.generated_at,
                uploaded_at=report.uploaded_at,
                llm_model=report.llm_model,
                llm_provider=report.llm_provider,
                news_detail_level=report.news_detail_level,
                timeline=copy.deepcopy(report.timeline or []),
                summary_md=_demo_text(report.summary_md),
                content_md=_demo_text(report.content_md),
                metrics=metrics,
                related_instruments=list(report.related_instruments or []),
                related_industries=list(report.related_industries or []),
                status=report.status,
                version=report.version,
            )
            self.s.add(new_report)
            copied.append((report, new_report))
        self.s.flush()
        for source_report, new_report in copied:
            if source_report.prev_version_id:
                new_report.prev_version_id = report_map.get(source_report.prev_version_id)


def _scale_optional(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return (value * DEMO_SCALE).quantize(Decimal("0.00000001"))


def _demo_text(value: str | None) -> str | None:
    if value is None:
        return None
    return f"[Demo account: values are scaled to 1/100 of the source portfolio.]\n\n{value}"
