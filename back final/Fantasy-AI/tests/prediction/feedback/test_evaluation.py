"""Tests for walk-forward evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.prediction.feedback.evaluation import FeedbackEvaluator, ComparisonResult


@pytest.fixture
def multi_gw_feedback():
    """Multi-GW feedback for evaluation."""
    rows = []
    rng = np.random.RandomState(42)
    for gw in range(1, 10):
        for i in range(30):
            predicted = 3.0 + rng.randn() * 2.0
            # Systematic underprediction + noise
            actual = predicted + 0.8 + rng.randn() * 1.0
            rows.append({
                "element": i,
                "season": "2026-27",
                "GW": gw,
                "predicted_points": predicted,
                "actual_points": actual,
                "prediction_error": actual - predicted,
            })
    return pd.DataFrame(rows)


class TestWalkForwardEvaluation:
    """Test walk-forward evaluation logic."""

    def test_returns_comparison_result(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        assert isinstance(result, ComparisonResult)

    def test_both_metrics_computed(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        assert result.baseline_metrics.n > 0
        assert result.adaptive_metrics.n > 0

    def test_per_gw_results_populated(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        assert not result.per_gw_results.empty
        assert "GW" in result.per_gw_results.columns
        assert "baseline_mae" in result.per_gw_results.columns
        assert "adaptive_mae" in result.per_gw_results.columns

    def test_n_gameweeks_correct(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        assert result.n_gameweeks == 9

    def test_empty_feedback(self):
        result = FeedbackEvaluator.evaluate_from_feedback(pd.DataFrame())
        assert result.n_gameweeks == 0

    def test_insufficient_gameweeks(self):
        fb = pd.DataFrame({
            "element": [1, 2],
            "GW": [1, 1],
            "predicted_points": [3.0, 4.0],
            "actual_points": [5.0, 2.0],
            "prediction_error": [2.0, -2.0],
        })
        result = FeedbackEvaluator.evaluate_from_feedback(fb, min_gameweeks=3)
        assert result.n_gameweeks == 0


class TestHighScoreMetrics:
    """Test high-score prediction quality."""

    def test_high_score_metrics_present(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        assert len(result.baseline_high_scores) > 0
        assert len(result.adaptive_high_scores) > 0

    def test_metrics_have_precision_recall(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        for hs in result.baseline_high_scores:
            assert hasattr(hs, "precision")
            assert hasattr(hs, "recall")
            assert hasattr(hs, "f1")
            assert hasattr(hs, "hit_rate")


class TestComparisonFormat:
    """Test formatted output."""

    def test_format_produces_string(self, multi_gw_feedback):
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        formatted = FeedbackEvaluator.format_comparison(result)
        assert isinstance(formatted, str)
        assert "Baseline" in formatted
        assert "Adaptive" in formatted
        assert "MAE" in formatted

    def test_temporal_ordering_in_per_gw(self, multi_gw_feedback):
        """Walk-forward must process GWs in chronological order."""
        result = FeedbackEvaluator.evaluate_from_feedback(multi_gw_feedback)
        gws = result.per_gw_results["GW"].values
        assert list(gws) == sorted(gws)
