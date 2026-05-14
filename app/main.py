import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import errors
from app.config import get_settings
from app.routers import (
    accounts as accounts_router,
)
from app.routers import (
    admin as admin_router,
)
from app.routers import (
    auth as auth_router,
)
from app.routers import (
    exchange_rates as exchange_rates_router,
)
from app.routers import (
    health,
)
from app.routers import (
    holdings as holdings_router,
)
from app.routers import (
    instruments as instruments_router,
)
from app.routers import (
    portfolio as portfolio_router,
)
from app.routers import (
    quotes as quotes_router,
)
from app.routers import (
    transactions as transactions_router,
)
from app.routers.reader import dashboard as reader_dashboard
from app.routers.reader import instruments_view as reader_instruments
from app.routers.reader import portfolio as reader_portfolio
from app.routers.reader import root as reader_root
from app.routers.reader import settings as reader_settings
from app.routers.reader import transactions_view as reader_transactions


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response


def create_app() -> FastAPI:
    settings = get_settings()

    # Build the FastMCP sub-app first so we can wire its lifespan into FastAPI.
    # Must happen before the FastAPI lifespan is defined to capture the reference.
    # The JWT middleware is installed inside build_http_app().
    from app.mcp.server import build_http_app

    mcp_http_app = build_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Run the MCP sub-app lifespan alongside the FastAPI lifespan so that
        # FastMCP's StreamableHTTPSessionManager task group is initialized.
        # FastMCP 3.x returns an app with a .lifespan attribute; 2.x does not.
        if hasattr(mcp_http_app, "lifespan") and mcp_http_app.lifespan is not None:
            async with mcp_http_app.lifespan(mcp_http_app):
                yield
        else:
            yield

    app = FastAPI(
        title="Investment Platform v2",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    errors.install(app)

    app.mount(
        "/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"
    )

    app.include_router(health.router)
    app.include_router(auth_router.router)
    app.include_router(accounts_router.router)
    app.include_router(instruments_router.router)
    app.include_router(admin_router.router)
    app.include_router(transactions_router.router)
    app.include_router(holdings_router.router)
    app.include_router(quotes_router.router)
    app.include_router(exchange_rates_router.router)
    app.include_router(portfolio_router.router)
    app.include_router(reader_root.router)
    app.include_router(reader_dashboard.router)
    app.include_router(reader_portfolio.router)
    app.include_router(reader_instruments.router)
    app.include_router(reader_transactions.router)
    app.include_router(reader_settings.router)

    # Mount the MCP sub-app at /mcp — must come after all include_router() calls.
    # Endpoint inside the sub-app is "/" → full path is POST /mcp/.
    app.mount("/mcp", mcp_http_app)

    return app


app = create_app()
