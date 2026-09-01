"""Tests for PredictionSnapshotStore."""

from __future__ import annotations

import pandas as pd
import pytest

from src.prediction.feedback.snapshot_store import PredictionSnapshotStore


@pytest.fixture
def snapshot_store(tmp_path):
    """Create a snapshot store in a temp directory."""
    return PredictionSnapshotStore(tmp_path / "snapshots")


@pytest.fixture
def sample_predictions():
    """Sample prediction DataFrame."""
    return pd.DataFrame({
        "element": [1, 2, 3, 4],
        "name": ["Player A", "Player B", "Player C", "Player D"],
        "team": ["Team X", "Team X", "Team Y", "Team Y"],
        "position": ["DEF", "MID", "FWD", "GKP"],
        "predicted_total_points": [3.5, 6.2, 4.1, 2.0],
        "feat_value": [50, 80, 100, 45],
        "feat_form_index": [0.5, 0.8, 0.3, 0.1],
    })


class TestSnapshotCreation:
    """Test snapshot creation and basic behavior."""

    def test_save_creates_file(self, snapshot_store, sample_predictions):
        path = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        assert path.exists()

    def test_snapshot_contains_required_columns(self, snapshot_store, sample_predictions):
        path = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        df = pd.read_csv(path)
        for col in ("element", "name", "team", "position", "season",
                     "target_gw", "base_prediction", "model_name",
                     "model_version", "prediction_timestamp"):
            assert col in df.columns, f"Missing column: {col}"

    def test_element_based_identity(self, snapshot_store, sample_predictions):
        path = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        df = pd.read_csv(path)
        assert list(df["element"]) == [1, 2, 3, 4]

    def test_base_prediction_values(self, snapshot_store, sample_predictions):
        path = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        df = pd.read_csv(path)
        assert list(df["base_prediction"]) == [3.5, 6.2, 4.1, 2.0]

    def test_feature_vector_preserved(self, snapshot_store, sample_predictions):
        path = snapshot_store.save_snapshot(
            sample_predictions,
            "2026-27",
            2,
            "dl_model",
            "v1",
            feature_columns=["feat_value", "feat_form_index"],
        )
        df = pd.read_csv(path)
        # Feature columns should be prefixed with feat_
        assert "feat_feat_value" in df.columns or "feat_value" in df.columns


class TestSnapshotImmutability:
    """Test that snapshots cannot be overwritten."""

    def test_immutable_no_overwrite(self, snapshot_store, sample_predictions):
        """Saving a second snapshot for the same GW must NOT overwrite."""
        path1 = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        content1 = path1.read_text()

        # Modify predictions
        modified = sample_predictions.copy()
        modified["predicted_total_points"] = [99.0, 99.0, 99.0, 99.0]

        path2 = snapshot_store.save_snapshot(
            modified, "2026-27", 2, "dl_model", "v2"
        )

        # Should return the same path
        assert path1 == path2

        # Content should be unchanged (original)
        assert path2.read_text() == content1

    def test_different_gw_creates_new(self, snapshot_store, sample_predictions):
        """Different GWs should create separate snapshots."""
        path1 = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        path2 = snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 3, "dl_model", "v1"
        )
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()


class TestSnapshotLoading:
    """Test snapshot loading."""

    def test_load_existing(self, snapshot_store, sample_predictions):
        snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        loaded = snapshot_store.load_snapshot("2026-27", 2)
        assert loaded is not None
        assert len(loaded) == 4

    def test_load_nonexistent_returns_none(self, snapshot_store):
        assert snapshot_store.load_snapshot("2026-27", 99) is None

    def test_exists_check(self, snapshot_store, sample_predictions):
        assert not snapshot_store.exists("2026-27", 2)
        snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        assert snapshot_store.exists("2026-27", 2)

    def test_list_snapshots(self, snapshot_store, sample_predictions):
        snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 1, "dl_model", "v1"
        )
        snapshot_store.save_snapshot(
            sample_predictions, "2026-27", 2, "dl_model", "v1"
        )
        snapshots = snapshot_store.list_snapshots()
        assert ("2026-27", 1) in snapshots
        assert ("2026-27", 2) in snapshots
