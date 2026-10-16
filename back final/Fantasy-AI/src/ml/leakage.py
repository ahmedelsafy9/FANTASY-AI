"""Leakage guards for feature matrices and temporal splits."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

LEAKY_SAME_GAMEWEEK_COLUMNS = (
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_missed",
    "penalties_saved",
    "red_cards",
    "yellow_cards",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "in_dreamteam",
    "starts",
    "total_points",
    "target",
)


@dataclass(frozen=True)
class LeakageReport:
    """Result of a leakage inspection."""

    ok: bool
    leaked_columns: tuple[str, ...]
    reasons: tuple[str, ...]


def inspect_feature_columns(
    feature_columns: list[str],
    target_column: str = "total_points",
) -> LeakageReport:
    """Fail if the target or same-gameweek outcomes are used as features."""
    leaked = [
        column
        for column in feature_columns
        if column == target_column or column in LEAKY_SAME_GAMEWEEK_COLUMNS
    ]
    reasons = tuple(f"column '{column}' is not available at prediction cutoff" for column in leaked)
    return LeakageReport(ok=not leaked, leaked_columns=tuple(leaked), reasons=reasons)


def assert_chronological_split(
    train_index: pd.Series,
    test_index: pd.Series,
) -> None:
    """Require every training key to be strictly before every test key."""
    if train_index.empty or test_index.empty:
        raise ValueError("Train and test windows must be non-empty.")
    if train_index.max() >= test_index.min():
        raise ValueError(
            "Temporal split leaked: training window is not strictly before the test window."
        )


def rolling_features_exclude_current(
    values: pd.Series,
    window: int,
) -> pd.Series:
    """Shift then roll so the current row cannot enter its own form features."""
    return values.shift(1).rolling(window=window, min_periods=1).mean()
