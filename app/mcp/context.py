"""Shared helper: yield (user, db, audit) for an MCP tool given its Context.

Usage in a tool:

    @mcp.tool()
    def my_tool(ctx: Context) -> SomeSchema:
        with mcp_request(ctx) as (user, db, audit):
            svc = SomeService(db, audit)
            return svc.do_thing(user.id)
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_session_factory
from app.models.user import User
from app.repositories.user import UserRepository


@contextmanager
def mcp_request(ctx) -> Iterator[tuple[User, Session, AuditWriter]]:
    """Open a DB session and yield (user, db, audit_writer).

    `ctx` is the FastMCP Context passed to every tool.

    The Starlette Request associated with the current MCP session is available
    at `ctx.request_context.request`.  Our McpJwtMiddleware stores the
    authenticated user's id on `request.state.user_id`, which is read here.

    Note: `scope["state"]` is shared across all Request instances constructed
    from the same ASGI scope, so middleware-set state is visible here even
    though the MCP SDK may create a new Request object internally.
    """
    request = ctx.request_context.request  # Starlette Request
    user_id: uuid.UUID = request.state.user_id

    factory = get_session_factory()
    s = factory()
    try:
        user = UserRepository(s).get_by_id(user_id)
        if user is None:
            raise RuntimeError(f"user {user_id} not found in MCP context")
        audit = AuditWriter(
            s,
            request_id=None,
            actor_user_id=user.id,
            actor_type="USER",
            ip=None,
        )
        yield user, s, audit
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
