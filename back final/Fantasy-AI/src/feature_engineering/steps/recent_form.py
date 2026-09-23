"""Recent-form feature engineering step (Configuration F).

Implements the winning feature configuration established by the Recent-Form
Representation Experiment and subsequent Ablation Study:

    Baseline features (98)
    + Raw Recent observations (112: 14 variables x [L3, L5] x lag k)
    + Volatility features (16: 8 metrics x [L3, L5])
    = 226 total production features

CRITICAL LEAKAGE SAFETY:
- All features use ONLY current-season data via `groupby([season, player])`.
- Features never cross season boundaries.
- Every observation is strictly lagged (k >= 1), ensuring that match t features
  depend only on information available strictly prior to match t.
"""

from __future__ import annotations

import warnings
from typing import Sequence

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key, resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)

RAW_FORM_VARIABLES: list[str] = [
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "bonus",
    "bps",
    "xP",
    "ict_index",
    "influence",
    "creativity",
    "threat",
    "expected_goals",
    "expected_assists",
]

WINDOWS: list[int] = [3, 5]

VOLATILITY_METRIC_NAMES: list[str] = [
    "high_score_6_count",
    "double_digit_count",
    "blank_count",
    "returns_count",
    "consistency_ratio",
    "pts_std",
    "pts_range",
    "minutes_std",
]


def _resolve_player_column(
    candidates: Sequence[str],
    data: pd.DataFrame,
) -> str:
    """Resolve the player identifier column present in the dataset."""
    for c in candidates:
        if c in data.columns:
            return c
    raise ValueError(f"No player identifier column found among {candidates}")


def build_raw_recent_values(
    df: pd.DataFrame,
    variables: list[str] = RAW_FORM_VARIABLES,
    windows: list[int] = WINDOWS,
    player_id_columns: Sequence[str] = ("name_normalized", "name", "element"),
) -> pd.DataFrame:
    """Derive individual GW-minus-k observations.

    Strictly groups by [season, player] and shifts by k >= 1 to prevent leakage
    and cross-season carry-over.
    """
    player_col = _resolve_player_column(player_id_columns, df)
    working = df.copy()
    new_cols: dict[str, pd.Series] = {}

    season_col = "season" if "season" in working.columns else None
    group_keys = (
        [working[season_col], working[player_col]]
        if season_col is not None
        else working[player_col]
    )

    for var in variables:
        if var not in working.columns:
            continue
        numeric_var = pd.to_numeric(working[var], errors="coerce")
        for window in windows:
            for k in range(1, window + 1):
                col_name = f"rf_{var}_L{window}_GW_minus_{k}"
                shifted = numeric_var.groupby(group_keys).shift(k)
                new_cols[col_name] = shifted

    return pd.concat([working, pd.DataFrame(new_cols, index=working.index)], axis=1)


