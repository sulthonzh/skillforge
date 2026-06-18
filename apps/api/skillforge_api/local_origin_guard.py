"""Local-origin guard — blocks browser requests from non-local origins.

Why this exists
---------------
SkillForge binds to 127.0.0.1 and the local UI endpoints (/api/marketplace/*,
/api/skills/*, etc.) have no auth: the assumption is "if you can reach
localhost, you're the owner." That assumption is FALSE for browser-driven
requests:

  * A user visits ``evil.com``. JavaScript there runs
    ``fetch("http://127.0.0.1:8000/api/marketplace/pair/code")``, gets a
    pairing code, completes pairing, and now holds a valid bridge token that
    can read the user's skill registry and publish on their behalf.
  * DNS rebinding: ``evil.com`` resolves to 127.0.0.1 mid-session, bypassing
    the same-origin policy entirely.

The 127.0.0.1 bind does NOT stop either attack — browsers happily fetch
localhost from any page. The CORS allowlist helps for credentialed requests,
but simple requests (GET, form POST) and some headers slip through, and CORS
is enforced by the browser, not the server.

The mitigation (same one Jupyter, VS Code's server, and Cursor use): if a
request carries an ``Origin`` or ``Referer`` header, that header MUST name a
local origin. Requests with NO origin (curl, the CLI, server-to-server) are
allowed — a browser always sets one of these headers on cross-origin fetches,
so its absence proves the request didn't come from a web page.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger(__name__)

# Origins that are allowed to drive the local API from a browser. Same set the
# CORS middleware already allows, kept here so the guard is self-contained.
# Note: urlparse returns the IPv6 loopback WITHOUT brackets as "::1".
_ALLOWED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",  # some setups address the loopback this way
        "::1",  # IPv6 loopback (urlparse strips the brackets)
    }
)


def _is_local_origin(origin_header: str | None) -> bool:
    """True if the origin header names a loopback host (or is absent).

    An absent header means the request didn't come from a browser (curl, the
    CLI, server-to-server) — those are trusted by the local-first model.
    """
    if not origin_header:
        return True
    try:
        host = urlparse(origin_header).hostname or ""
    except ValueError:
        return False
    # ``hostname`` lowercases and strips brackets on most inputs; be defensive.
    host = host.lower().strip("[]")
    return host in _ALLOWED_HOSTS


class LocalOriginGuardMiddleware(BaseHTTPMiddleware):
    """Reject browser requests whose Origin/Referer is not a loopback host.

    Installed before the routers so it covers every endpoint, including the
    token-less local UI endpoints that rely solely on the 127.0.0.1 bind.
    """

    async def dispatch(self, request: Request, call_next):
        # Check both Origin (preferred) and Referer (fallback — some simple
        # cross-origin requests carry Referer but not Origin).
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if not _is_local_origin(origin) or not _is_local_origin(referer):
            attacker = origin or referer or "<unknown>"
            log.warning(
                "Blocked non-local origin from reaching local API: %s (%s %s)",
                attacker,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Requests from non-local origins are blocked. "
                        "SkillForge only accepts browser requests from localhost."
                    )
                },
            )
        return await call_next(request)
