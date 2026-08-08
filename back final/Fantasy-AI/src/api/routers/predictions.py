"""Router: GET /predict, GET /top_players, GET /captain."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_prediction_query_service
from src.api.schemas import CaptainResponse, PredictionListResponse
from src.api.services.prediction_query_service import PredictionQueryService, _row_to_dict
from src.core.exceptions import PlayerNotFoundError

router = APIRouter(tags=["predictions"])


@router.get("/predict", response_model=PredictionListResponse)
def predict(
    request: Request,
    player_id: str | None = Query(
        default=None, description="If provided, return only this player's prediction."
    ),
    prediction_service: PredictionQueryService = Depends(get_prediction_query_service),
) -> PredictionListResponse:
    """Return next-Gameweek point predictions for every player, or one player.

    Args:
        request: The current request (used only for building the note).
        player_id: Optional player identifier to filter to a single
            player's prediction.
        prediction_service: Injected prediction query service.

    Returns:
        PredictionListResponse: One or every player's prediction,
        sorted highest to lowest.

    Raises:
        HTTPException: 404 if ``player_id`` is provided but not found.
    """
    if player_id is not None:
        try:
            player_prediction = prediction_service.get_by_player(player_id)
        except PlayerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        predictions = [player_prediction]
    else:
        predictions = [row for row in _iter_rows(prediction_service.get_all())]

    return PredictionListResponse(
        count=len(predictions),
        predicted_for_gw_note=(
            "predicted_for_gw reflects each player's own most recent match, so it may "
            "differ slightly between players who have played a different number of games."
        ),
        predictions=predictions,
    )


@router.get("/top_players", response_model=PredictionListResponse)
def top_players(
    limit: int = Query(default=10, ge=1, description="Maximum number of players to return."),
    prediction_service: PredictionQueryService = Depends(get_prediction_query_service),
) -> PredictionListResponse:
    """Return the top players by predicted next-Gameweek points.

    Args:
        limit: Maximum number of players to return.
        prediction_service: Injected prediction query service.

    Returns:
        PredictionListResponse: The top ``limit`` predictions, highest first.
    """
    top = prediction_service.get_top(limit)
    return PredictionListResponse(
        count=len(top),
        predicted_for_gw_note=(
            "predicted_for_gw reflects each player's own most recent match, so it may "
            "differ slightly between players who have played a different number of games."
        ),
        predictions=top,
    )


@router.get("/captain", response_model=CaptainResponse)
def captain(
    request: Request,
    prediction_service: PredictionQueryService = Depends(get_prediction_query_service),
) -> CaptainResponse:
    """Recommend a captain pick for the next Gameweek.

    Prefers the highest predicted scorer among players with a
    reliable recent playing-time record, to avoid recommending a
    player who might not start.

    Args:
        request: The current request (used to read app settings).
        prediction_service: Injected prediction query service.

    Returns:
        CaptainResponse: The recommended player, reasoning, and pool size.

    Raises:
        HTTPException: 404 if there are no predictions to choose from.
    """
    settings = request.app.state.fantasy_ai_state.settings
    minutes_columns = ("minutes_avg_last_3", "minutes_avg_last_5")
    try:
        recommendation = prediction_service.get_captain(
            minutes_columns=minutes_columns,
            min_minutes_avg=settings.api.captain_min_minutes_avg,
        )
    except PlayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CaptainResponse(
        recommendation=recommendation.player,
        reasoning=recommendation.reasoning,
        pool_size=recommendation.pool_size,
    )


def _iter_rows(data):
    """Yield each row of a predictions DataFrame as a plain dict.

    Args:
        data: The predictions DataFrame.

    Yields:
        dict: Each row, JSON-serializable.
    """
    for _, row in data.iterrows():
        yield _row_to_dict(row)
