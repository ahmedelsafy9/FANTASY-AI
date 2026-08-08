"""Unit tests for src.prediction.fixture_aware_next_gameweek."""

from __future__ import annotations

import pandas as pd

from src.prediction.fixture_aware_next_gameweek import (
    ResolvedFixture,
    UpcomingFixture,
    build_fixture_aware_next_gameweek_rows,
    resolve_team_fixtures,
    resolve_team_upcoming_fixtures,
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


# --- resolve_team_upcoming_fixtures ----------------------------------------------


def test_resolve_team_upcoming_fixtures_home_and_away_resolution() -> None:
    """Home and away fixtures resolve opponents, FDR difficulty, and home/away status correctly."""
    fixtures = [
        {
            "id": 101,
            "code": 2001,
            "event": 1,
            "finished": False,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
            "kickoff_time": "2026-08-20T19:00:00Z",
        }
    ]
    team_mapping = {1: "Arsenal", 2: "Chelsea"}
    resolved = resolve_team_upcoming_fixtures(fixtures, team_mapping)

    assert "Arsenal" in resolved
    assert "Chelsea" in resolved

    # Arsenal is Home vs Chelsea
    ars_fix = resolved["Arsenal"][0]
    assert ars_fix.is_home is True
    assert ars_fix.opponent_team_id == 2
    assert ars_fix.opponent_name == "Chelsea"
    assert ars_fix.difficulty == 2
    assert ars_fix.event == 1

    # Chelsea is Away vs Arsenal
    che_fix = resolved["Chelsea"][0]
    assert che_fix.is_home is False
    assert che_fix.opponent_team_id == 1
    assert che_fix.opponent_name == "Arsenal"
    assert che_fix.difficulty == 4
    assert che_fix.event == 1


def test_resolve_team_upcoming_fixtures_double_gameweek_and_ordering() -> None:
    """Multiple fixtures in the same gameweek (Double GW) are preserved in kickoff order."""
    fixtures = [
        {
            "id": 102,
            "event": 25,
            "finished": False,
            "team_h": 1,
            "team_a": 3,
            "team_h_difficulty": 3,
            "team_a_difficulty": 3,
            "kickoff_time": "2026-02-15T15:00:00Z",
        },
        {
            "id": 101,
            "event": 25,
            "finished": False,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
            "kickoff_time": "2026-02-11T19:45:00Z",
        },
    ]
    resolved = resolve_team_upcoming_fixtures(fixtures, {1: "Arsenal", 2: "Chelsea", 3: "Liverpool"})

    assert len(resolved["Arsenal"]) == 2
    # Earlier kickoff fixture (101) comes first
    assert resolved["Arsenal"][0].fixture_id == 101
    assert resolved["Arsenal"][0].opponent_name == "Chelsea"
    assert resolved["Arsenal"][1].fixture_id == 102
    assert resolved["Arsenal"][1].opponent_name == "Liverpool"


def test_resolve_team_upcoming_fixtures_null_event_and_kickoff_safety() -> None:
    """Fixtures with event=None or kickoff_time=None do not crash and are retained safely."""
    fixtures = [
        {
            "id": 999,
            "event": None,
            "finished": False,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 3,
            "team_a_difficulty": 3,
            "kickoff_time": None,
        }
    ]
    resolved = resolve_team_upcoming_fixtures(fixtures, {1: "Arsenal", 2: "Chelsea"})

    assert len(resolved["Arsenal"]) == 1
    fix = resolved["Arsenal"][0]
    assert fix.fixture_id == 999
    assert fix.event is None
    assert fix.kickoff_time is None

