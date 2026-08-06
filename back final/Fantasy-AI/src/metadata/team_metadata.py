"""Team presentation metadata: badge URLs, built from real bootstrap-static fields.

**Never fabricates a URL for a team the mapping doesn't cover.** If a
team's ``code`` field is missing, :func:`team_badge_url` returns
``None`` rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_BADGE_URL_TEMPLATE = "https://resources.premierleague.com/premierleague/badges/70/t{code}.png"


@dataclass(frozen=True)
class TeamMetadata:
    """Presentation metadata for one team.

    Attributes:
        team_id: The team's numeric FPL ID (season-specific).
        name: The team's full name.
        short_name: The team's 3-letter short code (e.g. ``"ARS"``).
        badge_url: URL to the team's badge image, or ``None`` if the
            source record didn't include a ``code`` field to build it
            from.
    """

    team_id: int
    name: str
    short_name: str | None
    badge_url: str | None


def team_badge_url(team_code: int | None) -> str | None:
    """Build a team badge image URL from its stable FPL ``code`` field.

    Args:
        team_code: The team's ``code`` field from bootstrap-static
            (distinct from ``id`` — ``code`` is stable across seasons;
            ``id`` is not). ``None`` if unavailable.

    Returns:
        str | None: The badge URL, or ``None`` if ``team_code`` is
        ``None`` — never a guessed/fabricated URL.
    """
    if team_code is None:
        return None
    return _BADGE_URL_TEMPLATE.format(code=team_code)


def build_team_metadata(teams: list[dict[str, Any]]) -> dict[int, TeamMetadata]:
    """Build a team-ID -> :class:`TeamMetadata` lookup from bootstrap-static teams.

    Args:
        teams: Raw team records from
            :meth:`~src.data_collection.sources.fpl_api_source.FPLApiDataSource.get_teams`.

    Returns:
        dict[int, TeamMetadata]: One entry per team with a valid ``id``.
    """
    result: dict[int, TeamMetadata] = {}
    for team in teams:
        team_id = team.get("id")
        if team_id is None:
            continue
        result[int(team_id)] = TeamMetadata(
            team_id=int(team_id),
            name=team.get("name", "Unknown"),
            short_name=team.get("short_name"),
            badge_url=team_badge_url(team.get("code")),
        )
    return result
