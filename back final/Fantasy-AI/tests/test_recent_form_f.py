"""Comprehensive automated test suite for Configuration F recent-form representation.

Tests cover:
1. Exactly 226 F features.
2. No duplicate feature names.
3. Exactly 98 baseline features.
4. Exactly 112 raw recent features.
5. Exactly 16 volatility features.
6. Exact feature-name and ordering equality with ablation F inventory.
7. Season boundary isolation (Season A matches never leak into Season B).
8. GW1 insufficient-history behavior (all recent-form features are NaN).
9. GW2/GW3 history behavior (GW2 has lag 1, GW3 has lags 1 and 2, etc.).
10. Current-match leakage safety: modifying match t outcome does not change match t features.
11. Future-match leakage safety: modifying match t+1 outcome does not change match t features.
12. Legitimate previous-match dependency: modifying match t-1 changes match t features.
13. Deterministic repeated execution.
14. Inference schema mismatch raises PredictionError.
15. Correct feature ordering validation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.core.exceptions import PredictionError
from src.feature_engineering.steps.recent_form import (
    PRODUCTION_FEATURES_F,
    RAW_FORM_VARIABLES,
    WINDOWS,
    VOLATILITY_METRIC_NAMES,
    RecentFormStep,
    build_raw_recent_values,
    build_volatility_features,
)
from src.prediction.loader import LoadedModel
from src.prediction.predictor import PredictionService


# ---------------------------------------------------------------------------
# 1-6. Schema, Counts, Uniqueness, Exact Equality
# ---------------------------------------------------------------------------

def test_feature_count_is_exactly_226() -> None:
    """Assert PRODUCTION_FEATURES_F has exactly 226 features."""
    assert len(PRODUCTION_FEATURES_F) == 226


def test_no_duplicate_feature_names() -> None:
    """Assert all feature names in PRODUCTION_FEATURES_F are unique."""
    assert len(set(PRODUCTION_FEATURES_F)) == len(PRODUCTION_FEATURES_F)


def test_required_groups_counts() -> None:
    """Assert schema contains exactly 98 baseline, 112 raw recent, and 16 volatility features."""
    raw_recent = [f for f in PRODUCTION_FEATURES_F if f.startswith("rf_") and "GW_minus" in f]
    volatility = [f for f in PRODUCTION_FEATURES_F if f.startswith("rf_vol_")]
    baseline = [f for f in PRODUCTION_FEATURES_F if f not in set(raw_recent) and f not in set(volatility)]

    assert len(baseline) == 98, f"Expected 98 baseline, got {len(baseline)}"
    assert len(raw_recent) == 112, f"Expected 112 raw recent, got {len(raw_recent)}"
    assert len(volatility) == 16, f"Expected 16 volatility, got {len(volatility)}"
    assert len(baseline) + len(raw_recent) + len(volatility) == 226


def test_exact_feature_equality_with_ablation_inventory() -> None:
    """Verify exact match with models/experiments/recent_form_ablation/feature_groups.csv."""
    from pathlib import Path

    csv_path = Path("models/experiments/recent_form_ablation/feature_groups.csv")
    if not csv_path.exists():
        pytest.skip("feature_groups.csv not found for ablation")

    df = pd.read_csv(csv_path)
    f_df = df[df["config"] == "F_Volatility"]
    ablation_features = f_df["feature"].tolist()

    assert len(ablation_features) == 226
    assert list(PRODUCTION_FEATURES_F) == ablation_features


# ---------------------------------------------------------------------------
# 7-9. Season Boundary & In-Season History Behavior
# ---------------------------------------------------------------------------

def test_season_boundary_isolation() -> None:
    """Verify that current-season features NEVER consume previous-season matches."""
    # Synthetic player across Season A and Season B
    df = pd.DataFrame(
        {
            "name_normalized": ["salah"] * 4,
            "season": ["2025-26", "2025-26", "2025-26", "2026-27"],
            "GW": [1, 2, 3, 1],
            "total_points": [2, 2, 20, 1],
            "minutes": [90, 90, 90, 90],
            "goals_scored": [0, 0, 3, 0],
            "assists": [0, 0, 1, 0],
            "clean_sheets": [0, 0, 0, 0],
            "bonus": [0, 0, 3, 0],
            "bps": [10, 10, 50, 10],
            "xP": [2.0, 2.0, 12.0, 2.0],
            "ict_index": [5.0, 5.0, 25.0, 5.0],
            "influence": [10.0, 10.0, 80.0, 10.0],
            "creativity": [10.0, 10.0, 50.0, 10.0],
            "threat": [10.0, 10.0, 90.0, 10.0],
            "expected_goals": [0.1, 0.1, 1.5, 0.1],
            "expected_assists": [0.0, 0.0, 0.5, 0.0],
        }
    )

    step = RecentFormStep()
    res, _ = step.apply(df)

    # For Season B GW1 (row index 3), no matches have occurred in 2026-27
    row_b_gw1 = res[(res["season"] == "2026-27") & (res["GW"] == 1)].iloc[0]

    # All raw recent features must be NaN
    for var in RAW_FORM_VARIABLES:
        for w in WINDOWS:
            for k in range(1, w + 1):
                col = f"rf_{var}_L{w}_GW_minus_{k}"
                assert pd.isna(row_b_gw1[col]), f"Expected NaN for {col} in Season B GW1, got {row_b_gw1[col]}"

    # Volatility counts should be 0, std/range/consistency should be NaN
    for w in WINDOWS:
        p = f"rf_vol_L{w}"
        assert row_b_gw1[f"{p}_high_score_6_count"] == 0.0
        assert row_b_gw1[f"{p}_double_digit_count"] == 0.0
        assert row_b_gw1[f"{p}_blank_count"] == 0.0
        assert row_b_gw1[f"{p}_returns_count"] == 0.0
        assert pd.isna(row_b_gw1[f"{p}_consistency_ratio"])
        assert pd.isna(row_b_gw1[f"{p}_pts_std"])
        assert pd.isna(row_b_gw1[f"{p}_pts_range"])
        assert pd.isna(row_b_gw1[f"{p}_minutes_std"])


def test_gw1_gw2_gw3_history_progression() -> None:
    """Verify exact history progression through GW1, GW2, and GW3."""
    df = pd.DataFrame(
        {
            "name_normalized": ["haaland"] * 3,
            "season": ["2026-27"] * 3,
            "GW": [1, 2, 3],
            "total_points": [13, 17, 2],
            "minutes": [90, 90, 90],
            "goals_scored": [2, 3, 0],
            "assists": [0, 0, 0],
            "clean_sheets": [1, 1, 0],
            "bonus": [3, 3, 0],
            "bps": [45, 60, 8],
            "xP": [8.0, 9.0, 7.0],
            "ict_index": [15.0, 20.0, 3.0],
            "influence": [60.0, 80.0, 5.0],
            "creativity": [10.0, 10.0, 5.0],
            "threat": [70.0, 90.0, 10.0],
            "expected_goals": [1.2, 1.8, 0.2],
            "expected_assists": [0.1, 0.0, 0.0],
        }
    )

    step = RecentFormStep()
    res, _ = step.apply(df)

    # GW1: all lags must be NaN
    gw1 = res[res["GW"] == 1].iloc[0]
    assert pd.isna(gw1["rf_total_points_L3_GW_minus_1"])
    assert pd.isna(gw1["rf_total_points_L3_GW_minus_2"])
    assert pd.isna(gw1["rf_total_points_L3_GW_minus_3"])

    # GW2: lag 1 should be GW1 points (13), lag 2 should be NaN
    gw2 = res[res["GW"] == 2].iloc[0]
    assert gw2["rf_total_points_L3_GW_minus_1"] == 13.0
    assert pd.isna(gw2["rf_total_points_L3_GW_minus_2"])
    assert pd.isna(gw2["rf_total_points_L3_GW_minus_3"])

    # GW3: lag 1 should be GW2 points (17), lag 2 should be GW1 points (13), lag 3 should be NaN
    gw3 = res[res["GW"] == 3].iloc[0]
    assert gw3["rf_total_points_L3_GW_minus_1"] == 17.0
    assert gw3["rf_total_points_L3_GW_minus_2"] == 13.0
    assert pd.isna(gw3["rf_total_points_L3_GW_minus_3"])

    # GW3 Volatility: completed matches before GW3 are GW1 (13) and GW2 (17)
    # high_score_6_count should be 2 (both 13 and 17 are >= 6)
    assert gw3["rf_vol_L3_high_score_6_count"] == 2.0
    assert gw3["rf_vol_L3_double_digit_count"] == 2.0
    assert gw3["rf_vol_L3_blank_count"] == 0.0
    # pts_range: 17 - 13 = 4
    assert gw3["rf_vol_L3_pts_range"] == 4.0


# ---------------------------------------------------------------------------
# 10-12. Rigorous Multi-Stage Leakage Tests
# ---------------------------------------------------------------------------

def test_rigorous_leakage_checks() -> None:
    """Rigorous leakage test as mandated by Critical Correction #5:

    1. Generate features from original history.
    2. Modify match t outcome -> match t features MUST remain unchanged.
    3. Modify match t+1 outcome -> match t features MUST remain unchanged.
    4. Modify match t-1 outcome -> match t features legitimately depending on t-1 MUST change.
    """
    base_data = pd.DataFrame(
        {
            "name_normalized": ["palmer"] * 5,
            "season": ["2026-27"] * 5,
            "GW": [1, 2, 3, 4, 5],
            "total_points": [5, 10, 3, 12, 6],
            "minutes": [90, 85, 75, 90, 90],
            "goals_scored": [0, 1, 0, 1, 0],
            "assists": [1, 1, 0, 1, 1],
            "clean_sheets": [0, 1, 0, 0, 1],
            "bonus": [0, 2, 0, 3, 0],
            "bps": [18, 35, 12, 42, 20],
            "xP": [4.0, 7.0, 3.5, 8.0, 5.0],
            "ict_index": [8.0, 14.0, 4.0, 16.0, 9.0],
            "influence": [25.0, 45.0, 10.0, 55.0, 30.0],
            "creativity": [35.0, 40.0, 15.0, 45.0, 35.0],
            "threat": [20.0, 35.0, 10.0, 40.0, 20.0],
            "expected_goals": [0.2, 0.6, 0.1, 0.7, 0.2],
            "expected_assists": [0.3, 0.4, 0.1, 0.5, 0.3],
        }
    )

    step = RecentFormStep()

    # Step 1: Generate original features
    res_orig, _ = step.apply(base_data)
    # Consider match t = GW3 (index 2)
    t_idx = 2
    orig_t_features = res_orig.iloc[t_idx].to_dict()

    # Step 2: Modify match t outcome (change GW3 total_points from 3 to 99)
    mod_t = base_data.copy()
    mod_t.loc[t_idx, "total_points"] = 99
    mod_t.loc[t_idx, "goals_scored"] = 10
    res_mod_t, _ = step.apply(mod_t)
    mod_t_features = res_mod_t.iloc[t_idx].to_dict()

    # All rf_ features for match t MUST be identical to original
    for feat in PRODUCTION_FEATURES_F:
        if feat.startswith("rf_"):
            orig_val = orig_t_features[feat]
            mod_val = mod_t_features[feat]
            if pd.isna(orig_val):
                assert pd.isna(mod_val), f"Leakage: {feat} at match t changed from NaN to {mod_val}"
            else:
                assert orig_val == mod_val, f"Leakage: {feat} at match t changed from {orig_val} to {mod_val}"

    # Step 3: Modify match t+1 outcome (change GW4 total_points from 12 to 88)
    mod_t_plus_1 = base_data.copy()
    mod_t_plus_1.loc[t_idx + 1, "total_points"] = 88
    res_mod_t_plus_1, _ = step.apply(mod_t_plus_1)
    mod_t1_features = res_mod_t_plus_1.iloc[t_idx].to_dict()

    for feat in PRODUCTION_FEATURES_F:
        if feat.startswith("rf_"):
            orig_val = orig_t_features[feat]
            mod_val = mod_t1_features[feat]
            if pd.isna(orig_val):
                assert pd.isna(mod_val), f"Future Leakage: {feat} at match t changed from NaN to {mod_val}"
            else:
                assert orig_val == mod_val, f"Future Leakage: {feat} at match t changed from {orig_val} to {mod_val}"

    # Step 4: Modify match t-1 outcome (change GW2 total_points from 10 to 999)
    mod_t_minus_1 = base_data.copy()
    mod_t_minus_1.loc[t_idx - 1, "total_points"] = 999
    res_mod_t_minus_1, _ = step.apply(mod_t_minus_1)
    mod_tm1_features = res_mod_t_minus_1.iloc[t_idx].to_dict()

    # Features that depend on GW2 (lag 1 for GW3) MUST change legitimately
    assert mod_tm1_features["rf_total_points_L3_GW_minus_1"] == 999.0
    assert orig_t_features["rf_total_points_L3_GW_minus_1"] == 10.0
    assert mod_tm1_features["rf_total_points_L3_GW_minus_1"] != orig_t_features["rf_total_points_L3_GW_minus_1"]

    # Features that depend only on GW1 (lag 2 for GW3) MUST remain unchanged
    assert mod_tm1_features["rf_total_points_L3_GW_minus_2"] == orig_t_features["rf_total_points_L3_GW_minus_2"]


# ---------------------------------------------------------------------------
# 13. Determinism
# ---------------------------------------------------------------------------

def test_determinism_on_identical_input() -> None:
    """Running RecentFormStep twice on identical input produces identical output."""
    data = pd.DataFrame(
        {
            "name_normalized": ["watkins"] * 3,
            "season": ["2026-27"] * 3,
            "GW": [1, 2, 3],
            "total_points": [5, 8, 2],
            "minutes": [90, 80, 70],
            "goals_scored": [0, 1, 0],
            "assists": [1, 0, 0],
            "clean_sheets": [0, 0, 0],
            "bonus": [0, 2, 0],
            "bps": [15, 25, 6],
            "xP": [4.0, 5.0, 4.0],
            "ict_index": [6.0, 10.0, 2.0],
            "influence": [20.0, 35.0, 5.0],
            "creativity": [20.0, 15.0, 5.0],
            "threat": [25.0, 40.0, 8.0],
            "expected_goals": [0.3, 0.5, 0.1],
            "expected_assists": [0.2, 0.1, 0.0],
        }
    )

    step = RecentFormStep()
    res1, _ = step.apply(data)
    res2, _ = step.apply(data)

    pd.testing.assert_frame_equal(res1, res2)


# ---------------------------------------------------------------------------
# 14-15. Inference Schema Validation
# ---------------------------------------------------------------------------

class _DummyModel:
    def predict(self, X):
        return np.zeros(len(X))


def test_inference_schema_validation_catches_mismatch() -> None:
    """PredictionService must raise clear PredictionError when schema is violated."""
    dummy_model = _DummyModel()
    loaded_model = LoadedModel(
        model=dummy_model,
        model_name="test_model",
        feature_columns=list(PRODUCTION_FEATURES_F),
        target_column="total_points",
        train_medians={f: 0.0 for f in PRODUCTION_FEATURES_F},
        metrics={},
    )
    svc = PredictionService(loaded_model)

    # Missing column test
    malformed_rows = pd.DataFrame({"value": [50.0], "was_home": [1.0]})
    with pytest.raises(PredictionError, match="Feature schema mismatch"):
        svc.predict(malformed_rows)


def test_inference_schema_validation_passes_with_exact_schema() -> None:
    """PredictionService succeeds when all 226 features are provided in correct schema."""
    dummy_model = _DummyModel()
    loaded_model = LoadedModel(
        model=dummy_model,
        model_name="test_model",
        feature_columns=list(PRODUCTION_FEATURES_F),
        target_column="total_points",
        train_medians={f: 0.0 for f in PRODUCTION_FEATURES_F},
        metrics={},
    )
    svc = PredictionService(loaded_model)

    valid_rows = pd.DataFrame([{f: 1.0 for f in PRODUCTION_FEATURES_F}])
    pred = svc.predict(valid_rows)
    assert "predicted_total_points" in pred.columns
    assert len(pred) == 1
