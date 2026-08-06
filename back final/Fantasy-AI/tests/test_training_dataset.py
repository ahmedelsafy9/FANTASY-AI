"""Unit tests for src.training.dataset."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config.settings import TrainingSettings
from src.training.dataset import prepare_split_dataset, select_feature_columns


def test_select_feature_columns_excludes_target_and_excluded_columns() -> None:
    """The target column and explicitly excluded columns must never be selected."""
    df = pd.DataFrame(
        {
            "season": ["2022-23"],
            "name": ["A"],
            "total_points": [10],
            "minutes": [90],
            "form_index": [5.0],
        }
    )
    settings = TrainingSettings(
        target_column="total_points", excluded_feature_columns=("season", "name")
    )
    features = select_feature_columns(df, settings)
    assert "total_points" not in features
    assert "season" not in features
    assert "name" not in features
    assert "minutes" in features
    assert "form_index" in features


def test_select_feature_columns_excludes_normalized_join_key_columns() -> None:
    """Any column ending in '_normalized' must be excluded automatically."""
    df = pd.DataFrame({"total_points": [10], "name_normalized": ["a"], "minutes": [90]})
    settings = TrainingSettings(target_column="total_points", excluded_feature_columns=())
    features = select_feature_columns(df, settings)
    assert "name_normalized" not in features
    assert "minutes" in features


def test_select_feature_columns_excludes_non_numeric_columns() -> None:
    """Text columns must never be selected as features."""
    df = pd.DataFrame({"total_points": [10], "team": ["Arsenal"], "minutes": [90]})
    settings = TrainingSettings(target_column="total_points", excluded_feature_columns=())
    features = select_feature_columns(df, settings)
    assert "team" not in features
    assert "minutes" in features


def test_select_feature_columns_includes_boolean_columns() -> None:
    """Boolean feature columns (e.g. is_home) must be selected."""
    df = pd.DataFrame({"total_points": [10], "is_home": [True]})
    settings = TrainingSettings(target_column="total_points", excluded_feature_columns=())
    features = select_feature_columns(df, settings)
    assert "is_home" in features


def test_default_settings_exclude_same_gameweek_outcome_stats_to_prevent_leakage() -> None:
    """Regression guard: the DEFAULT excluded_feature_columns must exclude every
    same-Gameweek raw outcome stat (minutes, goals, assists, bonus, bps, ict_index,
    etc.) — these are only known AFTER a match is played, and total_points is a
    near-deterministic function of several of them under FPL's own scoring rules.
    Using them unlagged as features previously let a model trivially reconstruct
    the target instead of learning anything predictive (verified empirically:
    R^2 ~0.995 with these columns present vs. a realistic score without them).
    This test exists so that gap can never silently reappear.
    """
    df = pd.DataFrame(
        {
            "total_points": [10],
            "minutes": [90],
            "goals_scored": [1],
            "assists": [0],
            "bonus": [2],
            "bps": [30],
            "ict_index": [8.5],
            "clean_sheets": [1],
            "goals_conceded": [0],
            "saves": [0],
            "yellow_cards": [0],
            "GW": [1],
            "was_home": [True],
            "value": [55],
        }
    )
    settings = TrainingSettings(target_column="total_points")  # use the real default
    features = select_feature_columns(df, settings)

    leaky_columns = {
        "minutes", "goals_scored", "assists", "bonus", "bps", "ict_index",
        "clean_sheets", "goals_conceded", "saves", "yellow_cards",
    }
    assert leaky_columns.isdisjoint(features), (
        f"Same-Gameweek outcome stat(s) leaked into default feature selection: "
        f"{leaky_columns & set(features)}"
    )
    # Legitimate pre-match-known columns must still be selected.
    assert {"GW", "was_home", "value"}.issubset(features)


def _build_chronological_df(n_players: int = 2, n_gws: int = 10) -> pd.DataFrame:
    rows = []
    for player in range(n_players):
        for gw in range(1, n_gws + 1):
            rows.append(
                {
                    "season": "2022-23",
                    "GW": gw,
                    "element": player,
                    "total_points": float(gw + player),
                    "minutes": 90.0,
                }
            )
    return pd.DataFrame(rows)


def test_prepare_split_dataset_splits_chronologically() -> None:
    """The test split must contain only the most recent rows by GW."""
    df = _build_chronological_df(n_players=1, n_gws=10)
    settings = TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=("element",),
        chronological_columns=("season", "GW"),
        test_fraction=0.2,
    )
    split = prepare_split_dataset(df, settings)

    assert len(split.X_train) + len(split.X_test) == len(df)
    assert len(split.X_test) == 2  # 20% of 10 rows


def test_prepare_split_dataset_raises_on_missing_target() -> None:
    """A missing target column must raise a clear ValueError."""
    df = pd.DataFrame({"minutes": [90]})
    settings = TrainingSettings(target_column="total_points")
    with pytest.raises(ValueError):
        prepare_split_dataset(df, settings)


def test_prepare_split_dataset_drops_rows_with_missing_target() -> None:
    """Rows with a missing target value must be dropped before splitting."""
    df = _build_chronological_df(n_players=1, n_gws=10)
    df.loc[0, "total_points"] = np.nan
    settings = TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=("element",),
        chronological_columns=("season", "GW"),
        test_fraction=0.2,
    )
    split = prepare_split_dataset(df, settings)
    assert len(split.X_train) + len(split.X_test) == len(df) - 1


def test_prepare_split_dataset_imputes_missing_features_with_train_median() -> None:
    """Missing feature values must be filled using the training split's median."""
    df = _build_chronological_df(n_players=1, n_gws=10)
    df.loc[0, "minutes"] = np.nan  # in the training portion
    settings = TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=("element",),
        chronological_columns=("season", "GW"),
        test_fraction=0.2,
    )
    split = prepare_split_dataset(df, settings)
    assert not split.X_train["minutes"].isna().any()
    assert split.train_medians["minutes"] == pytest.approx(90.0)
