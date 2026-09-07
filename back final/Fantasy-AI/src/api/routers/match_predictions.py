"""Router: GET /match-predictions/next-gameweek."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api.dependencies import get_match_prediction_service
from src.api.schemas import MatchPredictionResponse
from src.api.services.match_prediction_service import MatchPredictionService

router = APIRouter(prefix="/match-predictions", tags=["match-predictions"])


@router.get("/next-gameweek", response_model=MatchPredictionResponse)
def get_next_gameweek_match_predictions(
    request: Request,
    match_service: MatchPredictionService = Depends(get_match_prediction_service),
) -> MatchPredictionResponse:
    """Predict match outcomes for all fixtures in the upcoming Gameweek.

    Uses the existing trained Match Model (bivariate Poisson probability derivation)
    and attaches top performer projections (Fantasy Impact) from the Feedback 5 engine.
    """
    return match_service.predict_next_gameweek()
