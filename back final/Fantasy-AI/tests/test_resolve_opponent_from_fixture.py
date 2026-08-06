"""Unit tests for ResolveOpponentFromFixtureStep."""

from __future__ import annotations

import pandas as pd
import pytest

from src.preprocessing.steps.resolve_opponent_from_fixture import ResolveOpponentFromFixtureStep


def test_resolves_opponent_from_two_team_fixture() -> None:
    """A fixture with exactly 2 teams must resolve each row's opponent correctly."""
    df = pd.DataFrame(
        {
            "season": ["2022-23"] * 4,
            "fixture": [1, 1, 1, 1],
            "team": ["Arsenal", "Arsenal", "Chelsea", "Chelsea"],
            "opponent_team": [6, 6, 1, 1],  # numeric IDs — should be overwritten
            "total_points": [10, 8, 5, 3],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, summary = step.apply(df)

    arsenal_rows = result[result["team"] == "Arsenal"]
    chelsea_rows = result[result["team"] == "Chelsea"]

    assert (arsenal_rows["opponent_team"] == "Chelsea").all()
    assert (chelsea_rows["opponent_team"] == "Arsenal").all()
    assert "4/4" in summary.description  # all 4 rows resolved


def test_handles_multiple_fixtures_per_season() -> None:
    """Multiple fixtures in the same season must resolve independently."""
    df = pd.DataFrame(
        {
            "season": ["2022-23"] * 4,
            "fixture": [1, 1, 2, 2],
            "team": ["Arsenal", "Chelsea", "Liverpool", "Spurs"],
            "opponent_team": [6, 1, 18, 11],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    assert result.iloc[0]["opponent_team"] == "Chelsea"
    assert result.iloc[1]["opponent_team"] == "Arsenal"
    assert result.iloc[2]["opponent_team"] == "Spurs"
    assert result.iloc[3]["opponent_team"] == "Liverpool"


def test_handles_cross_season_fixture_id_reuse() -> None:
    """Same fixture ID in different seasons must resolve independently."""
    df = pd.DataFrame(
        {
            "season": ["2021-22", "2021-22", "2022-23", "2022-23"],
            "fixture": [1, 1, 1, 1],
            "team": ["Leeds", "Man City", "Arsenal", "Chelsea"],
            "opponent_team": [1, 2, 1, 2],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    assert result.iloc[0]["opponent_team"] == "Man City"
    assert result.iloc[1]["opponent_team"] == "Leeds"
    assert result.iloc[2]["opponent_team"] == "Chelsea"
    assert result.iloc[3]["opponent_team"] == "Arsenal"


def test_skips_fixture_with_not_two_teams() -> None:
    """A fixture with ≠ 2 teams (anomaly) must leave opponent_team unchanged."""
    df = pd.DataFrame(
        {
            "season": ["2022-23"] * 3,
            "fixture": [1, 1, 1],
            "team": ["Arsenal", "Chelsea", "Liverpool"],  # 3 teams = anomaly
            "opponent_team": [6, 1, 14],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    # Original values should be preserved (as objects, since dtype is cast).
    assert result.iloc[0]["opponent_team"] == 6
    assert result.iloc[1]["opponent_team"] == 1
    assert result.iloc[2]["opponent_team"] == 14


def test_skips_rows_with_missing_season_or_fixture() -> None:
    """Rows with missing season or fixture must be left unchanged."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", None, "2022-23"],
            "fixture": [1, 1, None],
            "team": ["Arsenal", "Chelsea", "Liverpool"],
            "opponent_team": [6, 1, 14],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    # Only the first row can potentially be resolved, but since its
    # fixture group only has one team (Arsenal, because Chelsea's
    # season is None), it's an anomalous fixture and won't resolve.
    # All values should remain as original.
    assert result.iloc[0]["opponent_team"] == 6
    assert result.iloc[1]["opponent_team"] == 1
    assert result.iloc[2]["opponent_team"] == 14


def test_noop_when_columns_missing() -> None:
    """Missing required columns must produce a no-op with a descriptive summary."""
    df = pd.DataFrame({"name": ["Player 1"], "total_points": [10]})
    step = ResolveOpponentFromFixtureStep()
    result, summary = step.apply(df)

    assert "missing column" in summary.description.lower()
    assert len(result) == len(df)


def test_preserves_already_correct_team_names() -> None:
    """If opponent_team already has team names, fixture resolution overwrites with the correct one."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23"],
            "fixture": [1, 1],
            "team": ["Arsenal", "Chelsea"],
            "opponent_team": ["Chelsea", "Arsenal"],  # already correct names
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    assert result.iloc[0]["opponent_team"] == "Chelsea"
    assert result.iloc[1]["opponent_team"] == "Arsenal"


def test_creates_opponent_column_if_absent() -> None:
    """If opponent_team column doesn't exist, the step should create it."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23"],
            "fixture": [1, 1],
            "team": ["Arsenal", "Chelsea"],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    assert "opponent_team" in result.columns
    assert result.iloc[0]["opponent_team"] == "Chelsea"
    assert result.iloc[1]["opponent_team"] == "Arsenal"


def test_no_team_mapped_to_itself() -> None:
    """A team must never be resolved as its own opponent."""
    df = pd.DataFrame(
        {
            "season": ["2022-23"] * 4,
            "fixture": [1, 1, 2, 2],
            "team": ["Arsenal", "Chelsea", "Arsenal", "Liverpool"],
            "opponent_team": [1, 2, 3, 4],
        }
    )
    step = ResolveOpponentFromFixtureStep()
    result, _ = step.apply(df)

    for _, row in result.iterrows():
        if pd.notna(row["opponent_team"]) and isinstance(row["opponent_team"], str):
            assert row["team"] != row["opponent_team"], (
                f"Team '{row['team']}' was mapped to itself in fixture {row['fixture']}"
            )
