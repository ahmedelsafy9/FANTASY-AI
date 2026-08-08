"""Router for proxying official Premier League player photos."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import httpx

router = APIRouter(tags=["player-photos"])

PHOTO_URL_TEMPLATE = (
    "https://resources.premierleague.com/"
    "premierleague/photos/players/110x140/p{photo_id}.png"
)


@router.get("/player-photo/{photo_id}")
async def get_player_photo(photo_id: str) -> Response:
    """Proxy an official Premier League player photo.

    The browser requests the image from our API instead of directly
    requesting the Premier League asset host.
    """
    if not photo_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid photo ID.")

    url = PHOTO_URL_TEMPLATE.format(photo_id=photo_id)

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve player photo.",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Player photo source returned HTTP {response.status_code}.",
        )

    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "image/png"),
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )