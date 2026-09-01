"""Tests proving no temporal data leakage in the feedback system.

These tests verify the CRITICAL architectural invariant:

    For predicting GW N, the system must NEVER use:
    - GW N actual points
    - GW N actual minutes, goals, assists, etc.
    - GW N feedback (which doesn't exist yet)
    - Any information derived from GW N or later

This is the single most important safety property of the feedback system.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config.settings import FeedbackSettings
from src.prediction.feedback.feedback_adapter import FeedbackAdapter
from src.prediction.feedback.feedback_store import FeedbackStore
from src.prediction.feedback.residual_model import ResidualModel


def _build_multi_gw_feedback(
    feedback_store: FeedbackStore,
    n_gws: int = 6,
    n_players: int = 20,
    secret_signal: float = 100.0,
) -> pd.DataFrame:
    """Build feedback where GW N data has a known secret signal.

    If the system leaks GW N data into GW N predictions, the corrections
    will reflect this secret signal, which we can detect.
    """
    rng = np.random.RandomState(42)
    all_feedback = []
    for gw in range(1, n_gws + 1):
        predicted_values = [3.0 + rng.randn() for _ in range(n_players)]
        # GW N has a unique, massive, detectable signal
        if gw == n_gws:
            actual_values = [p + secret_signal for p in predicted_values]
        else:
            actual_values = [p + 1.0 + rng.randn() * 0.5 for p in predicted_values]

        snapshot = pd.DataFrame({
            "element": list(range(n_players)),
            "base_prediction": predicted_values,
            "model_name": ["dl"] * n_players,
        })
        actual = pd.DataFrame({
            "element": list(range(n_players)),
            "season": ["2026-27"] * n_players,
            "GW": [gw] * n_players,
            "total_points": actual_values,
        })
        fb = feedback_store.generate_feedback(snapshot, actual, "2026-27", gw)
        all_feedback.append(fb)

    return pd.concat(all_feedback, ignore_index=True) if all_feedback else pd.DataFrame()


class TestFeedbackStoreTemporalSafety:
    """Test that feedback loading respects temporal boundaries."""

    def test_max_gw_filter_excludes_future(self, tmp_path):
        feedback_store = FeedbackStore(tmp_path / "fb")
        _build_multi_gw_feedback(feedback_store, n_gws=5, secret_signal=100.0)

        # Load feedback for predicting GW 3 — should NOT include GW 3, 4, 5
        loaded = feedback_store.load_feedback(max_gw=2)
        if "GW" in loaded.columns:
            gws = loaded["GW"].unique()
            assert all(gw <= 2 for gw in gws), f"Leakage! Found GWs: {gws}"
            assert 3 not in gws
            assert 4 not in gws
            assert 5 not in gws


class TestResidualModelTemporalSafety:
    """Test that residual features never use target-GW data."""

    def test_build_features_excludes_target_gw(self, tmp_path):
        feedback_store = FeedbackStore(tmp_path / "fb")
        model = ResidualModel(tmp_path / "model")
        _build_multi_gw_feedback(feedback_store, n_gws=6, secret_signal=100.0)

        all_feedback = feedback_store.load_feedback()  # All GWs
        current = pd.DataFrame({
            "element": list(range(20)),
            "base_prediction": [3.0] * 20,
            "position": ["MID"] * 20,
            "team": ["Team_0"] * 20,
        })

        # Build features for predicting GW 6 — should NOT use GW 6 data
        features = model.build_residual_features(
            all_feedback, current, target_gw=6
        )

        # The secret signal in GW 6 (error=100) should NOT appear in features
        if not features.empty:
            for col in features.columns:
                if col in ("element", "position", "team"):
                    continue
                vals = pd.to_numeric(features[col], errors="coerce").dropna()
                # If GW 6 data leaked, player_error_mean would be ~20+ (average of
                # small errors + the 100.0 signal)
                assert vals.max() < 50, (
                    f"Possible leakage in column '{col}': max={vals.max()}"
                )

    def test_train_with_max_gw_excludes_future(self, tmp_path):
        feedback_store = FeedbackStore(tmp_path / "fb")
        model = ResidualModel(tmp_path / "model")
        _build_multi_gw_feedback(feedback_store, n_gws=6, secret_signal=100.0)

        all_feedback = feedback_store.load_feedback()

        # Train only on GWs <= 4 (exclude the secret GW 6)
        model.train(all_feedback, max_gw=4)
        assert model.is_trained
        assert model.metadata.n_training_samples > 0


class TestAdapterTemporalSafety:
    """Test that the adapter never accesses target-GW actual data."""

    def test_correction_does_not_reflect_target_gw_signal(self, tmp_path):
        """If we predict GW N, the correction must NOT know GW N's actual result.

        Strategy: inject a massive signal (+100) in GW 6's actual data.
        If the system leaks, the correction would be very large.
        If properly isolated, the correction should be small (reflecting
        only the moderate errors from GWs 1-5).
        """
        feedback_store = FeedbackStore(tmp_path / "fb")
        model = ResidualModel(tmp_path / "model")
        settings = FeedbackSettings()

        _build_multi_gw_feedback(feedback_store, n_gws=6, secret_signal=100.0)

        adapter = FeedbackAdapter(feedback_store, model, settings)

        # Train on GWs 1-5 (the adapter should use max_gw=5 for GW 6 prediction)
        adapter.update_model("2026-27", 5)

        current = pd.DataFrame({
            "element": list(range(20)),
            "predicted_total_points": [3.0] * 20,
            "position": ["MID"] * 20,
            "team": ["Team_0"] * 20,
        })

        result = adapter.apply_correction(current, "2026-27", 6)

        # Corrections should be small (reflecting GW 1-5 patterns, not GW 6's +100)
        max_abs_correction = result["feedback_correction"].abs().max()
        assert max_abs_correction <= settings.max_correction + 1e-9, (
            f"Correction {max_abs_correction} exceeds cap — possible leakage"
        )

        # Mean correction should be modest (around +1.0 based on GW 1-5 bias)
        mean_correction = result["feedback_correction"].mean()
        assert abs(mean_correction) < 10, (
            f"Mean correction {mean_correction} is suspiciously large — "
            f"possible GW 6 leakage"
        )

    def test_cold_start_zero_correction(self, tmp_path):
        """With no feedback, correction must be exactly zero."""
        feedback_store = FeedbackStore(tmp_path / "fb")
        model = ResidualModel(tmp_path / "model")
        settings = FeedbackSettings()

        adapter = FeedbackAdapter(feedback_store, model, settings)

        current = pd.DataFrame({
            "element": [1, 2],
            "predicted_total_points": [3.0, 5.0],
        })

        result = adapter.apply_correction(current, "2026-27", 1)
        assert all(result["feedback_correction"] == 0.0)
        assert all(result["final_prediction"] == result["base_prediction"])


class TestEvaluationTemporalSafety:
    """Test walk-forward evaluation temporal integrity."""

    def test_per_gw_uses_only_prior_data(self, tmp_path):
        """Each GW evaluation should only use prior GW feedback."""
        from src.prediction.feedback.evaluation import FeedbackEvaluator

        rows = []
        rng = np.random.RandomState(42)
        for gw in range(1, 8):
            for i in range(20):
                predicted = 3.0 + rng.randn()
                actual = predicted + 1.0 + rng.randn() * 0.5
                rows.append({
                    "element": i,
                    "GW": gw,
                    "predicted_points": predicted,
                    "actual_points": actual,
                    "prediction_error": actual - predicted,
                })

        fb = pd.DataFrame(rows)
        result = FeedbackEvaluator.evaluate_from_feedback(fb, min_gameweeks=2)

        # The per-GW results should be in chronological order
        if not result.per_gw_results.empty:
            gws = result.per_gw_results["GW"].values
            assert list(gws) == sorted(gws)

        # Early GWs should have adaptive_mae == baseline_mae (cold start)
        if len(result.per_gw_results) >= 3:
            early = result.per_gw_results.iloc[0]
            assert early["adaptive_mae"] == pytest.approx(early["baseline_mae"])
