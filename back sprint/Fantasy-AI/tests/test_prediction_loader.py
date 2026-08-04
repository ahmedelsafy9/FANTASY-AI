"""Unit tests for src.prediction.loader."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest
from sklearn.linear_model import LinearRegression

from src.core.exceptions import ModelNotFoundError
from src.prediction.loader import load_model


def _write_fake_model(tmp_path: Path) -> tuple[Path, Path]:
    model = LinearRegression()
    model.fit([[1, 2], [3, 4], [5, 6]], [1, 2, 3])
    model_path = tmp_path / "model.joblib"
    joblib.dump(model, model_path)

    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_name": "linear_regression",
                "feature_columns": ["a", "b"],
                "target_column": "total_points",
                "train_medians": {"a": 1.0, "b": 2.0},
                "metrics": {"mae": 0.5, "rmse": 0.7, "r2": 0.9},
            }
        ),
        encoding="utf-8",
    )
    return model_path, metadata_path


def test_load_model_returns_populated_loaded_model(tmp_path: Path) -> None:
    """load_model must return a LoadedModel with all metadata fields populated."""
    model_path, metadata_path = _write_fake_model(tmp_path)
    loaded = load_model(model_path, metadata_path)

    assert loaded.model_name == "linear_regression"
    assert loaded.feature_columns == ["a", "b"]
    assert loaded.target_column == "total_points"
    assert loaded.train_medians == {"a": 1.0, "b": 2.0}
    assert loaded.metrics["mae"] == 0.5
    assert hasattr(loaded.model, "predict")


def test_load_model_raises_when_model_file_missing(tmp_path: Path) -> None:
    """A missing model artifact must raise ModelNotFoundError."""
    _, metadata_path = _write_fake_model(tmp_path)
    with pytest.raises(ModelNotFoundError):
        load_model(tmp_path / "does_not_exist.joblib", metadata_path)


def test_load_model_raises_when_metadata_file_missing(tmp_path: Path) -> None:
    """A missing metadata file must raise ModelNotFoundError."""
    model_path, _ = _write_fake_model(tmp_path)
    with pytest.raises(ModelNotFoundError):
        load_model(model_path, tmp_path / "does_not_exist.json")


def test_load_model_raises_when_metadata_missing_required_keys(tmp_path: Path) -> None:
    """Metadata missing a required key must raise ModelNotFoundError."""
    model_path, metadata_path = _write_fake_model(tmp_path)
    metadata_path.write_text(json.dumps({"model_name": "x"}), encoding="utf-8")
    with pytest.raises(ModelNotFoundError):
        load_model(model_path, metadata_path)
