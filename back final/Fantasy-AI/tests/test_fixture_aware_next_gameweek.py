"""Unit tests for src.prediction.fixture_aware_next_gameweek."""

from __future__ import annotations

import pandas as pd

from src.prediction.fixture_aware_next_gameweek import (
    ResolvedFixture,
    build_fixture_aware_next_gameweek_rows,
    resolve_team_fixtures,
)


# --- resolve_team_fixtures -------------------------------------------------------


def test_resolve_team_fixtures_maps_both_home_and_away_teams() -> None:
    """Both the home and away team must get a resolved fixture from one record."""
    fixtures = [
        {"event": 25, "team_h": 11, "team_a": 6, "team_h_difficulty": 2, "team_a_difficulty": 4}
    ]
    resolved = resolve_team_fixtures(fixtures, {11: "Arsenal", 6: "Chelsea"})
    assert resolved["Arsenal"] == ResolvedFixture(25, "Chelsea", True, 2)
    assert resolved["Chelsea"] == ResolvedFixture(25, "Arsenal", False, 4)


def test_resolve_team_fixtures_keeps_earliest_fixture_per_team() -> None:
    """If a team appears in multiple fixtures, the earliest Gameweek must win."""
    fixtures = [
        {"event": 27, "team_h": 11, "team_a": 6, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"event": 25, "team_h": 11, "team_a": 13, "team_h_difficulty": 2, "team_a_difficulty": 2},
    ]
    resolved = resolve_team_fixtures(fixtures, {11: "Arsenal", 6: "Chelsea", 13: "Liverpool"})
    assert resolved["Arsenal"].gameweek == 25
    assert resolved["Arsenal"].opponent == "Liverpool"


def test_resolve_team_fixtures_skips_records_missing_required_fields() -> None:
    """A fixture missing event/team_h/team_a must be skipped, not crash."""
    fixtures = [{"team_h": 11, "team_a": 6}]  # no 'event'
    resolved = resolve_team_fixtures(fixtures, {11: "Arsenal", 6: "Chelsea"})
    assert resolved == {}


def test_resolve_team_fixtures_handles_unmapped_team_id() -> None:
    """An unmapped team ID must fall back to a placeholder name, not crash."""
    fixtures = [{"event": 25, "team_h": 11, "team_a": 999, "team_h_difficulty": 3, "team_a_difficulty": 3}]
    resolved = resolve_team_fixtures(fixtures, {11: "Arsenal"})
    assert resolved["Arsenal"].opponent == "Team 999"


# --- build_fixture_aware_next_gameweek_rows --------------------------------------


def _sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "element": [1, 2],
            "season": ["2022-23"] * 2,
            "GW": [38, 38],
            "team": ["Arsenal", "Liverpool"],
            "minutes": [90, 90],
        }
    )


def test_falls_back_to_proxy_without_fixtures() -> None:
    """With no fixture data, behavior must match the original proxy builder exactly."""
    rows = build_fixture_aware_next_gameweek_rows(
        _sample_data(),
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        team_fixtures=None,
    )
    assert (rows["fixture_source"] == "proxy_last_played").all()
    assert (rows["predicted_for_gw"] == 1).all()  # original season-rollover behavior preserved


def test_uses_real_fixture_when_team_resolves() -> None:
    """A team with a resolved fixture must get the REAL Gameweek, not a wrapped-to-1 guess."""
    team_fixtures = {"Arsenal": ResolvedFixture(gameweek=25, opponent="Chelsea", is_home=True, difficulty=3)}
    rows = build_fixture_aware_next_gameweek_rows(
        _sample_data(),
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        team_fixtures=team_fixtures,
    )
    arsenal = rows[rows["team"] == "Arsenal"].iloc[0]
    assert arsenal["predicted_for_gw"] == 25
    assert arsenal["opponent_team"] == "Chelsea"
    assert arsenal["is_home"] == 1
    assert arsenal["fixture_difficulty"] == 3
    assert arsenal["fixture_source"] == "real_fixture"


def test_unresolved_team_honestly_falls_back_within_same_call() -> None:
    """A team with NO resolved fixture must still fall back to the proxy, not crash or guess."""
    team_fixtures = {"Arsenal": ResolvedFixture(gameweek=25, opponent="Chelsea", is_home=True, difficulty=3)}
    rows = build_fixture_aware_next_gameweek_rows(
        _sample_data(),
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        team_fixtures=team_fixtures,
    )
    liverpool = rows[rows["team"] == "Liverpool"].iloc[0]
    assert liverpool["fixture_source"] == "proxy_last_played"
    assert liverpool["predicted_for_gw"] == 1


def test_every_row_has_a_fixture_source_label() -> None:
    """Every output row must be labeled with which method produced its fixture data."""
    rows = build_fixture_aware_next_gameweek_rows(
        _sample_data(),
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        team_fixtures={},
    )
    assert set(rows["fixture_source"]) == {"proxy_last_played"}
