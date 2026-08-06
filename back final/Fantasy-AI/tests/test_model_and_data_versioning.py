"""Unit tests for ModelVersionManager and DataVersionManager."""

from __future__ import annotations

from pathlib import Path

from src.automation.data_versioning import DataVersionManager
from src.automation.model_versioning import ModelVersionManager


def test_model_version_manager_versions_both_files_together(tmp_path: Path) -> None:
    """register_model must version the model artifact and its metadata as one unit."""
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model-bytes")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text('{"model_name": "rf"}')

    manager = ModelVersionManager(tmp_path / "model_versions", max_versions_to_keep=5)
    entry = manager.register_model(model_path, metadata_path, {"model_name": "rf"})

    assert manager.resolve_model_path(entry).read_bytes() == b"model-bytes"
    assert "rf" in manager.resolve_metadata_path(entry).read_text()


def test_model_version_manager_promote_to_best_copies_files(tmp_path: Path) -> None:
    """promote_to_best must copy a version's files over the live best-model paths."""
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model-v1")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text("{}")

    manager = ModelVersionManager(tmp_path / "model_versions", max_versions_to_keep=5)
    entry = manager.register_model(model_path, metadata_path, {})

    best_model_path = tmp_path / "best_model.joblib"
    best_metadata_path = tmp_path / "best_model_metadata.json"
    manager.promote_to_best(entry, best_model_path, best_metadata_path)

    assert best_model_path.read_bytes() == b"model-v1"
    assert best_metadata_path.exists()


def test_data_version_manager_detects_change_via_content_hash(tmp_path: Path) -> None:
    """has_changed_since_last_snapshot must detect real content changes."""
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text("a,b\n1,2\n")

    manager = DataVersionManager(tmp_path / "data_versions", max_versions_to_keep=5)
    assert manager.has_changed_since_last_snapshot(dataset_path) is True

    manager.snapshot(dataset_path, {"rows": 1})
    assert manager.has_changed_since_last_snapshot(dataset_path) is False

    dataset_path.write_text("a,b\n1,2\n3,4\n")
    assert manager.has_changed_since_last_snapshot(dataset_path) is True


def test_data_version_manager_no_change_for_identical_rewrite(tmp_path: Path) -> None:
    """Rewriting a file with identical content must not register as changed."""
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text("a,b\n1,2\n")

    manager = DataVersionManager(tmp_path / "data_versions", max_versions_to_keep=5)
    manager.snapshot(dataset_path, {})

    dataset_path.write_text("a,b\n1,2\n")  # byte-for-byte identical
    assert manager.has_changed_since_last_snapshot(dataset_path) is False
