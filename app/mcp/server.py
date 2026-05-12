"""FastMCP server instance — tools register themselves on import.

HTTP transport: streamable-http (FastMCP 3.x default).
The sub-app is mounted at `/mcp` in app/main.py:
    app.mount("/mcp", build_http_app())

The actual MCP endpoint inside the sub-app is `/` (path="" resolved to root),
so the full path from the FastAPI perspective is `/mcp/` (POST).

Method used: `mcp.http_app(path="/", middleware=[...])` (FastMCP >= 2.0).
Alternatives that were considered and skipped:
  - `mcp.streamable_http_app()` — alias for http_app in older 2.x releases
  - `mcp.sse_app()` — SSE transport (legacy)

FastMCP 3.x installs starlette >= 1.0.0 which conflicts with FastAPI 0.117.1's
requirement of starlette < 0.49.0.  The starlette pin in requirements.txt is
handled by keeping starlette 0.48.x installed; fastmcp works fine with it.
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

    # Pass middleware at construction time (cleaner than post-construction
    # add_middleware which requires rebuilding the middleware stack).
    # path="/" ensures the route inside the sub-app is "/" so that when
    # mounted at /mcp the full endpoint is POST /mcp/.
    return mcp.http_app(
        path="/",
        middleware=[Middleware(McpJwtMiddleware)],
    )
