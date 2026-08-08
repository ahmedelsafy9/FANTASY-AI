"""Player presentation metadata: photo URLs, built from real bootstrap-static fields.

Never fabricates a URL for a player the source data doesn't cover.
If a player's ``photo`` field is missing or malformed, ``player_photo_url``
returns ``None`` rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# FPL/Official Premier League player-photo endpoint.
# The ID here comes from bootstrap-static's ``photo`` field,
# NOT from the player's FPL ``element`` ID.
_PHOTO_URL_TEMPLATE = (
    "https://resources.premierleague.com/"
    "premierleague/photos/players/110x140/p{photo_id}.png"
)


@dataclass(frozen=True)
class PlayerMetadata:
    """Presentation metadata for one player.

    Attributes:
        player_id: The player's numeric FPL ``element`` ID.
        web_name: The player's short display name.
        team_id: The player's current team ID.
        photo_url: URL to the player's photo, or ``None`` if the
            source record didn't include a valid ``photo`` field.
        full_name: The player's full name (first_name + second_name).
    """

    player_id: int
    web_name: str
    team_id: int | None
    photo_url: str | None
    full_name: str | None = None


def player_photo_url(photo_field: str | None) -> str | None:
    """Build a player photo URL from bootstrap-static's ``photo`` field.

    The FPL bootstrap-static ``photo`` field normally looks like:

        "487838.jpg"

    The numeric part (487838) is the Premier League photo identifier.
    It is NOT the same thing as the FPL ``element`` ID.

    Args:
        photo_field: Raw ``photo`` value from bootstrap-static.

    Returns:
        The official player-photo URL, or ``None`` when the field is
        missing or does not have the expected ``<numeric_id>.jpg`` form.
    """
    if photo_field is None:
        return None

    value = str(photo_field).strip()

    if not value:
        return None

    photo_id, separator, extension = value.rpartition(".")

    # Require an actual filename-like value such as "487838.jpg".
    if not separator:
        return None

    if extension.lower() != "jpg":
        return None

    if not photo_id.isdigit():
        return None

    return _PHOTO_URL_TEMPLATE.format(photo_id=photo_id)


def build_player_metadata(
    elements: list[dict[str, Any]],
) -> dict[int, PlayerMetadata]:
    """Build a player-ID -> PlayerMetadata lookup.

    Args:
        elements:
            Raw player records from the ``elements`` list in the
            FPL bootstrap-static response.

    Returns:
        A dictionary keyed by the player's FPL ``element`` ID.
        Players without a valid ``id`` are skipped.
    """
    result: dict[int, PlayerMetadata] = {}

    for element in elements:
        player_id = element.get("id")

        if player_id is None:
            continue

        try:
            numeric_player_id = int(player_id)
        except (TypeError, ValueError):
            continue

        fn = str(element.get("first_name", "")).strip()
        sn = str(element.get("second_name", "")).strip()
        full_name = f"{fn} {sn}".strip() if (fn or sn) else None

        result[numeric_player_id] = PlayerMetadata(
            player_id=numeric_player_id,
            web_name=str(element.get("web_name", "Unknown")),
            team_id=(
                int(element["team"])
                if element.get("team") is not None
                else None
            ),
            photo_url=player_photo_url(element.get("photo")),
            full_name=full_name,
        )

    return result