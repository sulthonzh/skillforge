"""FastAPI application entrypoint.

Wires routers and CORS, and — when a static Web UI directory is provided —
serves the bundled Next.js export from the same origin so ``skillforge serve``
runs one process on one port.

API routes and ``/health`` are registered first, so they always take precedence
over the static file mount at ``/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .routers import (
    bridge as bridge_router,
    chat,
    deploy as deploy_router,
    eval as eval_router,
    health,
    marketplace as marketplace_router,
    registry,
    settings as settings_router,
    skills,
    templates,
)
from .settings import get_settings

log = logging.getLogger("skillforge_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup/shutdown hooks.

    Bootstraps the generated skill-creator skill + the default eval suite on
    first run. Wrapped so a failure never breaks startup.
    """
    try:
        from .services.bootstrap import bootstrap_skill_creator

        bootstrap_skill_creator()
    except Exception as exc:  # pragma: no cover - never break startup
        log.warning("skill-creator bootstrap skipped: %s", exc)
    try:
        from .services.eval.suites import get_suite_store

        get_suite_store().seed_default()
    except Exception as exc:  # pragma: no cover - never break startup
        log.warning("eval suite seed skipped: %s", exc)
    yield


def create_app(static_dir: str | Path | None = None) -> FastAPI:
    """Build the FastAPI app.

    Args:
        static_dir: Optional path to a statically-exported Web UI. When the
            directory exists, it is mounted at ``/`` so the API and UI share one
            origin (bundled mode). When omitted or missing, the app is API-only.
    """
    app = FastAPI(
        title="SkillForge API",
        description="Local-first AI-powered engineering skill builder.",
        version=__version__,
        lifespan=_lifespan,
    )

    # CORS — explicit allowlist. `allow_origins=["*"]` + `credentials=True` is
    # an invalid Fetch-spec combo and a CSRF hole (any website could call the
    # local API). Allow the Next dev server; the marketplace origin is added by
    # the bridge router's own CORS handling for paired sessions.
    settings = get_settings()
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Bundled mode is same-origin (the API serves the UI), so no CORS needed;
        # include localhost:8000 for the api-only/dev case where the browser hits :8000 directly.
        f"http://localhost:{settings.api_port}",
        f"http://127.0.0.1:{settings.api_port}",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 1) API routes first — they win over the static mount below.
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(skills.router)
    app.include_router(registry.router)
    app.include_router(settings_router.router)
    app.include_router(eval_router.router)
    app.include_router(marketplace_router.router)
    app.include_router(bridge_router.router)
    app.include_router(deploy_router.router)
    app.include_router(templates.router)

    # 2) Optionally serve the bundled Web UI from the same origin.
    web_path = Path(static_dir).expanduser() if static_dir else None
    if web_path and web_path.is_dir():
        _mount_web_ui(app, web_path)
        log.info("Serving bundled Web UI from %s", web_path)
    else:
        log.info("Running API-only (no bundled Web UI found at %s)", static_dir)

    return app


def _mount_web_ui(app: FastAPI, web_dir: Path) -> None:
    """Mount a static-exported SPA at ``/`` with client-side routing fallback.

    Next.js static export emits ``<route>.html`` (e.g. ``registry.html``) plus a
    static asset tree. We:
      * mount ``/_next`` and other asset dirs statically,
      * add a catch-all that serves ``<name>.html`` for clean URLs, falling back
        to ``index.html`` for deep client-side routes.
    """
    index_html = web_dir / "index.html"
    if not index_html.is_file():
        log.warning("Web UI dir has no index.html; not mounting UI.")
        return

    # Static assets (/_next, /favicon.ico, etc.). html=False so we control
    # the SPA fallback ourselves on the catch-all below.
    next_dir = web_dir / "_next"
    if next_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=next_dir), name="web-next-assets")

    # Mount any other static asset directories Next emits at the root.
    for asset_name in ("assets", "static", "images"):
        asset_dir = web_dir / asset_name
        if asset_dir.is_dir():
            app.mount(f"/{asset_name}", StaticFiles(directory=asset_dir), name=f"web-{asset_name}")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str, request: Request):
        """Serve a static file, a route's .html, or index.html (SPA fallback).

        API routes and /health are already registered above, so they never
        reach this handler.
        """
        # A direct file request (e.g. /_next/.../chunk.js handled above, or a
        # root file like /favicon.ico).
        candidate = web_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)

        # Clean-URL → static route. Next export (trailingSlash) emits
        # ``<name>/index.html`` per route; older exports may use ``<name>.html``.
        stem = full_path.rstrip("/")
        if stem:
            # /registry → registry/index.html
            dir_index = web_dir / stem / "index.html"
            if dir_index.is_file():
                return FileResponse(dir_index)
            # /registry → registry.html
            html_candidate = web_dir / f"{stem}.html"
            if html_candidate.is_file():
                return FileResponse(html_candidate)
            # Nested path (e.g. /skills/some-skill) → first segment's page.
            section = stem.split("/", 1)[0]
            section_index = web_dir / section / "index.html"
            if section_index.is_file():
                return FileResponse(section_index)
            section_html = web_dir / f"{section}.html"
            if section_html.is_file():
                return FileResponse(section_html)

        # Root or unknown → SPA fallback, let the client router handle it.
        return FileResponse(index_html)


# Default app: API-only. The CLI's `serve` passes a static_dir when running in
# bundled mode. Importing `app` directly (e.g. for uvicorn or tests) is always
# safe and never serves the UI unless configured. We build it quietly (no log
# line) so the default import doesn't print a misleading "API-only" notice.
def _create_default_app() -> FastAPI:
    """Create the module-level app without the "no Web UI" log line."""
    logging.getLogger("skillforge_api").setLevel(logging.WARNING)
    try:
        return create_app()
    finally:
        logging.getLogger("skillforge_api").setLevel(logging.INFO)


app = _create_default_app()
