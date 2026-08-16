"""The Fantasy-AI FastAPI application.

Run locally with:

    uvicorn src.api.main:app --reload

Swagger UI is served at ``/swagger`` (configurable via
``FANTASY_AI_API_DOCS_URL``); the raw OpenAPI schema is always at
``/openapi.json``.

Authentication: this API is intentionally public and read-only. Every
route only serves precomputed, publicly-available FPL predictions —
there is no user data, no write endpoints, and no training/automation
endpoint is wired into this app (those exist only as separate
offline scripts under ``scripts/``). The frontend's Google OAuth
"login" is a client-side-only UI gate — it is NOT enforced by this
backend and provides no real access control; do not treat it as
authentication when reasoning about this API's security. If that
changes (e.g. per-user data is added), real server-side auth will be
required here — it intentionally hasn't been added preemptively.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from src.api.routers import players, predictions
from src.api.schemas import HealthResponse
from src.api.state import build_app_state
from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.core.exceptions import FantasyAIError

logger = get_logger(__name__)


def _get_client_ip(request: Request) -> str:
    """Resolve the real client IP for rate-limiting, safely.

    Deliberately does NOT trust ``X-Forwarded-For`` — that header can
    contain client-supplied, spoofable values, especially with more
    than one hop in front of the app.

    On Fly.io, the app sits behind Fly's own edge proxy, so the raw
    ASGI/TCP peer (``request.client.host``) is Fly's internal proxy,
    not the real client — using it directly would make every request
    look like it comes from the same source, collapsing the per-IP
    limit into one global limit shared by all users. Fly's edge sets
    the ``Fly-Client-IP`` header itself (overwriting anything a client
    tries to send), so unlike ``X-Forwarded-For`` it can be trusted
    when this app is actually deployed on Fly.

    Falls back to the raw TCP peer when the header is absent (local
    dev, tests, or any environment that isn't Fly's proxy).

    Args:
        request: The incoming request.

    Returns:
        str: The best-available client IP for rate-limiting purposes.
    """
    fly_client_ip = request.headers.get("Fly-Client-IP")
    if fly_client_ip:
        return fly_client_ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load data, the trained model, and predictions once at startup.

    Args:
        app: The FastAPI application instance.

    Yields:
        None
    """
    configure_logging()
    settings = get_settings()

    try:
        app.state.fantasy_ai_state = build_app_state(settings)

        logger.info("Fantasy-AI API startup complete.")

    except (FileNotFoundError, FantasyAIError) as exc:
        logger.error(
            "Fantasy-AI API starting WITHOUT usable state: %s. "
            "Run the full pipeline (scripts.run_feature_engineering, "
            "scripts.run_training) before serving traffic.",
            exc,
        )

        app.state.fantasy_ai_state = None

    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        FastAPI: The configured application.
    """
    settings = get_settings()
    is_production = settings.environment.lower() == "production"

    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        docs_url=settings.api.docs_url,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Rate limiting (abuse / scraping protection on public read endpoints).
    #
    # NOTE: with the default "memory://" storage this only limits requests
    # within a single running process. That's fine for a single instance
    # but is NOT sufficient once the app runs as multiple
    # instances/workers (or per-invocation serverless) — in that case set
    # FANTASY_AI_RATE_LIMIT_STORAGE_URI to a shared store (e.g. Redis)
    # before relying on this alone.
    # ------------------------------------------------------------------

    if is_production and settings.api.rate_limit_storage_uri.startswith("memory://"):
        logger.warning(
            "Rate limiting is using in-memory storage in a production environment. "
            "This only limits requests per-instance. If this deploys as more than "
            "one instance/worker, set FANTASY_AI_RATE_LIMIT_STORAGE_URI to a shared "
            "store (e.g. redis://...) or the limit is trivially bypassed by hitting "
            "different instances."
        )

    limiter = Limiter(
        key_func=_get_client_ip,
        storage_uri=settings.api.rate_limit_storage_uri,
        default_limits=[settings.api.rate_limit_default],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------

    app.include_router(players.router)
    app.include_router(predictions.router)

    # ------------------------------------------------------------------
    # Health endpoint
    # ------------------------------------------------------------------

    @app.get("/", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        """Report whether the API has usable prediction state loaded.

        Returns:
            HealthResponse: Current API/model state.
        """
        state = app.state.fantasy_ai_state

        if state is None:
            return HealthResponse(status="not_ready")

        return HealthResponse(
            status="ok",
            model_name=state.loaded_model.model_name,
            player_count=len(state.predictions),
            live_metadata_available=state.live_metadata_available,
        )

    # ------------------------------------------------------------------
    # State protection middleware
    # ------------------------------------------------------------------

    @app.middleware("http")
    async def require_state_loaded(request, call_next):
        """Return 503 for data-dependent routes if startup state failed.

        Args:
            request: The incoming request.
            call_next: The next handler in the middleware chain.

        Returns:
            The response, or a 503 JSON error if state isn't loaded.
        """

        always_available_paths = (
            "/",
            app.docs_url,
            app.redoc_url,
            "/openapi.json",
        )

        if (
            request.method != "OPTIONS"
            and request.url.path not in always_available_paths
            and getattr(app.state, "fantasy_ai_state", None) is None
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Prediction data is not available. Run the data pipeline "
                        "(ingestion, preprocessing, feature engineering, training) first."
                    )
                },
            )

        return await call_next(request)

    # ------------------------------------------------------------------
    # Security headers
    # ------------------------------------------------------------------
    # This is a pure JSON API with no HTML/JS pages of its own, so headers
    # aimed at browser-rendered content (Content-Security-Policy,
    # X-Frame-Options, Permissions-Policy) have no meaningful effect here
    # and are intentionally omitted rather than added for the sake of a
    # checklist. The headers below all apply to plain API responses.
    # ------------------------------------------------------------------

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        """Attach headers relevant to a JSON-only API to every response."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response

    # ------------------------------------------------------------------
    # Safe error responses
    # ------------------------------------------------------------------
    # Unhandled exceptions are logged with full detail server-side and
    # returned to the client as a generic message only — no stack traces,
    # file paths, or exception text ever reach the response body.
    # ------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    # Note: CORSMiddleware is added LAST so that Starlette wraps it around
    # all custom @app.middleware("http") handlers, ensuring CORS headers
    # are attached to ALL responses (including 503 errors and OPTIONS preflights).
    #
    # Production origins come strictly from FANTASY_AI_CORS_ORIGINS (no
    # wildcards). Localhost origins are dev defaults and are only added
    # when outside of FANTASY_AI_ENV=production. allow_credentials
    # defaults to False since this API has no cookie/session-based auth.
    # ------------------------------------------------------------------

    dev_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    if is_production:
        allowed_origins = list(settings.api.cors_allowed_origins)
        if not allowed_origins:
            logger.warning(
                "FANTASY_AI_ENV=production but FANTASY_AI_CORS_ORIGINS is not set — "
                "no browser origin will be able to call this API. Set it to your "
                "production frontend origin(s), comma-separated."
            )
    else:
        # Development: default local dev origins + any configured origins
        allowed_origins = list(
            dict.fromkeys(dev_origins + list(settings.api.cors_allowed_origins))
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    return app


app = create_app()