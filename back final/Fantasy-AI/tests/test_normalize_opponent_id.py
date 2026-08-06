"""Unit tests for src.preprocessing.steps.normalize_opponent_id."""

from __future__ import annotations

import pandas as pd

from src.preprocessing.steps.normalize_opponent_id import NormalizeOpponentIdStep


def test_resolves_numeric_opponent_ids_to_names() -> None:
    """With a mapping, numeric opponent IDs must be resolved to team names."""
    df = pd.DataFrame({"opponent_team": [11, 6]})
    step = NormalizeOpponentIdStep(
        opponent_column="opponent_team", team_id_mapping={11: "Arsenal", 6: "Chelsea"}
    )
    result, summary = step.apply(df)
    assert result["opponent_team"].tolist() == ["Arsenal", "Chelsea"]
    assert "Resolved 2" in summary.description


def test_is_a_noop_without_a_mapping() -> None:
    """With no mapping, the column must be left completely unchanged."""
    df = pd.DataFrame({"opponent_team": [11, 6]})
    step = NormalizeOpponentIdStep(opponent_column="opponent_team", team_id_mapping=None)
    result, summary = step.apply(df)
    assert result["opponent_team"].tolist() == [11, 6]
    assert "No team ID mapping" in summary.description


def test_is_a_noop_when_column_absent() -> None:
    """A missing opponent column must not raise — the step is simply a no-op."""
    df = pd.DataFrame({"other": [1, 2]})
    step = NormalizeOpponentIdStep(
        opponent_column="opponent_team", team_id_mapping={11: "Arsenal"}
    )
    result, summary = step.apply(df)
    assert "not present" in summary.description
    assert len(result) == 2


def test_preserves_row_count() -> None:
    """This step must never add or remove rows."""
    df = pd.DataFrame({"opponent_team": [11, 6, 999]})
    step = NormalizeOpponentIdStep(
        opponent_column="opponent_team", team_id_mapping={11: "Arsenal", 6: "Chelsea"}
    )
    result, summary = step.apply(df)
    assert len(result) == 3
    assert summary.rows_before == summary.rows_after == 3
