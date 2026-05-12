"""JWT middleware for the MCP sub-app.

Mirrors `app.dependencies.get_current_user` semantics but sets
`request.state.user_id` (and related fields) so MCP tools can read it via
Context. Installed on the FastMCP Starlette sub-app via `install()`.
"""

from __future__ import annotations

import uuid

from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db import get_session_factory
from app.repositories.user import UserRepository
from app.security import decode_access_token


class McpJwtMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization") or ""
        if not auth.startswith("Bearer "):
            return JSONResponse({"error": "missing bearer"}, status_code=401)
        token = auth[len("Bearer ") :]
        try:
            claims = decode_access_token(token)
        except JWTError as e:
            return JSONResponse({"error": f"invalid token: {e}"}, status_code=401)

        sub = claims.get("sub")
        if not sub:
            return JSONResponse({"error": "no subject"}, status_code=401)

        # Fetch user (one DB hit per MCP request — acceptable; could cache in P3)
        factory = get_session_factory()
        with factory() as s:
            user = UserRepository(s).get_by_id(uuid.UUID(sub))
            if user is None or not user.is_active:
                return JSONResponse({"error": "user inactive"}, status_code=401)
            request.state.user_id = user.id
            request.state.user_email = user.email
            request.state.user_role = user.role
        return await call_next(request)


def install(app) -> None:
    """Add McpJwtMiddleware to an existing Starlette app instance."""
    app.add_middleware(McpJwtMiddleware)
