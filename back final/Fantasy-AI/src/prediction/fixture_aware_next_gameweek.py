"""Builds next-Gameweek feature rows using REAL upcoming fixtures where possible.

**Phase 3 fix**: the original `build_next_gameweek_rows` (Sprint 7) used
each player's most recently *played* row as a proxy for their next
match — including, most visibly, wrapping `predicted_for_gw` to 1 at
the season boundary for every player still active in the final
Gameweek (e.g. the reported "866 players ... set to 1" case). That
proxy is still used here as the FALLBACK, but is no longer the only
option: when real fixture data is available (via
`FPLApiDataSource.get_fixtures()` + `get_teams()`), this module
resolves each player's TRUE next opponent, home/away status, and
official FPL fixture-difficulty rating, and never guesses a Gameweek
number — it uses the fixture's own `event` field.

**This does not hide the limitation** — every output row carries a
`fixture_source` field (`"real_fixture"` or `"proxy_last_played"`) so
callers (API, UI) can display or filter on data quality honestly,
exactly as instructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import PredictionError
from src.prediction.next_gameweek import build_next_gameweek_rows

logger = get_logger(__name__)


@dataclass(frozen=True)
class ResolvedFixture:
    """A player's real upcoming fixture, resolved from live fixture data.

    Attributes:
        gameweek: The real upcoming Gameweek (from the fixture's own
            ``event`` field — never guessed).
        opponent: The real opponent team name.
        is_home: Whether the player's team is at home for this fixture.
        difficulty: FPL's own official 1-5 fixture-difficulty rating
            for the player's team in this fixture (not derived — taken
            directly from ``team_h_difficulty``/``team_a_difficulty``).
    """

    gameweek: int
    opponent: str
    is_home: bool
    difficulty: int | None


def resolve_team_fixtures(
    fixtures: list[dict[str, Any]],
    team_id_to_name: dict[int, str],
) -> dict[str, ResolvedFixture]:
    """Resolve each team's next fixture from a raw fixtures list.

    Args:
        fixtures: Raw fixture records from
            :meth:`~src.data_collection.sources.fpl_api_source.FPLApiDataSource.get_fixtures`.
        team_id_to_name: Team-ID -> name mapping (see
            :mod:`src.data_collection.services.team_mapping_service`).

    Returns:
        dict[str, ResolvedFixture]: Team name -> that team's next
        resolved fixture. Only the earliest upcoming fixture per team
        is kept (fixtures should already be future-only, but this
        guards against duplicates/reschedules).
    """
    by_team: dict[str, ResolvedFixture] = {}

    # Fixtures are assumed sorted by kickoff time as returned by the API;
    # sort defensively by (event, kickoff_time) to be certain we keep each
    # team's EARLIEST upcoming fixture, not an arbitrary one.
    sortable = [f for f in fixtures if f.get("event") is not None]
    sortable.sort(key=lambda f: (f["event"], f.get("kickoff_time") or ""))

    for fixture in sortable:
        home_id = fixture.get("team_h")
        away_id = fixture.get("team_a")
        event = fixture.get("event")
        if home_id is None or away_id is None or event is None:
            continue

        home_name = team_id_to_name.get(home_id)
        away_name = team_id_to_name.get(away_id)

        if home_name and home_name not in by_team:
            by_team[home_name] = ResolvedFixture(
                gameweek=int(event),
                opponent=away_name or f"Team {away_id}",
                is_home=True,
                difficulty=fixture.get("team_h_difficulty"),
            )
        if away_name and away_name not in by_team:
            by_team[away_name] = ResolvedFixture(
                gameweek=int(event),
                opponent=home_name or f"Team {home_id}",
                is_home=False,
                difficulty=fixture.get("team_a_difficulty"),
            )

    logger.info("Resolved next fixtures for %d team(s).", len(by_team))
    return by_team


def build_fixture_aware_next_gameweek_rows(
    data: pd.DataFrame,
    player_id_columns: tuple[str, ...],
    chronological_columns: tuple[str, ...],
    max_valid_gameweek: int,
    team_column: str = "team",
    team_fixtures: dict[str, ResolvedFixture] | None = None,
) -> pd.DataFrame:
    """Build next-Gameweek rows, preferring real fixture data over the proxy.

    For each player, starts from the same base row the original proxy
    approach uses (their most recent played match's features — still
    the best available *feature* snapshot, since we don't have next-
    match minutes/goals/etc. yet by definition). What changes is the
    *fixture metadata*: when ``team_fixtures`` resolves the player's
    team to a real upcoming fixture, ``predicted_for_gw``,
    ``opponent_team``, ``is_home``, and a new ``fixture_difficulty``
    column are overwritten with the REAL values, and
    ``fixture_source`` is set to ``"real_fixture"``. Otherwise, the
    original proxy behavior (including the documented season-rollover
    warning) is preserved and ``fixture_source`` is set to
    ``"proxy_last_played"``.

    Args:
        data: The full engineered dataset.
        player_id_columns: Candidate player-identifier columns.
        chronological_columns: Candidate match-order columns.
        max_valid_gameweek: Last Gameweek of a season.
        team_column: Column identifying the player's own team.
        team_fixtures: Team name -> resolved next fixture, from
            :func:`resolve_team_fixtures`. ``None`` or empty makes this
            function behave identically to the original proxy-only
            builder (full backward compatibility).

    Returns:
        pd.DataFrame: One row per player, with real fixture data
        applied wherever available.

    Raises:
        PredictionError: Propagated from the underlying proxy builder
            if no player identifier or chronological column exists.
    """
    rows = build_next_gameweek_rows(
        data,
        player_id_columns=player_id_columns,
        chronological_columns=chronological_columns,
        max_valid_gameweek=max_valid_gameweek,
    )
    rows = rows.copy()
    rows["fixture_source"] = "proxy_last_played"
    rows["fixture_difficulty"] = pd.NA

    if not team_fixtures or team_column not in rows.columns:
        if not team_fixtures:
            logger.warning(
                "No real fixture data available; all %d row(s) use the "
                "last-played-match proxy. See the 'fixture_source' column.",
                len(rows),
            )
        return rows

    resolved_count = 0
    for idx, row in rows.iterrows():
        team = row.get(team_column)
        fixture = team_fixtures.get(team) if isinstance(team, str) else None
        if fixture is None:
            continue
        rows.at[idx, "predicted_for_gw"] = fixture.gameweek
        rows.at[idx, "opponent_team"] = fixture.opponent
        rows.at[idx, "is_home"] = int(fixture.is_home)
        rows.at[idx, "fixture_difficulty"] = fixture.difficulty
        rows.at[idx, "fixture_source"] = "real_fixture"
        resolved_count += 1

    logger.info(
        "Resolved real upcoming fixtures for %d/%d player row(s); %d still use the proxy.",
        resolved_count,
        len(rows),
        len(rows) - resolved_count,
    )
    return rows
