"""Router: POST /squad/build, GET /squad/build.

Constructs an optimal 15-player FPL squad using the budget-aware two-stage
optimization strategy, respecting £100m budget (or user-specified budget)
and official FPL squad composition rules.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_squad_builder_service
from src.api.schemas import SquadBuildRequest, SquadBuildResponse
from src.api.services.squad_builder_service import SquadBuilderService
from src.core.exceptions import SquadBuilderError

router = APIRouter(prefix="/squad", tags=["squad"])


@router.get("/build", response_model=SquadBuildResponse)
def build_squad_get(
    request: Request,
    budget: float = Query(default=100.0, ge=40.0, le=200.0, description="Total squad budget in £M"),
    formation: str = Query(default="4-4-2", description="Starting XI formation e.g. 4-4-2, 3-5-2"),
    core_picks_count: int = Query(default=4, ge=1, le=8, description="Target number of core premium picks"),
    squad_service: SquadBuilderService = Depends(get_squad_builder_service),
) -> SquadBuildResponse:
    """Build an optimal 15-player squad within budget via GET query params."""
    app_state = request.app.state.fantasy_ai_state
    season = getattr(app_state, "season", None)
    gameweek = getattr(app_state, "predicted_gameweek", None)

    try:
        return squad_service.build_squad(
            budget=budget,
            formation=formation,
            core_picks_count=core_picks_count,
            season=season,
            gameweek=gameweek,
        )
    except SquadBuilderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/build", response_model=SquadBuildResponse)
def build_squad_post(
    request: Request,
    payload: SquadBuildRequest,
    squad_service: SquadBuilderService = Depends(get_squad_builder_service),
) -> SquadBuildResponse:
    """Build an optimal 15-player squad within budget via POST payload."""
    app_state = request.app.state.fantasy_ai_state
    season = getattr(app_state, "season", None)
    gameweek = getattr(app_state, "predicted_gameweek", None)

    try:
        return squad_service.build_squad(
            budget=payload.budget,
            formation=payload.formation,
            core_picks_count=payload.core_picks_count,
            season=season,
            gameweek=gameweek,
        )
    except SquadBuilderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
