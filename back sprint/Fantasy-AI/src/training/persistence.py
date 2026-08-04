"""Persists the best trained model and the metadata needed to reuse it.

The metadata file is what Sprint 7's prediction pipeline will read to
know exactly which features to compute, in which order, and how to
impute missing values — the model artifact alone is not enough to make
a correct prediction.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.training.dataset import SplitDataset
from src.training.models import ModelResult, TrainingResult

logger = get_logger(__name__)


def save_best_model(
    result: TrainingResult,
    split: SplitDataset,
    model_path: Path,
    metadata_path: Path,
) -> None:
    """Persist the best model artifact and its reproducibility metadata.

    Args:
        result: The full training result (used to find the best model
            and record its metrics).
        split: The prepared split (used to record imputation medians).
        model_path: File path the model artifact should be written to
            (``.joblib``).
        metadata_path: File path the JSON metadata should be written to.

    Raises:
        ValueError: If ``result.best_model_name`` does not match any
            entry in ``result.results``.
    """
    best_result = _find_result(result, result.best_model_name)

    ensure_directory(model_path.parent)
    joblib.dump(best_result.model, model_path)
    logger.info("Saved best model ('%s') to %s.", best_result.name, model_path)

    metadata = {
        "model_name": best_result.name,
        "generated_at": result.generated_at.isoformat(),
        "target_column": result.target_column,
        "feature_columns": result.feature_columns,
        "train_medians": split.train_medians,
        "train_rows": result.train_rows,
        "test_rows": result.test_rows,
        "metrics": {
            "mae": best_result.metrics.mae,
            "rmse": best_result.metrics.rmse,
            "r2": best_result.metrics.r2,
        },
    }
    ensure_directory(metadata_path.parent)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("Saved model metadata to %s.", metadata_path)


def _find_result(result: TrainingResult, name: str) -> ModelResult:
    """Find a specific model's result by name.

    Args:
        result: The full training result to search.
        name: The model name to find.

    Returns:
        ModelResult: The matching result.

    Raises:
        ValueError: If no result with that name exists.
    """
    for model_result in result.results:
        if model_result.name == name:
            return model_result
    raise ValueError(f"No result found for model '{name}'.")
