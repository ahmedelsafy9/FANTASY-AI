"""Router: GET /player/{player_id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_player_service
from src.api.schemas import PlayerResponse
from src.api.services.player_service import PlayerService
from src.core.exceptions import PlayerNotFoundError

router = APIRouter(tags=["players"])


@router.get("/player/{player_id}", response_model=PlayerResponse)
def get_player(
    player_id: str,
    player_service: PlayerService = Depends(get_player_service),
) -> PlayerResponse:
    """Return a player's most recently known state.

    Args:
        player_id: The player's identifier (as used in the underlying
            dataset — typically the FPL ``element`` ID).
        player_service: Injected player lookup service.

    Returns:
        PlayerResponse: The player's latest known row.

    Raises:
        HTTPException: 404 if no player matches ``player_id``.
    """
    try:
        player = player_service.get_player(player_id)
    except PlayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlayerResponse(data=player)