def build_volatility_features(
    df: pd.DataFrame,
    windows: list[int] = WINDOWS,
    player_id_columns: Sequence[str] = ("name_normalized", "name", "element"),
) -> pd.DataFrame:
    """Stability and volatility features for total_points and minutes.

    Computes:
    - high_score_6_count (points >= 6)
    - double_digit_count (points >= 10)
    - blank_count (points <= 2)
    - returns_count (points >= 4)
    - consistency_ratio (returns / valid_matches)
    - pts_std (ddof=1)
    - pts_range (max - min)
    - minutes_std (ddof=1)
    over recent completed match windows, strictly before the current match.
    """
    player_col = _resolve_player_column(player_id_columns, df)
    working = df.copy()
    new_cols: dict[str, pd.Series] = {}

    pts_var = "total_points"
    min_var = "minutes"
    if pts_var not in working.columns:
        return working

    season_col = "season" if "season" in working.columns else None
    group_keys = (
        [working[season_col], working[player_col]]
        if season_col is not None
        else working[player_col]
    )

    pts_numeric = pd.to_numeric(working[pts_var], errors="coerce")
    min_numeric = (
        pd.to_numeric(working[min_var], errors="coerce")
        if min_var in working.columns
        else None
    )

    for window in windows:
        prefix = f"rf_vol_L{window}"
        pts_shifted = []
        min_shifted = []
        for k in range(1, window + 1):
            s = pts_numeric.groupby(group_keys).shift(k)
            pts_shifted.append(s.values)
            if min_numeric is not None:
                ms = min_numeric.groupby(group_keys).shift(k)
                min_shifted.append(ms.values)

        pts_matrix = np.column_stack(list(reversed(pts_shifted)))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            high_score_6 = np.nansum(pts_matrix >= 6, axis=1).astype(float)
            double_digit = np.nansum(pts_matrix >= 10, axis=1).astype(float)
            blank_count = np.nansum(pts_matrix <= 2, axis=1).astype(float)
            returns_count = np.nansum(pts_matrix >= 4, axis=1).astype(float)
            valid_count = np.sum(~np.isnan(pts_matrix), axis=1).astype(float)
            consistency = np.where(valid_count > 0, returns_count / valid_count, np.nan)
            pts_std = np.nanstd(pts_matrix, axis=1, ddof=1)
            pts_range = np.nanmax(pts_matrix, axis=1) - np.nanmin(pts_matrix, axis=1)

        new_cols[f"{prefix}_high_score_6_count"] = pd.Series(high_score_6, index=working.index)
        new_cols[f"{prefix}_double_digit_count"] = pd.Series(double_digit, index=working.index)
        new_cols[f"{prefix}_blank_count"] = pd.Series(blank_count, index=working.index)
        new_cols[f"{prefix}_returns_count"] = pd.Series(returns_count, index=working.index)
        new_cols[f"{prefix}_consistency_ratio"] = pd.Series(consistency, index=working.index)
        new_cols[f"{prefix}_pts_std"] = pd.Series(pts_std, index=working.index)
        new_cols[f"{prefix}_pts_range"] = pd.Series(pts_range, index=working.index)

        if min_shifted:
            min_matrix = np.column_stack(list(reversed(min_shifted)))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                min_std = np.nanstd(min_matrix, axis=1, ddof=1)
            new_cols[f"{prefix}_minutes_std"] = pd.Series(min_std, index=working.index)

    return pd.concat([working, pd.DataFrame(new_cols, index=working.index)], axis=1)


