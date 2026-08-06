"""Unit tests for ModelTrainer, the model factory, persistence, and report writer."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.config.settings import TrainingSettings
from src.training.dataset import prepare_split_dataset
from src.training.factory import build_default_model_specs
from src.training.models import ModelSpec
from src.training.persistence import save_best_model
from src.training.report_writer import write_comparison_report
from src.training.trainer import ModelTrainer


def _build_linear_dataset(n_players: int = 3, n_gws: int = 20) -> pd.DataFrame:
    """A dataset where total_points is a near-deterministic function of minutes."""
    rng = np.random.default_rng(42)
    rows = []
    for player in range(n_players):
        for gw in range(1, n_gws + 1):
            minutes = 90.0
            noise = rng.normal(0, 0.1)
            rows.append(
                {
                    "season": "2022-23",
                    "GW": gw,
                    "element": player,
                    "minutes": minutes,
                    "bonus": float(gw % 3),
                    "total_points": 0.1 * minutes + 2 * (gw % 3) + noise,
                }
            )
    return pd.DataFrame(rows)


def _default_settings() -> TrainingSettings:
    return TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=("element",),
        chronological_columns=("season", "GW"),
        test_fraction=0.2,
        random_state=42,
    )


def test_build_default_model_specs_always_includes_sklearn_models() -> None:
    """Linear regression and random forest must always be available (core deps)."""
    specs, skipped = build_default_model_specs(_default_settings())
    names = {spec.name for spec in specs}
    assert "linear_regression" in names
    assert "random_forest" in names
    # skipped is a dict of name->reason for any library that failed to import;
    # it must never claim a core dependency (sklearn-based) is skipped.
    assert "linear_regression" not in skipped
    assert "random_forest" not in skipped


def test_trainer_trains_all_specs_and_selects_best() -> None:
    """The trainer must train every spec and select the best by the primary metric."""
    settings = _default_settings()
    df = _build_linear_dataset()
    split = prepare_split_dataset(df, settings)

    specs = [
        ModelSpec(name="linear_regression", build=lambda: LinearRegression()),
        ModelSpec(name="mean_baseline", build=lambda: _MeanBaseline()),
    ]
    trainer = ModelTrainer(model_specs=specs, settings=settings)
    result = trainer.run(split, skipped_models={})

    assert len(result.results) == 2
    # Linear regression should clearly outperform the naive mean baseline
    # on this near-linear synthetic dataset.
    assert result.best_model_name == "linear_regression"


def test_trainer_skips_failing_model_without_sinking_the_run() -> None:
    """A model that raises during fit must be recorded as skipped, not crash the run."""
    settings = _default_settings()
    df = _build_linear_dataset()
    split = prepare_split_dataset(df, settings)

    specs = [
        ModelSpec(name="linear_regression", build=lambda: LinearRegression()),
        ModelSpec(name="broken_model", build=lambda: _AlwaysFailsModel()),
    ]
    trainer = ModelTrainer(model_specs=specs, settings=settings)
    result = trainer.run(split, skipped_models={})

    assert result.best_model_name == "linear_regression"
    assert "broken_model" in result.skipped_models


def test_trainer_raises_when_every_model_fails() -> None:
    """If every candidate model fails to train, the trainer must raise."""
    settings = _default_settings()
    df = _build_linear_dataset()
    split = prepare_split_dataset(df, settings)

    specs = [ModelSpec(name="broken_model", build=lambda: _AlwaysFailsModel())]
    trainer = ModelTrainer(model_specs=specs, settings=settings)

    with pytest.raises(RuntimeError):
        trainer.run(split, skipped_models={})


def test_save_best_model_writes_artifact_and_metadata(tmp_path: Path) -> None:
    """save_best_model must write a loadable model artifact and complete metadata."""
    settings = _default_settings()
    df = _build_linear_dataset()
    split = prepare_split_dataset(df, settings)

    specs = [ModelSpec(name="linear_regression", build=lambda: LinearRegression())]
    trainer = ModelTrainer(model_specs=specs, settings=settings)
    result = trainer.run(split, skipped_models={})

    model_path = tmp_path / "model.joblib"
    metadata_path = tmp_path / "metadata.json"
    save_best_model(result, split, model_path, metadata_path)

    assert model_path.exists()
    assert metadata_path.exists()

    import joblib

    loaded_model = joblib.load(model_path)
    predictions = loaded_model.predict(split.X_test)
    assert len(predictions) == len(split.X_test)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["model_name"] == "linear_regression"
    assert metadata["feature_columns"] == split.feature_columns
    assert "mae" in metadata["metrics"]


def test_write_comparison_report_produces_readable_file(tmp_path: Path) -> None:
    """write_comparison_report must produce a Markdown file naming the best model."""
    settings = _default_settings()
    df = _build_linear_dataset()
    split = prepare_split_dataset(df, settings)

    specs = [
        ModelSpec(name="linear_regression", build=lambda: LinearRegression()),
        ModelSpec(name="mean_baseline", build=lambda: _MeanBaseline()),
    ]
    trainer = ModelTrainer(model_specs=specs, settings=settings)
    result = trainer.run(split, skipped_models={"xgboost": "not installed"})

    report_path = tmp_path / "report.md"
    write_comparison_report(result, report_path)

    text = report_path.read_text(encoding="utf-8")
    assert "Machine Learning Baseline Comparison Report" in text
    assert result.best_model_name in text
    assert "xgboost" in text


class _MeanBaseline:
    """A trivial estimator that always predicts the training mean."""

    def fit(self, X, y):  # noqa: N803 - sklearn convention
        self._mean = float(np.mean(y))
        return self

    def predict(self, X):  # noqa: N803 - sklearn convention
        return np.full(shape=(len(X),), fill_value=self._mean)


class _AlwaysFailsModel:
    """A model whose fit() always raises, to test trainer resilience."""

    def fit(self, X, y):  # noqa: N803 - sklearn convention
        raise RuntimeError("synthetic training failure")

    def predict(self, X):  # noqa: N803 - sklearn convention
        raise RuntimeError("should never be called")
