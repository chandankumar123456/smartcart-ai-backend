"""FastAPI application entry point.

Architecture:
  User → CDN → Load Balancer → FastAPI App → Agent Pipeline → DB → Response
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import cart, events, recipe, search
from app.cache.redis_cache import get_cache
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.queue.worker import get_job_queue

logger = logging.getLogger(__name__)
settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle hooks."""
    # Startup
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    cache = get_cache()
    await cache.connect()
    queue = get_job_queue()
    await queue.start(num_workers=2)
    yield
    # Shutdown
    logger.info("Shutting down...")
    await queue.stop()
    await cache.disconnect()


def create_app() -> FastAPI:
    frontend_dir = Path(__file__).resolve().parent / "frontend"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "SmartCart AI — Multi-agent grocery intelligence platform. "
            "Compares prices across Blinkit, Zepto, Instamart, BigBasket, JioMart, DMart."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------
    register_exception_handlers(app)

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(search.router, tags=["AI Search"])
    app.include_router(recipe.router, tags=["AI Recipe"])
    app.include_router(cart.router, tags=["AI Cart"])
    app.include_router(events.router, tags=["Platform Intelligence"])
    if frontend_dir.exists():
        app.mount("/ui-assets", StaticFiles(directory=frontend_dir), name="ui-assets")
    else:
        logger.warning("Frontend directory missing at %s; /ui assets disabled", frontend_dir)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        cache = get_cache()
        return {
            "status": "ok",
            "version": settings.app_version,
            "cache": "connected" if cache.is_available else "unavailable",
        }

    @app.get("/", tags=["System"])
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "endpoints": [
                "/parse-query",
                "/search",
                "/recipe",
                "/cart-optimization",
                "/platform-events",
                "/ui",
            ],
            "docs": "/docs",
        }

    @app.get("/ui", include_in_schema=False)
    async def ui() -> FileResponse:
        if not frontend_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UI assets are not available",
            )
        return FileResponse(frontend_dir / "index.html")

    return app


app = create_app()
