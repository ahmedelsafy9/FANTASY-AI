"""Tests for FeedbackAdapter."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config.settings import FeedbackSettings
from src.prediction.feedback.feedback_adapter import FeedbackAdapter
from src.prediction.feedback.feedback_store import FeedbackStore
from src.prediction.feedback.residual_model import ResidualModel


@pytest.fixture
def stores(tmp_path):
    """Create feedback infrastructure."""
    feedback_dir = tmp_path / "feedback"
    model_dir = tmp_path / "model"
    feedback_store = FeedbackStore(feedback_dir)
    residual_model = ResidualModel(model_dir)
    settings = FeedbackSettings()
    return feedback_store, residual_model, settings


@pytest.fixture
def base_predictions():
    """Sample base predictions."""
    return pd.DataFrame({
        "element": [1, 2, 3, 4, 5],
        "name": ["A", "B", "C", "D", "E"],
        "team": ["T1", "T1", "T2", "T2", "T3"],
        "position": ["DEF", "MID", "FWD", "GKP", "DEF"],
        "predicted_total_points": [3.5, 6.2, 4.1, 2.0, 5.5],
    })


def _seed_feedback(feedback_store, n_gws=5, n_players=10):
    """Create multiple GWs of feedback for testing."""
    rng = np.random.RandomState(42)
    for gw in range(1, n_gws + 1):
        snapshot = pd.DataFrame({
            "element": list(range(n_players)),
            "base_prediction": [3.0 + rng.randn() for _ in range(n_players)],
            "model_name": ["dl"] * n_players,
        })
        actual = pd.DataFrame({
            "element": list(range(n_players)),
            "season": ["2026-27"] * n_players,
            "GW": [gw] * n_players,
            "total_points": [p + 1.0 + rng.randn() * 0.5 for p in snapshot["base_prediction"]],
        })
        feedback_store.generate_feedback(snapshot, actual, "2026-27", gw)


class TestColdStart:
    """Test cold-start behavior: insufficient feedback → no correction."""

    def test_no_feedback_returns_base(self, stores, base_predictions):
        feedback_store, residual_model, settings = stores
        adapter = FeedbackAdapter(feedback_store, residual_model, settings)

        result = adapter.apply_correction(
            base_predictions, "2026-27", 2
        )

        assert "feedback_correction" in result.columns
        assert "final_prediction" in result.columns
        assert all(result["feedback_correction"] == 0.0)
        assert all(result["feedback_confidence"] == 0.0)
        # Final prediction = base prediction when no feedback
        assert list(result["final_prediction"]) == list(result["base_prediction"])

    def test_insufficient_gameweeks(self, stores, base_predictions):
        feedback_store, residual_model, settings = stores
        # Only 1 GW of feedback (need 3)
        _seed_feedback(feedback_store, n_gws=1)
        adapter = FeedbackAdapter(feedback_store, residual_model, settings)

        result = adapter.apply_correction(
            base_predictions, "2026-27", 2
        )
        assert all(result["feedback_correction"] == 0.0)


class TestCorrectionApplication:
    """Test that corrections are properly applied when sufficient feedback exists."""

    def test_correction_applied_with_sufficient_feedback(self, stores, base_predictions):
        feedback_store, residual_model, settings = stores
        _seed_feedback(feedback_store, n_gws=5, n_players=20)

        adapter = FeedbackAdapter(feedback_store, residual_model, settings)
        # Train the model first
        adapter.update_model("2026-27", 5)

        result = adapter.apply_correction(
            base_predictions, "2026-27", 6
        )

        # Some corrections should be non-zero
        assert "feedback_correction" in result.columns
        assert "final_prediction" in result.columns
        # Final = base + correction
        np.testing.assert_array_almost_equal(
            result["final_prediction"].values,
            result["base_prediction"].values + result["feedback_correction"].values,
        )

    def test_correction_cap_enforced(self, stores, base_predictions):
        feedback_store, residual_model, settings = stores
        _seed_feedback(feedback_store, n_gws=5, n_players=20)

        adapter = FeedbackAdapter(feedback_store, residual_model, settings)
        adapter.update_model("2026-27", 5)

        result = adapter.apply_correction(
            base_predictions, "2026-27", 6
        )

        max_corr = settings.max_correction
        assert all(result["feedback_correction"].abs() <= max_corr + 1e-9)


class TestOutputColumns:
    """Test that output has all required columns."""

    def test_required_columns_present(self, stores, base_predictions):
        feedback_store, residual_model, settings = stores
        adapter = FeedbackAdapter(feedback_store, residual_model, settings)

        result = adapter.apply_correction(
            base_predictions, "2026-27", 2
        )

        required = [
            "base_prediction",
            "feedback_correction",
            "final_prediction",
            "feedback_confidence",
            "base_model_version",
            "feedback_model_version",
        ]
        for col in required:
            assert col in result.columns, f"Missing output column: {col}"

    def test_base_prediction_preserved(self, stores, base_predictions):
        """The original base prediction must never be overwritten."""
        feedback_store, residual_model, settings = stores
        adapter = FeedbackAdapter(feedback_store, residual_model, settings)

        result = adapter.apply_correction(
            base_predictions, "2026-27", 2
        )
        assert list(result["base_prediction"]) == [3.5, 6.2, 4.1, 2.0, 5.5]


class TestModelUpdate:
    """Test residual model training via adapter."""

    def test_update_with_sufficient_data(self, stores):
        feedback_store, residual_model, settings = stores
        _seed_feedback(feedback_store, n_gws=5, n_players=20)

        adapter = FeedbackAdapter(feedback_store, residual_model, settings)
        success = adapter.update_model("2026-27", 5)
        assert success
        assert residual_model.is_trained

    def test_update_with_insufficient_data(self, stores):
        feedback_store, residual_model, settings = stores
        # Only 1 GW — below min_feedback_gameweeks
        _seed_feedback(feedback_store, n_gws=1)

        adapter = FeedbackAdapter(feedback_store, residual_model, settings)
        success = adapter.update_model("2026-27", 1)
        assert not success
