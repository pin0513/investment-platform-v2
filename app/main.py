import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app import errors
from app.config import get_settings
from app.routers import accounts as accounts_router, auth as auth_router, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response


def create_app() -> FastAPI:
    settings = get_settings()
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

    app.include_router(health.router)
    app.include_router(auth_router.router)
    app.include_router(accounts_router.router)
    return app


app = create_app()
