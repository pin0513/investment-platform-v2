from __future__ import annotations

import builtins
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.account import Account
from app.repositories.account import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate


class AccountNotFoundError(Exception):
    pass


class AccountService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = AccountRepository(session)
        self.audit = audit

    def list(self, user_id: uuid.UUID) -> builtins.list[Account]:
        return self.repo.list_for_user(user_id)

    def get(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        acc = self.repo.get_for_user(user_id, account_id)
        if acc is None:
            raise AccountNotFoundError(str(account_id))
        return acc

    def create(self, user_id: uuid.UUID, payload: AccountCreate) -> Account:
        acc = Account(
            id=uuid.uuid4(),
            user_id=user_id,
            name=payload.name,
            account_type=payload.account_type,
            provider=payload.provider,
            currency=payload.currency,
            external_account_no_last4=payload.external_account_no_last4,
            metadata_json=payload.metadata,
            is_active=True,
        )
        self.repo.create(acc)
        self.audit.record(
            action="INSERT",
            target_table="accounts",
            target_id=acc.id,
            after={
                "name": acc.name,
                "account_type": acc.account_type,
                "provider": acc.provider,
                "currency": acc.currency,
            },
        )
        return acc

    def update(self, user_id: uuid.UUID, account_id: uuid.UUID, payload: AccountUpdate) -> Account:
        acc = self.get(user_id, account_id)
        before: dict[str, Any] = {
            "name": acc.name,
            "provider": acc.provider,
            "currency": acc.currency,
            "external_account_no_last4": acc.external_account_no_last4,
            "is_active": acc.is_active,
            "metadata": dict(acc.metadata_json or {}),
        }
        if payload.name is not None:
            acc.name = payload.name
        if payload.provider is not None:
            acc.provider = payload.provider
        if payload.currency is not None:
            acc.currency = payload.currency
        if payload.external_account_no_last4 is not None:
            acc.external_account_no_last4 = payload.external_account_no_last4
        if payload.is_active is not None:
            acc.is_active = payload.is_active
        if payload.metadata is not None:
            acc.metadata_json = payload.metadata

        self.audit.record(
            action="UPDATE",
            target_table="accounts",
            target_id=acc.id,
            before=before,
            after={
                "name": acc.name,
                "provider": acc.provider,
                "currency": acc.currency,
                "external_account_no_last4": acc.external_account_no_last4,
                "is_active": acc.is_active,
                "metadata": dict(acc.metadata_json or {}),
            },
        )
        return acc

    def delete(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        acc = self.get(user_id, account_id)
        self.repo.soft_delete(acc)
        self.audit.record(
            action="DELETE",
            target_table="accounts",
            target_id=acc.id,
            before={"name": acc.name},
        )
