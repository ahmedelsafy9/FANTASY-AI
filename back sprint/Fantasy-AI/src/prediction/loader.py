"""Loads a trained model artifact and its reproducibility metadata.

The training layer (Sprint 6) persists a ``.joblib`` model file and a
companion JSON metadata file describing exactly how to reproduce its
input feature vector (feature column order, imputation medians,
target column). This module reunites the two into a single object the
rest of the prediction layer can use without caring about either
file's on-disk format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

from src.config.logging_config import get_logger
from src.core.exceptions import ModelNotFoundError

logger = get_logger(__name__)


@dataclass
class LoadedModel:
    """A trained model plus everything needed to feed it correctly.

    Attributes:
        model: The fitted, scikit-learn-compatible estimator.
        model_name: The model's identifier (e.g. ``"random_forest"``).
        feature_columns: Feature columns, in the exact order the model
            expects them.
        target_column: The column the model predicts.
        train_medians: Per-feature medians (from the training split)
            to use when imputing missing values at inference time.
        metrics: The model's held-out test metrics, as recorded during
            training (for display/logging, not used in inference).
    """

    model: Any
    model_name: str
    feature_columns: list[str]
    target_column: str
    train_medians: dict[str, float]
    metrics: dict[str, float]


def load_model(model_path: Path, metadata_path: Path) -> LoadedModel:
    """Load a trained model artifact together with its metadata.

    Args:
        model_path: Path to the ``.joblib`` model artifact.
        metadata_path: Path to the companion JSON metadata file.

    Returns:
        LoadedModel: The reunited model and metadata.

    Raises:
        ModelNotFoundError: If either file is missing or cannot be
            parsed.
    """
    if not model_path.exists():
        raise ModelNotFoundError(f"Model artifact not found at {model_path}.")
    if not metadata_path.exists():
        raise ModelNotFoundError(f"Model metadata not found at {metadata_path}.")

    try:
        model = joblib.load(model_path)
    except Exception as exc:  # noqa: BLE001 - surface as a domain error
        raise ModelNotFoundError(f"Could not load model artifact at {model_path}: {exc}") from exc

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelNotFoundError(
            f"Could not read model metadata at {metadata_path}: {exc}"
        ) from exc

    required_keys = {"model_name", "feature_columns", "target_column", "train_medians"}
    missing_keys = required_keys - metadata.keys()
    if missing_keys:
        raise ModelNotFoundError(f"Model metadata at {metadata_path} is missing keys: {missing_keys}.")

    logger.info(
        "Loaded model '%s' (%d feature columns) from %s.",
        metadata["model_name"],
        len(metadata["feature_columns"]),
        model_path,
    )

    return LoadedModel(
        model=model,
        model_name=metadata["model_name"],
        feature_columns=list(metadata["feature_columns"]),
        target_column=metadata["target_column"],
        train_medians=dict(metadata["train_medians"]),
        metrics=dict(metadata.get("metrics", {})),
    )
