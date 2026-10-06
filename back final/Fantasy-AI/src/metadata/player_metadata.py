"""Player presentation metadata: photo URLs, built from real bootstrap-static fields.

Never fabricates a URL for a player the source data doesn't cover.
If a player's ``photo`` field is missing or malformed, ``player_photo_url``
returns ``None`` rather than guessing.

As of the availability integration, this module also extracts official
FPL availability/status fields (``chance_of_playing_*``, ``news``,
``news_added``, ``ep_next``, etc.) from bootstrap-static.  These are
the authoritative source for injury flags, doubt status, and transfer
news used by both the prediction adjustment and chatbot knowledge layers.
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


_POSITION_MAP: dict[int, str] = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


@dataclass(frozen=True)
class PlayerMetadata:
    """Presentation and availability metadata for one player.

    Attributes:
        player_id: The player's numeric FPL ``element`` ID.
        web_name: The player's short display name.
        team_id: The player's current team ID.
        photo_url: URL to the player's photo, or ``None`` if the
            source record didn't include a valid ``photo`` field.
        first_name: The player's first name.
        second_name: The player's surname.
        element_type: The FPL position ID (1: GKP, 2: DEF, 3: MID, 4: FWD).
        position: Short position string ("GKP", "DEF", "MID", "FWD").
        now_cost: Price in 10ths of £M (e.g. 60 for £6.0m).
        value: Price in £M (e.g. 6.0).
        status: Player availability status (e.g. "a", "d", "i", "s", "u").
        full_name: The player's full name (first_name + second_name).
        chance_of_playing_next_round: Official FPL % chance of playing next
            GW (0/25/50/75/100 or ``None`` meaning no flag).
        chance_of_playing_this_round: Official FPL % chance of playing this
            GW (same scale).
        news: Free-text injury/transfer/availability news from the FPL API.
        news_added: ISO-8601 timestamp when the news was last updated.
        ep_next: FPL's own expected-points estimate for the next Gameweek.
        ep_this: FPL's own expected-points estimate for this Gameweek.
        selected_by_percent: Current ownership percentage (e.g. 42.2).
        form_score: FPL's rolling form score.
        points_per_game: Average points per game this season.
        total_points_season: Total FPL points this season.
        minutes_season: Total minutes played this season.
        starts_season: Total starts this season.
        expected_goals: Season cumulative xG.
        expected_assists: Season cumulative xA.
        expected_goal_involvements: Season cumulative xGI.
    """

    player_id: int
    web_name: str
    team_id: int | None
    photo_url: str | None
    first_name: str | None = None
    second_name: str | None = None
    element_type: int | None = None
    position: str | None = None
    now_cost: int | None = None
    value: float | None = None
    status: str | None = None
    full_name: str | None = None
    # --- Availability / status fields (from bootstrap-static) -----------
    chance_of_playing_next_round: int | None = None
    chance_of_playing_this_round: int | None = None
    news: str | None = None
    news_added: str | None = None
    ep_next: float | None = None
    ep_this: float | None = None
    selected_by_percent: float | None = None
    form_score: float | None = None
    points_per_game: float | None = None
    total_points_season: int | None = None
    minutes_season: int | None = None
    starts_season: int | None = None
    expected_goals: float | None = None
    expected_assists: float | None = None
    expected_goal_involvements: float | None = None


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


def _safe_int(raw: Any) -> int | None:
    """Parse *raw* to ``int``, returning ``None`` on failure or ``None`` input."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _safe_float(raw: Any) -> float | None:
    """Parse *raw* to ``float``, returning ``None`` on failure or ``None`` input."""
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


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

        team_id = (
            int(element["team"])
            if element.get("team") is not None
            else None
        )
        elem_type = (
            int(element["element_type"])
            if element.get("element_type") is not None
            else None
        )
        pos = _POSITION_MAP.get(elem_type) if elem_type is not None else None
        now_cost = (
            int(element["now_cost"])
            if element.get("now_cost") is not None
            else None
        )
        val = now_cost
        fn = str(element.get("first_name", "")).strip()
        sn = str(element.get("second_name", "")).strip()
        full_name = f"{fn} {sn}".strip() if (fn or sn) else None

        # --- Parse news text (strip to None if empty) ---
        raw_news = element.get("news")
        news_text: str | None = None
        if raw_news is not None:
            news_text = str(raw_news).strip() or None

        result[numeric_player_id] = PlayerMetadata(
            player_id=numeric_player_id,
            web_name=str(element.get("web_name", "Unknown")),
            first_name=(
                str(element["first_name"])
                if element.get("first_name") is not None
                else None
            ),
            second_name=(
                str(element["second_name"])
                if element.get("second_name") is not None
                else None
            ),
            team_id=team_id,
            element_type=elem_type,
            position=pos,
            now_cost=now_cost,
            value=val,
            status=(
                str(element["status"])
                if element.get("status") is not None
                else None
            ),
            photo_url=player_photo_url(element.get("photo")),
            full_name=full_name,
            # --- Availability / status fields ---
            chance_of_playing_next_round=_safe_int(
                element.get("chance_of_playing_next_round")
            ),
            chance_of_playing_this_round=_safe_int(
                element.get("chance_of_playing_this_round")
            ),
            news=news_text,
            news_added=(
                str(element["news_added"])
                if element.get("news_added") is not None
                else None
            ),
            ep_next=_safe_float(element.get("ep_next")),
            ep_this=_safe_float(element.get("ep_this")),
            selected_by_percent=_safe_float(
                element.get("selected_by_percent")
            ),
            form_score=_safe_float(element.get("form")),
            points_per_game=_safe_float(element.get("points_per_game")),
            total_points_season=_safe_int(element.get("total_points")),
            minutes_season=_safe_int(element.get("minutes")),
            starts_season=_safe_int(element.get("starts")),
            expected_goals=_safe_float(element.get("expected_goals")),
            expected_assists=_safe_float(element.get("expected_assists")),
            expected_goal_involvements=_safe_float(
                element.get("expected_goal_involvements")
            ),
        )

    return result