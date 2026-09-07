"""FastAPI dependency providers.

Each function here is a thin adapter turning the app's shared
:class:`~src.api.state.AppState` (built once at startup) into the
framework-free service objects the route handlers use. Keeping this
translation in one place means route handlers never touch
``request.app.state`` directly.
"""

from __future__ import annotations

from fastapi import Request

from src.api.services.match_prediction_service import MatchPredictionService
from src.api.services.player_service import PlayerService
from src.api.services.prediction_query_service import PredictionQueryService
from src.api.services.squad_builder_service import SquadBuilderService
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
        data=state.predictions,
        player_id_columns=(state.player_id_column, "id", "element", "name"),
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
    prediction_column = (
        "predicted_fpl_rank_score"
        if "predicted_fpl_rank_score" in state.predictions.columns
        else "predicted_expected_points"
        if "predicted_expected_points" in state.predictions.columns
        else "predicted_total_points"
        if "predicted_total_points" in state.predictions.columns
        else f"predicted_{state.loaded_model.target_column}"
        if f"predicted_{state.loaded_model.target_column}" in state.predictions.columns
        else state.predictions.columns[0]
    )
    return PredictionQueryService(
        predictions=state.predictions,
        player_id_column=state.player_id_column,
        prediction_column=prediction_column,
    )


def get_match_prediction_service(request: Request) -> MatchPredictionService:
    """Build a MatchPredictionService from the current application state."""
    state = get_app_state(request)
    return MatchPredictionService(app_state=state)


def get_squad_builder_service(request: Request) -> SquadBuilderService:
    """Build a SquadBuilderService from the current application state."""
    state = get_app_state(request)
    return SquadBuilderService(predictions=state.predictions)

