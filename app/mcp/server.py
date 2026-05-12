"""FastMCP server instance — tools register themselves on import.

HTTP transport: streamable-http (FastMCP 3.x) or SSE (FastMCP 2.x).
The sub-app is mounted at `/mcp` in app/main.py:
    app.mount("/mcp", build_http_app())

Compatibility:
  - FastMCP 3.x: uses `mcp.http_app(path="/", middleware=[...])` (streamable-HTTP).
  - FastMCP 2.x: falls back to `mcp.sse_app()` with middleware added via
    `add_middleware` (SSE transport).  Both respond to the same `/mcp/` path;
    the transport protocol differs but the JWT guard remains identical.

CI may resolve `fastmcp>=2.0` to 2.x when the `mcp`→`sse-starlette`→`starlette>=0.49`
chain conflicts with FastAPI 0.117.1's `starlette<0.49` requirement.  The shim
here makes both versions work without code changes.
"""

from fastmcp import FastMCP
from starlette.middleware import Middleware

mcp = FastMCP(name="investment-platform-v2")


def build_http_app():
    """Return a Starlette ASGI sub-app with JWT middleware and all tools loaded.

    Tools are imported here (not at module level) to avoid circular imports
    during test collection.  Each import executes @mcp.tool() decorators so
    the tools are registered on the shared `mcp` instance.
    """
    from app.mcp.auth import McpJwtMiddleware
    from app.mcp.tools import (  # noqa: F401  (side-effect: registers tools)
        accounts,
        instruments,
        portfolio,
        quotes,
        transactions,
    )

    if hasattr(mcp, "http_app"):
        # FastMCP 3.x — streamable-HTTP transport.
        # path="/" ensures the route inside the sub-app is "/" so that when
        # mounted at /mcp the full endpoint is POST /mcp/.
        return mcp.http_app(
            path="/",
            middleware=[Middleware(McpJwtMiddleware)],
        )
    else:
        # FastMCP 2.x — SSE transport fallback.
        # sse_app() returns a plain Starlette app; we wrap it with the JWT
        # middleware using add_middleware (rebuilds the middleware stack once).
        starlette_app = mcp.sse_app()
        starlette_app.add_middleware(McpJwtMiddleware)
        return starlette_app
