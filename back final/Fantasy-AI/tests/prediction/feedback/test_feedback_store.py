"""Tests for FeedbackStore."""

from __future__ import annotations

import pandas as pd
import pytest

from src.prediction.feedback.feedback_store import FeedbackStore


@pytest.fixture
def feedback_store(tmp_path):
    """Create a feedback store in a temp directory."""
    return FeedbackStore(tmp_path / "feedback")


@pytest.fixture
def sample_snapshot():
    """Sample prediction snapshot."""
    return pd.DataFrame({
        "element": [1, 2, 3],
        "name": ["Player A", "Player B", "Player C"],
        "team": ["Team X", "Team Y", "Team Z"],
        "position": ["DEF", "MID", "FWD"],
        "base_prediction": [3.0, 6.0, 4.0],
        "model_name": ["dl_model"] * 3,
        "model_version": ["v1"] * 3,
    })


@pytest.fixture
def sample_actual():
    """Sample actual Gameweek data."""
    return pd.DataFrame({
        "element": [1, 2, 3],
        "name": ["Player A", "Player B", "Player C"],
        "team": ["Team X", "Team Y", "Team Z"],
        "position": ["DEF", "MID", "FWD"],
        "season": ["2026-27"] * 3,
        "GW": [1, 1, 1],
        "total_points": [5, 2, 12],
        "minutes": [90, 60, 90],
        "goals_scored": [0, 0, 2],
        "assists": [1, 0, 0],
        "clean_sheets": [1, 0, 0],
        "bonus": [0, 0, 3],
        "bps": [25, 10, 40],
    })


class TestFeedbackGeneration:
    """Test feedback record generation."""

    def test_correct_join_on_element(self, feedback_store, sample_snapshot, sample_actual):
        feedback = feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        assert len(feedback) == 3
        assert list(feedback["element"]) == [1, 2, 3]

    def test_correct_error_calculation(self, feedback_store, sample_snapshot, sample_actual):
        feedback = feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        # Player 1: actual=5, predicted=3 → error=+2
        row1 = feedback[feedback["element"] == 1].iloc[0]
        assert row1["prediction_error"] == pytest.approx(2.0)
        assert row1["absolute_error"] == pytest.approx(2.0)
        assert row1["squared_error"] == pytest.approx(4.0)

        # Player 2: actual=2, predicted=6 → error=-4
        row2 = feedback[feedback["element"] == 2].iloc[0]
        assert row2["prediction_error"] == pytest.approx(-4.0)
        assert row2["absolute_error"] == pytest.approx(4.0)

        # Player 3: actual=12, predicted=4 → error=+8
        row3 = feedback[feedback["element"] == 3].iloc[0]
        assert row3["prediction_error"] == pytest.approx(8.0)

    def test_error_direction_classification(self, feedback_store, sample_snapshot, sample_actual):
        feedback = feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        row1 = feedback[feedback["element"] == 1].iloc[0]
        assert row1["error_direction"] == "underprediction"  # actual > predicted

        row2 = feedback[feedback["element"] == 2].iloc[0]
        assert row2["error_direction"] == "overprediction"  # predicted > actual

    def test_actual_contribution_columns_preserved(self, feedback_store, sample_snapshot, sample_actual):
        feedback = feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        # Actual stats should be available with actual_ prefix
        assert "actual_minutes" in feedback.columns
        assert "actual_goals_scored" in feedback.columns
        assert "actual_assists" in feedback.columns
        assert "actual_bonus" in feedback.columns

    def test_idempotency(self, feedback_store, sample_snapshot, sample_actual):
        """Running feedback generation twice should not duplicate records."""
        fb1 = feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        fb2 = feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        # Both should have the same number of records
        assert len(fb1) == len(fb2)

        # The file should only have one copy
        loaded = feedback_store.load_feedback(season="2026-27", max_gw=1)
        assert len(loaded) == len(fb1)


class TestMissingPlayers:
    """Test handling of missing/unmatched players."""

    def test_missing_player_in_actual(self, feedback_store, sample_snapshot):
        """Players in snapshot but not in actual should be excluded."""
        actual = pd.DataFrame({
            "element": [1, 2],  # Player 3 missing
            "season": ["2026-27"] * 2,
            "GW": [1, 1],
            "total_points": [5, 2],
        })
        feedback = feedback_store.generate_feedback(
            sample_snapshot, actual, "2026-27", 1
        )
        assert len(feedback) == 2
        assert 3 not in feedback["element"].values

    def test_empty_actual_data(self, feedback_store, sample_snapshot):
        """Empty actual data should return empty feedback."""
        actual = pd.DataFrame(columns=["element", "season", "GW", "total_points"])
        feedback = feedback_store.generate_feedback(
            sample_snapshot, actual, "2026-27", 1
        )
        assert feedback.empty


class TestFeedbackLoading:
    """Test feedback loading with temporal filters."""

    def test_load_all(self, feedback_store, sample_snapshot, sample_actual):
        for gw in [1, 2, 3]:
            actual = sample_actual.copy()
            actual["GW"] = gw
            feedback_store.generate_feedback(
                sample_snapshot, actual, "2026-27", gw
            )
        loaded = feedback_store.load_feedback()
        assert len(loaded) == 9  # 3 players × 3 GWs

    def test_load_with_max_gw(self, feedback_store, sample_snapshot, sample_actual):
        for gw in [1, 2, 3]:
            actual = sample_actual.copy()
            actual["GW"] = gw
            feedback_store.generate_feedback(
                sample_snapshot, actual, "2026-27", gw
            )
        loaded = feedback_store.load_feedback(max_gw=2)
        gws = loaded["GW"].unique()
        assert 3 not in gws
        assert 1 in gws
        assert 2 in gws

    def test_load_with_season_filter(self, feedback_store, sample_snapshot, sample_actual):
        feedback_store.generate_feedback(
            sample_snapshot, sample_actual, "2026-27", 1
        )
        loaded = feedback_store.load_feedback(season="2025-26")
        assert loaded.empty