class RecentFormStep(FeatureStep):
    """Derives Configuration F recent-form features (Raw Recent + Volatility).

    Appends:
    - 112 raw recent features: GW_minus_k observations across 14 stats.
    - 16 volatility features: stability/consistency metrics across L3 and L5.
    Total: 128 new features.
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...] = ("name_normalized", "name", "element"),
        chronological_columns: tuple[str, ...] = ("season", "GW"),
        variables: list[str] = RAW_FORM_VARIABLES,
        windows: list[int] = WINDOWS,
    ) -> None:
        self._player_id_columns = player_id_columns
        self._chronological_columns = chronological_columns
        self._variables = variables
        self._windows = windows

    @property
    def name(self) -> str:
        return "recent_form"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        rows_before = len(data)
        player_id_column = resolve_column(self._player_id_columns, data)
        sort_columns = chronological_sort_key(data, self._chronological_columns)

        if player_id_column is None:
            logger.warning(
                "No player identifier column found among %s; skipping recent form.",
                self._player_id_columns,
            )
            return data, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=rows_before,
                columns_added=[],
                description="No player identifier column available; skipped.",
            )

        working = data.copy()
        working["__recent_form_orig_idx__"] = range(len(working))
        sort_by = [player_id_column, *sort_columns]
        working = working.sort_values(by=sort_by, kind="mergesort")

        working = build_raw_recent_values(
            working,
            variables=self._variables,
            windows=self._windows,
            player_id_columns=(player_id_column,),
        )
        working = build_volatility_features(
            working,
            windows=self._windows,
            player_id_columns=(player_id_column,),
        )

        working = working.sort_values(by="__recent_form_orig_idx__", kind="mergesort").drop(
            columns=["__recent_form_orig_idx__"]
        )

        added = [c for c in working.columns if c not in data.columns]
        logger.info("RecentFormStep added %d feature columns.", len(added))

        return working, FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=added,
            description=f"Derived {len(added)} recent form features (Configuration F).",
        )


def _load_production_features_f() -> tuple[str, ...]:
    """Build the single authoritative production feature schema of 226 features."""
    # 98 baseline features in exact production order
    baseline_98 = [
        "value",
        "was_home",
        "GW",
        "total_points_avg_last_3",
        "total_points_avg_last_5",
        "total_points_avg_last_10",
        "minutes_avg_last_3",
        "minutes_avg_last_5",
        "minutes_avg_last_10",
        "bps_avg_last_3",
        "bps_avg_last_5",
        "bps_avg_last_10",
        "ict_index_avg_last_3",
        "ict_index_avg_last_5",
        "ict_index_avg_last_10",
        "xG_avg_last_3",
        "xG_avg_last_5",
        "xG_avg_last_10",
        "xA_avg_last_3",
        "xA_avg_last_5",
        "xA_avg_last_10",
        "threat_avg_last_3",
        "threat_avg_last_5",
        "threat_avg_last_10",
        "creativity_avg_last_3",
        "creativity_avg_last_5",
        "creativity_avg_last_10",
        "influence_avg_last_3",
        "influence_avg_last_5",
        "influence_avg_last_10",
        "goals_scored_avg_last_3",
        "goals_scored_avg_last_5",
        "assists_avg_last_3",
        "assists_avg_last_5",
        "bonus_avg_last_3",
        "bonus_avg_last_5",
        "key_passes_avg_last_3",
        "key_passes_avg_last_5",
        "big_chances_created_avg_last_3",
        "big_chances_created_avg_last_5",
        "big_chances_missed_avg_last_3",
        "big_chances_missed_avg_last_5",
        "is_position_gkp",
        "is_position_def",
        "is_position_mid",
        "is_position_fwd",
        "prev_gw_minutes",
        "prev_gw_played",
        "prev_gw_started",
        "prev_gw_bench_unused",
        "starts_last_3",
        "bench_unused_last_3",
        "starts_last_5",
        "bench_unused_last_5",
        "is_promoted_team",
        "opponent_is_promoted_team",
        "prev_season_minutes",
        "prev_season_points",
        "prev_season_matches",
        "prev_season_ppm",
        "player_is_new_to_pl",
        "team_attack_strength",
        "team_defence_strength",
        "opponent_attack_strength",
        "opponent_defence_strength",
        "fixture_difficulty",
        "clean_sheet_likelihood",
        "threat_per_90_last_5",
        "creativity_per_90_last_5",
        "bps_per_90_last_5",
        "goal_involvement_rate_last_5",
        "attacking_threat_index",
        "xG_per_90_last_5",
        "xA_per_90_last_5",
        "key_passes_per_90_last_5",
        "big_chances_created_per_90_last_5",
        "big_chances_missed_rate_last_5",
        "xGI_per_90_last_5",
        "opportunity_index_last_5",
        "minutes_std_last_5",
        "minutes_share_last_5",
        "rotation_risk_index",
        "consecutive_starts",
        "consecutive_60_plus",
        "consecutive_90s",
        "expected_minutes",
        "minutes_prev_7d",
        "matches_prev_7d",
        "minutes_prev_14d",
        "matches_prev_14d",
        "is_home",
        "rest_days",
        "team_strength",
        "opponent_strength",
        "team_form_trend",
        "price_trend_last_1",
        "price_trend_last_5",
        "form_index",
    ]

    # 112 raw recent features in exact ablation order
    raw_112: list[str] = []
    for var in RAW_FORM_VARIABLES:
        for w in WINDOWS:
            for k in range(1, w + 1):
                raw_112.append(f"rf_{var}_L{w}_GW_minus_{k}")

    # 16 volatility features in exact ablation order
    vol_16: list[str] = []
    for w in WINDOWS:
        p = f"rf_vol_L{w}"
        for metric in VOLATILITY_METRIC_NAMES:
            vol_16.append(f"{p}_{metric}")

    all_226 = tuple(baseline_98 + raw_112 + vol_16)
    assert len(all_226) == 226, f"Expected 226 features, got {len(all_226)}"
    assert len(set(all_226)) == 226, "Duplicate feature names in PRODUCTION_FEATURES_F"
    return all_226


PRODUCTION_FEATURES_F: tuple[str, ...] = _load_production_features_f()
