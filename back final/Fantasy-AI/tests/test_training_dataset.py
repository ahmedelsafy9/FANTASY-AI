"""Unit tests for src.training.dataset."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config.settings import TrainingSettings
from src.training.dataset import (
    _season_sort_key,
    _build_recency_weights,
    prepare_split_dataset,
    select_feature_columns,
)


# =====================================================================
# select_feature_columns tests (unchanged)
# =====================================================================


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


# =====================================================================
# _season_sort_key tests
# =====================================================================


def test_season_sort_key_parses_standard_format() -> None:
    """Standard YYYY-YY season strings must parse to the start year."""
    assert _season_sort_key("2022-23") == 2022
    assert _season_sort_key("2016-17") == 2016
    assert _season_sort_key("2025-26") == 2025
    assert _season_sort_key("1999-00") == 1999


def test_season_sort_key_returns_none_for_invalid() -> None:
    """Non-season strings must return None."""
    assert _season_sort_key("2022") is None
    assert _season_sort_key("not-a-season") is None
    assert _season_sort_key("") is None
    assert _season_sort_key("22-23") is None
    assert _season_sort_key("2022-234") is None


# =====================================================================
# _build_recency_weights tests
# =====================================================================


def _make_multi_season_df() -> pd.DataFrame:
    """Three-season dataset with 5 rows per season."""
    rows = []
    for season in ["2020-21", "2021-22", "2022-23"]:
        for gw in range(1, 6):
            rows.append({
                "season": season,
                "GW": gw,
                "total_points": float(gw),
                "minutes": 90.0,
            })
    return pd.DataFrame(rows)


def test_recency_weights_string_seasons() -> None:
    """Multi-season YYYY-YY dataset must produce correct linear weights."""
    df = _make_multi_season_df()  # 15 rows, 3 seasons
    settings = TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=("element",),
        season_weight_max=3.0,
        season_weight_min=1.0,
    )

    # Use all 15 rows as "training", full dataset = same
    weights = _build_recency_weights(
        train_df=df,
        all_data=df,
        settings=settings,
    )

    assert len(weights) == 15

    # 3 seasons, linear: 2020-21=1.0, 2021-22=2.0, 2022-23=3.0
    season_2020 = weights.iloc[0:5]
    season_2021 = weights.iloc[5:10]
    season_2022 = weights.iloc[10:15]

    assert season_2020.to_list() == pytest.approx([1.0] * 5)
    assert season_2021.to_list() == pytest.approx([2.0] * 5)
    assert season_2022.to_list() == pytest.approx([3.0] * 5)


def test_recency_weights_single_season() -> None:
    """A single season must receive the maximum weight."""
    df = pd.DataFrame({
        "season": ["2022-23"] * 5,
        "GW": list(range(1, 6)),
        "total_points": [1.0] * 5,
    })
    settings = TrainingSettings(
        target_column="total_points",
        season_weight_max=3.0,
        season_weight_min=1.0,
    )

    weights = _build_recency_weights(
        train_df=df,
        all_data=df,
        settings=settings,
    )

    assert weights.to_list() == pytest.approx([3.0] * 5)


def test_recency_weights_missing_season_column() -> None:
    """When the season column is absent, all weights must be 1.0."""
    df = pd.DataFrame({
        "GW": [1, 2, 3],
        "total_points": [1.0, 2.0, 3.0],
    })
    settings = TrainingSettings(target_column="total_points")

    weights = _build_recency_weights(
        train_df=df,
        all_data=df,
        settings=settings,
    )

    assert weights.to_list() == pytest.approx([1.0] * 3)


def test_recency_weights_custom_settings() -> None:
    """Custom season_weight_max/min must be respected."""
    df = _make_multi_season_df()
    settings = TrainingSettings(
        target_column="total_points",
        season_weight_max=5.0,
        season_weight_min=2.0,
    )

    weights = _build_recency_weights(
        train_df=df,
        all_data=df,
        settings=settings,
    )

    # 3 seasons, linear: 2020-21=2.0, 2021-22=3.5, 2022-23=5.0
    assert weights.iloc[0] == pytest.approx(2.0)
    assert weights.iloc[5] == pytest.approx(3.5)
    assert weights.iloc[10] == pytest.approx(5.0)


def test_recency_weights_latest_season_only_in_test() -> None:
    """When the latest season is only in the full dataset (test split),
    training weights should still be assigned correctly for older seasons,
    and no max-weight rows should exist in training."""
    all_data = _make_multi_season_df()  # 3 seasons

    # Train only on the first two seasons (10 rows)
    train_df = all_data.iloc[:10].copy()

    settings = TrainingSettings(
        target_column="total_points",
        season_weight_max=3.0,
        season_weight_min=1.0,
    )

    weights = _build_recency_weights(
        train_df=train_df,
        all_data=all_data,
        settings=settings,
    )

    # No training row should have the max weight (3.0)
    # because 2022-23 is only in the test set
    assert weights.max() < 3.0

    # 2020-21 should be 1.0, 2021-22 should be 2.0
    assert weights.iloc[0:5].to_list() == pytest.approx([1.0] * 5)
    assert weights.iloc[5:10].to_list() == pytest.approx([2.0] * 5)


# =====================================================================
# prepare_split_dataset tests (unchanged)
# =====================================================================


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


def test_prepare_split_dataset_multi_season_weights() -> None:
    """End-to-end: prepare_split_dataset with multiple seasons produces
    non-uniform weights for training rows."""
    rows = []
    for season in ["2020-21", "2021-22", "2022-23"]:
        for gw in range(1, 11):
            rows.append({
                "season": season,
                "GW": gw,
                "total_points": float(gw),
                "minutes": 90.0,
            })
    df = pd.DataFrame(rows)  # 30 rows

    settings = TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=(),
        chronological_columns=("season", "GW"),
        test_fraction=0.2,
        season_weight_max=3.0,
        season_weight_min=1.0,
    )
    split = prepare_split_dataset(df, settings)

    # Weights should not all be 1.0 — the bug is fixed
    assert split.train_weights.max() > 1.0
    # The latest season in the training set should have higher weight
    assert split.train_weights.min() < split.train_weights.max()
