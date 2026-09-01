"""Tests for FeedbackAnalyzer."""

from __future__ import annotations

import pandas as pd
import pytest

from src.prediction.feedback.feedback_analyzer import FeedbackAnalyzer


@pytest.fixture
def sample_feedback():
    """Multi-GW feedback dataset for analysis."""
    rows = []
    for gw in range(1, 6):
        for i, (pos, team) in enumerate([
            ("DEF", "Team X"), ("MID", "Team X"),
            ("FWD", "Team Y"), ("GKP", "Team Y"),
            ("DEF", "Team Z"), ("MID", "Team Z"),
        ]):
            predicted = 3.0 + i * 0.5 + gw * 0.1
            # DEF systematically underpredicted, FWD overpredicted
            if pos == "DEF":
                actual = predicted + 2.0
            elif pos == "FWD":
                actual = predicted - 1.5
            else:
                actual = predicted + (0.5 if gw % 2 == 0 else -0.3)
            rows.append({
                "element": 100 + i,
                "name": f"Player_{i}",
                "team": team,
                "position": pos,
                "season": "2026-27",
                "GW": gw,
                "predicted_points": predicted,
                "actual_points": actual,
                "prediction_error": actual - predicted,
                "absolute_error": abs(actual - predicted),
                "squared_error": (actual - predicted) ** 2,
                "error_direction": (
                    "underprediction" if actual > predicted
                    else "overprediction" if actual < predicted
                    else "exact"
                ),
            })
    return pd.DataFrame(rows)


class TestGlobalMetrics:
    """Test global metric computation."""

    def test_metrics_not_nan(self, sample_feedback):
        metrics = FeedbackAnalyzer.compute_global_metrics(sample_feedback)
        assert metrics.n > 0
        assert not pd.isna(metrics.mae)
        assert not pd.isna(metrics.rmse)
        assert not pd.isna(metrics.spearman)
        assert not pd.isna(metrics.pearson)

    def test_mae_positive(self, sample_feedback):
        metrics = FeedbackAnalyzer.compute_global_metrics(sample_feedback)
        assert metrics.mae > 0

    def test_rmse_gte_mae(self, sample_feedback):
        metrics = FeedbackAnalyzer.compute_global_metrics(sample_feedback)
        assert metrics.rmse >= metrics.mae

    def test_rates_sum_to_one(self, sample_feedback):
        metrics = FeedbackAnalyzer.compute_global_metrics(sample_feedback)
        # Over + under should be close to 1 (minus exact matches)
        total = metrics.overprediction_rate + metrics.underprediction_rate
        assert total <= 1.0 + 1e-9

    def test_empty_input(self):
        metrics = FeedbackAnalyzer.compute_global_metrics(pd.DataFrame())
        assert metrics.n == 0

    def test_to_dict(self, sample_feedback):
        metrics = FeedbackAnalyzer.compute_global_metrics(sample_feedback)
        d = metrics.to_dict()
        assert "mae" in d
        assert "rmse" in d
        assert "r2" in d


class TestPlayerLevelAnalysis:
    """Test player-level error analysis."""

    def test_returns_categories(self, sample_feedback):
        result = FeedbackAnalyzer.player_level_analysis(sample_feedback)
        assert "biggest_underpredictions" in result
        assert "biggest_overpredictions" in result
        assert "largest_absolute_errors" in result

    def test_underpredictions_positive_error(self, sample_feedback):
        result = FeedbackAnalyzer.player_level_analysis(sample_feedback)
        under = result["biggest_underpredictions"]
        # The top entry should always have a positive error (underprediction)
        assert under.iloc[0]["prediction_error"] > 0

    def test_overpredictions_negative_error(self, sample_feedback):
        result = FeedbackAnalyzer.player_level_analysis(sample_feedback)
        over = result["biggest_overpredictions"]
        # The top entry should always have a negative error (overprediction)
        assert over.iloc[0]["prediction_error"] < 0

    def test_empty_input(self):
        result = FeedbackAnalyzer.player_level_analysis(pd.DataFrame())
        assert result == {}


class TestSegmentAnalysis:
    """Test segment-level error analysis."""

    def test_position_segments(self, sample_feedback):
        biases = FeedbackAnalyzer.segment_analysis(sample_feedback, "position")
        assert len(biases) > 0
        positions = {b.segment_value for b in biases}
        assert "DEF" in positions

    def test_def_underprediction_detected(self, sample_feedback):
        biases = FeedbackAnalyzer.segment_analysis(sample_feedback, "position")
        def_bias = next(b for b in biases if b.segment_value == "DEF")
        # DEF was systematically underpredicted (+2.0 error)
        assert def_bias.mean_signed_error > 1.0

    def test_fwd_overprediction_detected(self, sample_feedback):
        biases = FeedbackAnalyzer.segment_analysis(sample_feedback, "position")
        fwd_bias = next(b for b in biases if b.segment_value == "FWD")
        # FWD was systematically overpredicted (-1.5 error)
        assert fwd_bias.mean_signed_error < -1.0


class TestBiasDiscovery:
    """Test automatic bias discovery."""

    def test_discovers_biases(self, sample_feedback):
        biases = FeedbackAnalyzer.discover_biases(sample_feedback)
        assert len(biases) > 0

    def test_sorted_by_magnitude(self, sample_feedback):
        biases = FeedbackAnalyzer.discover_biases(sample_feedback)
        if len(biases) >= 2:
            assert abs(biases[0].mean_signed_error) >= abs(biases[1].mean_signed_error)
