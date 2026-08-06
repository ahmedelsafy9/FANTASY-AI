"""Unit tests for individual validation checks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.validation.checks.data_types import DataTypeCheck
from src.validation.checks.duplicate_rows import DuplicateRowsCheck
from src.validation.checks.gameweek import GameweekCheck
from src.validation.checks.missing_values import MissingValuesCheck
from src.validation.checks.player_id import PlayerIdCheck


# --- MissingValuesCheck ------------------------------------------------------


def test_missing_values_passes_when_required_columns_complete() -> None:
    """The check must pass when required columns have no missing values."""
    df = pd.DataFrame({"season": ["2022-23", "2022-23"], "name": ["A", "B"]})
    check = MissingValuesCheck(required_columns=("season", "name"))
    result = check.run(df)
    assert result.passed is True
    assert result.total_issue_count == 0


def test_missing_values_fails_when_required_column_has_nulls() -> None:
    """The check must fail when a required column contains missing values."""
    df = pd.DataFrame({"season": ["2022-23", None], "name": ["A", "B"]})
    check = MissingValuesCheck(required_columns=("season", "name"))
    result = check.run(df)
    assert result.passed is False
    assert any("REQUIRED" in issue.description for issue in result.issues)


def test_missing_values_reports_but_does_not_fail_on_optional_columns() -> None:
    """Missing values in a non-required column must not fail the check."""
    df = pd.DataFrame({"season": ["2022-23", "2022-23"], "bonus": [1, None]})
    check = MissingValuesCheck(required_columns=("season",))
    result = check.run(df)
    assert result.passed is True
    assert result.total_issue_count == 1


# --- DuplicateRowsCheck -------------------------------------------------------


def test_duplicate_rows_passes_for_unique_data() -> None:
    """The check must pass when no rows are duplicated."""
    df = pd.DataFrame(
        {"season": ["2022-23", "2022-23"], "name": ["A", "B"], "GW": [1, 1]}
    )
    check = DuplicateRowsCheck(key_columns=("season", "name", "GW"))
    result = check.run(df)
    assert result.passed is True


def test_duplicate_rows_detects_full_duplicates() -> None:
    """The check must detect fully identical rows."""
    df = pd.DataFrame(
        {"season": ["2022-23", "2022-23"], "name": ["A", "A"], "GW": [1, 1]}
    )
    check = DuplicateRowsCheck(key_columns=("season", "name", "GW"))
    result = check.run(df)
    assert result.passed is False
    assert result.total_issue_count >= 1


def test_duplicate_rows_detects_key_duplicates_with_different_other_columns() -> None:
    """The check must detect duplicate logical keys even if other columns differ."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23"],
            "name": ["A", "A"],
            "GW": [1, 1],
            "minutes": [90, 45],
        }
    )
    check = DuplicateRowsCheck(key_columns=("season", "name", "GW"))
    result = check.run(df)
    assert result.passed is False


# --- DataTypeCheck -------------------------------------------------------------


def test_data_types_passes_for_clean_numeric_columns() -> None:
    """The check must pass when numeric columns parse cleanly."""
    df = pd.DataFrame({"total_points": [1, 2, 3], "minutes": [90, 45, 0]})
    check = DataTypeCheck(expected_numeric_columns=("total_points", "minutes"))
    result = check.run(df)
    assert result.passed is True


def test_data_types_flags_non_numeric_value() -> None:
    """The check must flag a non-numeric value in an expected-numeric column."""
    df = pd.DataFrame({"total_points": [1, "abc", 3]})
    check = DataTypeCheck(expected_numeric_columns=("total_points",))
    result = check.run(df)
    assert result.passed is False
    assert result.total_issue_count == 1
    assert result.issues[0].column == "total_points"


def test_data_types_ignores_missing_expected_column() -> None:
    """The check must not fail if an expected column is simply absent."""
    df = pd.DataFrame({"other": [1, 2]})
    check = DataTypeCheck(expected_numeric_columns=("total_points",))
    result = check.run(df)
    assert result.passed is True


# --- GameweekCheck -------------------------------------------------------------


def test_gameweek_passes_for_valid_range() -> None:
    """The check must pass when all Gameweek values are within range."""
    df = pd.DataFrame({"GW": [1, 19, 38]})
    check = GameweekCheck(gameweek_columns=("GW", "round"), min_gameweek=1, max_gameweek=38)
    result = check.run(df)
    assert result.passed is True


def test_gameweek_flags_out_of_range_values() -> None:
    """The check must flag Gameweek values outside the configured range."""
    df = pd.DataFrame({"GW": [0, 1, 39]})
    check = GameweekCheck(gameweek_columns=("GW", "round"), min_gameweek=1, max_gameweek=38)
    result = check.run(df)
    assert result.passed is False
    assert result.total_issue_count == 2


def test_gameweek_uses_fallback_column_when_primary_absent() -> None:
    """The check must fall back to the next candidate column if the first is absent."""
    df = pd.DataFrame({"round": [1, 2, 3]})
    check = GameweekCheck(gameweek_columns=("GW", "round"), min_gameweek=1, max_gameweek=38)
    result = check.run(df)
    assert result.passed is True


def test_gameweek_skips_gracefully_when_no_column_present() -> None:
    """The check must pass trivially and note the skip when no GW column exists."""
    df = pd.DataFrame({"unrelated": [1, 2]})
    check = GameweekCheck(gameweek_columns=("GW", "round"), min_gameweek=1, max_gameweek=38)
    result = check.run(df)
    assert result.passed is True
    assert "skipped" in result.summary


# --- PlayerIdCheck -------------------------------------------------------------


def test_player_id_passes_for_valid_numeric_ids() -> None:
    """The check must pass for positive, non-missing numeric identifiers."""
    df = pd.DataFrame({"element": [1, 2, 3]})
    check = PlayerIdCheck(player_id_columns=("element", "name"))
    result = check.run(df)
    assert result.passed is True


def test_player_id_flags_non_positive_numeric_ids() -> None:
    """The check must flag zero, negative, or missing numeric identifiers."""
    df = pd.DataFrame({"element": [1, 0, -5, np.nan]})
    check = PlayerIdCheck(player_id_columns=("element", "name"))
    result = check.run(df)
    assert result.passed is False
    assert result.total_issue_count == 3


def test_player_id_flags_blank_string_ids() -> None:
    """The check must flag blank or missing string identifiers."""
    df = pd.DataFrame({"name": ["Salah", "  ", None]})
    check = PlayerIdCheck(player_id_columns=("element", "name"))
    result = check.run(df)
    assert result.passed is False
    assert result.total_issue_count == 2
