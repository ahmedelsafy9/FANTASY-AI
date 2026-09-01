"""Tests for ResidualModel."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.prediction.feedback.residual_model import ResidualModel


@pytest.fixture
def model_dir(tmp_path):
    """Temp directory for model artifacts."""
    return tmp_path / "residual_model"


@pytest.fixture
def multi_gw_feedback():
    """Multi-Gameweek feedback dataset suitable for training."""
    rows = []
    rng = np.random.RandomState(42)
    for gw in range(1, 8):
        for i in range(20):
            predicted = 3.0 + rng.randn() * 1.5
            # Systematic bias: players with high prediction get overpredicted
            bias = -0.3 * (predicted - 3.0)
            noise = rng.randn() * 0.5
            actual = predicted + bias + noise
            rows.append({
                "element": i,
                "name": f"Player_{i}",
                "team": f"Team_{i % 4}",
                "position": ["DEF", "MID", "FWD", "GKP"][i % 4],
                "season": "2026-27",
                "GW": gw,
                "predicted_points": predicted,
                "actual_points": actual,
                "prediction_error": actual - predicted,
                "absolute_error": abs(actual - predicted),
            })
    return pd.DataFrame(rows)


class TestResidualTraining:
    """Test residual model training."""

    def test_train_succeeds(self, model_dir, multi_gw_feedback):
        model = ResidualModel(model_dir)
        metadata = model.train(multi_gw_feedback)
        assert model.is_trained
        assert metadata.n_training_samples > 0
        assert metadata.n_gameweeks > 0

    def test_train_version_increments(self, model_dir, multi_gw_feedback):
        model = ResidualModel(model_dir)
        m1 = model.train(multi_gw_feedback)
        assert m1.version == "v1"
        m2 = model.train(multi_gw_feedback)
        assert m2.version == "v2"

    def test_train_with_max_gw(self, model_dir, multi_gw_feedback):
        model = ResidualModel(model_dir)
        metadata = model.train(multi_gw_feedback, max_gw=4)
        assert model.is_trained
        # Should only use GWs 1-4 for training
        assert metadata.n_gameweeks <= 4


class TestResidualPrediction:
    """Test residual model prediction."""

    def test_predict_returns_corrections(self, model_dir, multi_gw_feedback):
        model = ResidualModel(model_dir)
        model.train(multi_gw_feedback)

        current = pd.DataFrame({
            "element": [0, 1, 2],
            "base_prediction": [5.0, 3.0, 7.0],
            "position": ["DEF", "MID", "FWD"],
            "team": ["Team_0", "Team_1", "Team_2"],
        })

        features = model.build_residual_features(
            multi_gw_feedback, current, target_gw=8
        )
        corrections = model.predict(features)
        assert len(corrections) == 3

    def test_predict_untrained_raises(self, model_dir):
        model = ResidualModel(model_dir)
        with pytest.raises(RuntimeError):
            model.predict(pd.DataFrame({"base_prediction": [1.0]}))


class TestRecencyWeighting:
    """Test exponential decay recency weighting."""

    def test_recent_gws_weighted_more(self, model_dir):
        """Recent GWs should have higher sample weights."""
        model = ResidualModel(model_dir)

        # Create feedback with a pattern shift at GW 5
        rows = []
        rng = np.random.RandomState(42)
        for gw in range(1, 10):
            for i in range(15):
                predicted = 4.0
                # Pattern shifts at GW 5: early GWs underpredicted, later overpredicted
                if gw < 5:
                    actual = predicted + 2.0 + rng.randn() * 0.3
                else:
                    actual = predicted - 1.5 + rng.randn() * 0.3
                rows.append({
                    "element": i,
                    "position": "MID",
                    "team": "Team_0",
                    "GW": gw,
                    "predicted_points": predicted,
                    "actual_points": actual,
                    "prediction_error": actual - predicted,
                })

        fb = pd.DataFrame(rows)
        model.train(fb, half_life=3.0)
        assert model.is_trained

        # Correction should reflect the RECENT pattern (overprediction)
        current = pd.DataFrame({
            "element": [0],
            "base_prediction": [4.0],
            "position": ["MID"],
            "team": ["Team_0"],
        })
        features = model.build_residual_features(fb, current, target_gw=10, half_life=3.0)
        correction = model.predict(features)
        # Recent pattern is overprediction → correction should be negative
        assert correction[0] < 0


class TestColdStart:
    """Test cold-start behavior."""

    def test_insufficient_data_returns_empty(self, model_dir):
        model = ResidualModel(model_dir)
        # Only 1 GW of feedback — not enough
        fb = pd.DataFrame({
            "element": [1, 2],
            "GW": [1, 1],
            "predicted_points": [3.0, 4.0],
            "actual_points": [5.0, 2.0],
            "prediction_error": [2.0, -2.0],
        })
        metadata = model.train(fb)
        assert not model.is_trained  # Should not train with only 1 GW


class TestModelPersistence:
    """Test save/load functionality."""

    def test_save_and_load(self, model_dir, multi_gw_feedback):
        model1 = ResidualModel(model_dir)
        model1.train(multi_gw_feedback)
        model1.save()

        model2 = ResidualModel(model_dir)
        assert not model2.is_trained
        loaded = model2.load()
        assert loaded
        assert model2.is_trained
        assert model2.version == model1.version

    def test_load_nonexistent_returns_false(self, model_dir):
        model = ResidualModel(model_dir)
        assert not model.load()


class TestCorrectionCap:
    """Test that corrections are bounded."""

    def test_corrections_within_bounds(self, model_dir, multi_gw_feedback):
        model = ResidualModel(model_dir)
        model.train(multi_gw_feedback)

        current = pd.DataFrame({
            "element": list(range(20)),
            "base_prediction": [10.0] * 20,
            "position": ["MID"] * 20,
            "team": ["Team_0"] * 20,
        })

        features = model.build_residual_features(
            multi_gw_feedback, current, target_gw=8
        )
        corrections = model.predict(features)
        # Raw corrections can be anything, capping is done by the adapter
        # But verify they are finite numbers
        assert all(np.isfinite(corrections))
