from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.media import router as media_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, configure_logging, logger
from app.core.runtime_settings import refresh_if_stale
from app.db.schema_state import schema_status
from app.services.analytics_service import download_geoip_db, geoip_available
from app.services.storage_service import is_s3_configured

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    configure_logging(settings.DEBUG)
    logger.info(
        "startup",
        env=settings.ENV,
        database=settings.DATABASE_URL.split("://")[0],
        queue="redis" if settings.REDIS_URL else "in-process",
        storage="s3" if is_s3_configured() else "local-disk",
        tryon_provider=settings.VIRTUAL_TRYON_PROVIDER,
        stylist_provider=settings.LLM_PROVIDER,
        payment_provider=settings.PAYMENT_PROVIDER,
    )
    # Shout if the database is behind this code. A pending migration shows
    # up later as a 500 deep inside an ordinary request ("column
    # tryon_results.placements does not exist" — live, after a deploy where
    # `alembic` wasn't on PATH so the migration silently never ran), which
    # is a long way from the cause. Startup is where it's cheap to see.
    schema = await schema_status()
    if schema.get("state") == "behind":
        logger.error("database_schema_behind_code", **schema)
    elif schema.get("state") == "unknown":
        logger.warning("database_schema_state_unknown", **schema)

    # admin-panel overrides (app_settings table) take precedence over .env
    await refresh_if_stale(force=True)
    if settings.GEOIP_AUTO_DOWNLOAD and not geoip_available():
        # visitor countries show as "unknown" until this finishes; never block startup on it
        app.state.geoip_download = asyncio.create_task(download_geoip_db())
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def answer_crashes_through_cors(request: Request, call_next):  # noqa: ANN202
        """Turn an unhandled error into a 500 the browser can read.

        Registered BEFORE the CORS middleware on purpose: Starlette nests
        each newly added middleware outside the ones already registered,
        so registering this first puts it inside CORS, which is where it
        has to be for the error response to come back with the header.

        This has to be a middleware *inside* the CORS layer, not an
        exception handler: Starlette runs handlers for unhandled
        exceptions in ServerErrorMiddleware, which sits outside every
        user middleware — so its response carries no
        Access-Control-Allow-Origin and the browser reports "blocked by
        CORS policy" for what is really a server error. That cost us an
        afternoon looking at CORS settings while the actual fault was a
        500 (a database column missing because a migration hadn't been
        run). Caught here, the response travels back out through the CORS
        middleware and arrives as the 500 it is.

        The client gets a generic message; the traceback goes to the log
        with the request id."""
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 — deliberately everything
            logger.exception(
                "unhandled_error", path=request.url.path, method=request.method, error=str(exc)[:500]
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Something went wrong on our side. Please try again."},
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    @app.middleware("http")
    async def sync_runtime_settings(request: Request, call_next):  # noqa: ANN202
        # throttled to one DB check per REFRESH_SECONDS per process, so a
        # key saved from the admin panel reaches every worker without a restart
        await refresh_if_stale()
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):  # noqa: ANN202, ARG001
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Invalid request", "errors": exc.errors()},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # noqa: ANN202, ARG001
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Local-disk media is only ever mounted in dev (no S3 configured) —
    # production serves signed S3/R2/CDN URLs directly, never through the API.
    if not is_s3_configured():
        app.include_router(media_router)

    @app.get("/health", tags=["meta"])
    async def health():  # noqa: ANN202
        # `schema` says whether the database has the migrations this code
        # needs: deploying without running them makes ordinary requests
        # fail in ways that look like anything but a pending migration
        return {
            "status": "ok",
            "env": settings.ENV,
            "tryon_provider": settings.VIRTUAL_TRYON_PROVIDER,
            "queue": "redis" if settings.REDIS_URL else "in-process",
            "schema": await schema_status(),
        }

    return app


app = create_app()
