"""Unit tests for Multi-Objective / Multi-Head FPL Player Scoring Integration."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.api.dependencies import get_prediction_query_service
from src.config.settings import Settings
from src.prediction.loader import LoadedModel, load_model
from src.prediction.multi_objective_scorer import (
    MultiObjectiveModel,
    ProbabilityCalibrator,
    load_multi_objective_model,
)
from src.prediction.predictor import PredictionService


@pytest.fixture
def multi_objective_loaded():
    """Fixture providing the loaded multi-objective model."""
    return load_multi_objective_model()


def test_multi_objective_model_loading(multi_objective_loaded):
    """Test 1: Multi-objective model loads all 4 heads + 3 calibrators correctly."""
    lm = multi_objective_loaded
    assert isinstance(lm, LoadedModel)
    assert lm.model_name == "multi_objective_score_d"
    assert lm.target_column == "total_points"
    assert len(lm.feature_columns) == 98

    model: MultiObjectiveModel = lm.model
    assert isinstance(model, MultiObjectiveModel)
    assert model.play_model is not None
    assert model.points_model is not None
    assert model.p6_model is not None
    assert model.p10_model is not None
    assert model.play_calibrator is not None
    assert model.p6_calibrator is not None
    assert model.p10_calibrator is not None
    assert model.alpha == 0.5
    assert model.beta == 0.25


def test_calibrators_validity_and_bounds(multi_objective_loaded):
    """Test 2: Calibrators are valid and produce calibrated probabilities bounded in [0, 1]."""
    model: MultiObjectiveModel = multi_objective_loaded.model
    test_probs = np.linspace(0.0, 1.0, 50)

    for name, calibrator in [
        ("play", model.play_calibrator),
        ("p6", model.p6_calibrator),
        ("p10", model.p10_calibrator),
    ]:
        calibrated = calibrator.predict(test_probs)
        assert calibrated.shape == test_probs.shape, f"{name} shape mismatch"
        assert np.all(calibrated >= 0.0), f"{name} produced negative probabilities"
        assert np.all(calibrated <= 1.0), f"{name} produced probabilities > 1.0"
        assert np.all(np.isfinite(calibrated)), f"{name} produced non-finite values"


def test_score_d_formula_verification():
    """Test 3: Score_D formula exactly equals P(play) * E(points|play) * (1 + 0.5*P6 + 0.25*P10)."""
    # Create mock heads with known constant outputs
    mock_play_model = MagicMock()
    mock_play_model.predict_proba.return_value = np.array([[0.2, 0.8]])  # P(play) = 0.8

    mock_points_model = MagicMock()
    mock_points_model.predict.return_value = np.array([4.0])  # E(points|play) = 4.0

    mock_p6_model = MagicMock()
    mock_p6_model.predict_proba.return_value = np.array([[0.7, 0.3]])  # P6 = 0.3

    mock_p10_model = MagicMock()
    mock_p10_model.predict_proba.return_value = np.array([[0.9, 0.1]])  # P10 = 0.1

    raw_calibrator = ProbabilityCalibrator(method="raw")

    mock_model = MultiObjectiveModel(
        play_model=mock_play_model,
        points_model=mock_points_model,
        p6_model=mock_p6_model,
        p10_model=mock_p10_model,
        play_calibrator=raw_calibrator,
        p6_calibrator=raw_calibrator,
        p10_calibrator=raw_calibrator,
        feature_columns=["f1", "f2"],
        train_medians={"f1": 0.0, "f2": 0.0},
        alpha=0.5,
        beta=0.25,
    )

    df = pd.DataFrame({"f1": [1.0], "f2": [2.0]})
    res = mock_model.predict_raw(df)

    expected_p_play = 0.8
    expected_exp_if_play = 4.0
    expected_p6 = 0.3
    expected_p10 = 0.1

    expected_score_a = expected_p_play * expected_exp_if_play  # 3.2
    expected_score_d = expected_score_a * (
        1.0 + 0.5 * expected_p6 + 0.25 * expected_p10
    )  # 3.2 * (1 + 0.15 + 0.025) = 3.2 * 1.175 = 3.76

    assert pytest.approx(res["p_play"][0]) == expected_p_play
    assert pytest.approx(res["expected_points_if_play"][0]) == expected_exp_if_play
    assert pytest.approx(res["p6"][0]) == expected_p6
    assert pytest.approx(res["p10"][0]) == expected_p10
    assert pytest.approx(res["expected_points"][0]) == expected_score_a
    assert pytest.approx(res["score_d"][0]) == expected_score_d
    assert pytest.approx(mock_model.predict(df)[0]) == expected_score_d


def test_missing_value_handling(multi_objective_loaded):
    """Test 4: Missing values (NaN) are safely imputed via medians without crashing."""
    lm = multi_objective_loaded
    # All NaNs DataFrame
    nan_df = pd.DataFrame({col: [np.nan, np.nan] for col in lm.feature_columns})
    pred = lm.model.predict(nan_df)
    assert len(pred) == 2
    assert np.all(np.isfinite(pred))

    # Partial NaNs with empty columns missing entirely from input
    sparse_df = pd.DataFrame({"element": [1, 2]})  # zero feature columns present
    sparse_pred = lm.model.predict(sparse_df)
    assert len(sparse_pred) == 2
    assert np.all(np.isfinite(sparse_pred))


def test_feature_ordering_consistency(multi_objective_loaded):
    """Test 5: Model produces identical output regardless of input column ordering."""
    lm = multi_objective_loaded
    cols = lm.feature_columns

    # Standard order
    data_dict = {col: [float(i % 7)] for i, col in enumerate(cols)}
    df_ordered = pd.DataFrame(data_dict)

    # Reversed order + extra metadata columns
    rev_cols = list(reversed(cols))
    data_dict_rev = {col: [float(i % 7)] for i, col in enumerate(cols)}
    data_dict_rev["extra_metadata"] = ["unrelated"]
    data_dict_rev["another_col"] = [999.0]
    df_reordered = pd.DataFrame(data_dict_rev)[["extra_metadata"] + rev_cols + ["another_col"]]

    pred_ordered = lm.model.predict(df_ordered)
    pred_reordered = lm.model.predict(df_reordered)

    np.testing.assert_allclose(pred_ordered, pred_reordered, rtol=1e-5, atol=1e-5)


def test_output_finite_and_valid_ranges(multi_objective_loaded):
    """Test 6: Outputs are finite, probabilities in [0, 1], and scores are non-negative."""
    lm = multi_objective_loaded
    test_df = pd.DataFrame({col: np.linspace(0, 10, 15) for col in lm.feature_columns})

    raw = lm.model.predict_raw(test_df)
    for key, val in raw.items():
        assert np.all(np.isfinite(val)), f"Non-finite value in {key}"

    assert np.all(raw["p_play"] >= 0.0) and np.all(raw["p_play"] <= 1.0)
    assert np.all(raw["p6"] >= 0.0) and np.all(raw["p6"] <= 1.0)
    assert np.all(raw["p10"] >= 0.0) and np.all(raw["p10"] <= 1.0)
    assert np.all(raw["score_d"] >= 0.0)


def test_production_fallback_configuration(monkeypatch):
    """Test 7: Production fallback via FANTASY_AI_SCORING_MODEL='production' works."""
    monkeypatch.setenv("FANTASY_AI_SCORING_MODEL", "production")
    settings = Settings()
    assert settings.prediction.scoring_model == "production"

    # Verify best_model.joblib is loadable as production model
    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = settings.paths.models_dir / "best_model_metadata.json"
    prod_model = load_model(model_path, metadata_path)
    assert prod_model.model_name != "multi_objective_score_d"


def test_api_predict_breakdown_schema_compatibility(multi_objective_loaded):
    """Test 8: predict_breakdown returns all required fields for API integration."""
    lm = multi_objective_loaded
    test_df = pd.DataFrame({col: [1.0] for col in lm.feature_columns})
    test_df["element"] = [101]

    breakdown = lm.model.predict_breakdown(test_df)

    required_fields = [
        "score_d",
        "play_probability",
        "conditional_expected_points",
        "p6_probability",
        "p10_probability",
        "predicted_total_points",
        "predicted_expected_points",
    ]
    for field in required_fields:
        assert field in breakdown.columns, f"Missing required breakdown column: {field}"

    # Verify PredictionService integrates seamlessly
    service = PredictionService(lm)
    res = service.predict(test_df)
    for field in required_fields:
        assert field in res.columns, f"Missing column in PredictionService output: {field}"
    assert res["predicted_total_points"].iloc[0] == pytest.approx(res["score_d"].iloc[0])


def test_match_prediction_model_untouched():
    """Test 9: Match prediction model is untouched and loads successfully."""
    from src.multi_stage.match_model import load_match_model

    multi_stage_dir = Path("models/multi_stage")
    assert multi_stage_dir.exists(), "Multi-stage match model dir must exist"
    assert (multi_stage_dir / "match_model.joblib").exists(), "Match model artifact missing"
    assert (multi_stage_dir / "match_model_metadata.json").exists(), "Match metadata artifact missing"

    model, meta = load_match_model(multi_stage_dir)
    assert model is not None, "Failed to load match model"
    assert meta is not None and "feature_cols" in meta, "Match model metadata missing feature_cols"
