"""Test MCP tools without going through HTTP — use FastMCP's in-memory Client."""

import os
import uuid

import pytest

from app.db import session_scope
from app.mcp.server import mcp
from app.models.account import Account
from app.models.refresh_token import RefreshToken
from app.models.user import User

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture(autouse=True)
def _register_tools():
    """Importing tool modules registers them with the singleton mcp instance."""
    from app.mcp.tools import accounts, instruments, transactions  # noqa: F401


@pytest.fixture
def test_user():
    user_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=f"mcptools-{uuid.uuid4().hex[:8]}@x.z",
                slug=f"mt{uuid.uuid4().hex[:8]}",
                role="USER",
                is_active=True,
            )
        )
    yield user_id
    with session_scope() as s:
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(Account).filter(Account.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


async def test_list_accounts_tool_registered(test_user):
    from fastmcp import Client

    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "list_accounts" in names
        assert "create_account" in names
        assert "add_transaction" in names
        assert "reverse_transaction" in names


async def test_more_tools_registered(test_user):
    from fastmcp import Client

    from app.mcp.tools import portfolio, quotes  # noqa: F401

    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "get_portfolio_summary" in names
        assert "get_holdings" in names
        assert "recompute_holdings" in names
        assert "set_quote" in names
        assert "set_exchange_rate" in names
