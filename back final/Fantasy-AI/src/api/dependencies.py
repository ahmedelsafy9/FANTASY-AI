"""FastAPI dependency providers.

Each function here is a thin adapter turning the app's shared
:class:`~src.api.state.AppState` (built once at startup) into the
framework-free service objects the route handlers use. Keeping this
translation in one place means route handlers never touch
``request.app.state`` directly.
"""

from __future__ import annotations

from fastapi import Request

from src.api.services.player_service import PlayerService
from src.api.services.prediction_query_service import PredictionQueryService
from src.api.state import AppState


def get_app_state(request: Request) -> AppState:
    """Retrieve the shared application state from the FastAPI app.

    Args:
        request: The current request, used to access ``app.state``.

    Returns:
        AppState: The application's shared state.
    """
    return request.app.state.fantasy_ai_state  # type: ignore[no-any-return]


def get_player_service(request: Request) -> PlayerService:
    """Build a :class:`PlayerService` from the current application state.

    Args:
        request: The current request.

    Returns:
        PlayerService: A service for player lookups.
    """
    state = get_app_state(request)
    return PlayerService(
        data=state.engineered_data,
        player_id_columns=state.settings.feature_engineering.player_id_columns,
        chronological_columns=state.settings.feature_engineering.chronological_columns,
    )


def get_prediction_query_service(request: Request) -> PredictionQueryService:
    """Build a :class:`PredictionQueryService` from the current application state.

    Args:
        request: The current request.

    Returns:
        PredictionQueryService: A service for prediction queries.
    """
    state = get_app_state(request)
    prediction_column = f"predicted_{state.loaded_model.target_column}"
    return PredictionQueryService(
        predictions=state.predictions,
        player_id_column=state.player_id_column,
        prediction_column=prediction_column,
    )
