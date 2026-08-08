"""The Fantasy-AI FastAPI application.

Run locally with:

    uvicorn src.api.main:app --reload

Swagger UI is served at ``/swagger`` (configurable via
``FANTASY_AI_API_DOCS_URL``); the raw OpenAPI schema is always at
``/openapi.json``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.api.routers import players, predictions
from src.api.schemas import HealthResponse
from src.api.state import build_app_state
from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.core.exceptions import FantasyAIError

logger = get_logger(__name__)


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

    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        docs_url=settings.api.docs_url,
        lifespan=lifespan,
    )

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
    # CORS
    # ------------------------------------------------------------------
    # Note: CORSMiddleware is added LAST so that Starlette wraps it around
    # all custom @app.middleware("http") handlers, ensuring CORS headers
    # are attached to ALL responses (including 503 errors and OPTIONS preflights).
    # ------------------------------------------------------------------

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()