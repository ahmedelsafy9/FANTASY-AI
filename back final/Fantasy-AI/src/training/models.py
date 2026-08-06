"""Domain models shared across the training layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass(frozen=True)
class RegressionMetrics:
    """Standard regression evaluation metrics.

    Attributes:
        mae: Mean Absolute Error — average magnitude of prediction
            error, in the same units as the target (FPL points).
        rmse: Root Mean Squared Error — like MAE but penalizes large
            errors more heavily.
        r2: R-squared — proportion of variance in the target explained
            by the model (1.0 is a perfect fit; 0.0 matches predicting
            the mean every time).
    """

    mae: float
    rmse: float
    r2: float


@dataclass
class ModelSpec:
    """Specification for one candidate model to train and evaluate.

    Attributes:
        name: Short, human-readable identifier (e.g. ``"random_forest"``).
        build: Zero-argument factory returning a fresh, unfitted
            scikit-learn-compatible estimator (implements ``fit`` and
            ``predict``). Building fresh per training run avoids state
            leaking between runs.
    """

    name: str
    build: Callable[[], Any]


@dataclass
class ModelResult:
    """The outcome of training and evaluating a single candidate model.

    Attributes:
        name: The model's identifier, matching its :class:`ModelSpec`.
        model: The fitted estimator.
        metrics: Evaluation metrics computed on the held-out test set.
        train_seconds: Wall-clock time spent fitting the model.
    """

    name: str
    model: Any = field(repr=False)
    metrics: RegressionMetrics
    train_seconds: float


@dataclass
class TrainingResult:
    """The outcome of a full training run across every candidate model.

    Attributes:
        generated_at: When the training run finished.
        feature_columns: The feature columns used for training, in
            order — persisted so the prediction layer (Sprint 7) can
            reconstruct an identical feature vector.
        target_column: The column that was predicted.
        train_rows: Number of rows in the training split.
        test_rows: Number of rows in the held-out test split.
        results: One :class:`ModelResult` per candidate model that was
            successfully trained (a model whose library is not
            installed is skipped, not failed).
        best_model_name: Name of the model selected as best, according
            to the configured primary metric.
        skipped_models: Names of models that could not be trained
            (e.g. their library is not installed), with a reason.
    """

    generated_at: datetime
    feature_columns: list[str]
    target_column: str
    train_rows: int
    test_rows: int
    results: list[ModelResult] = field(default_factory=list)
    best_model_name: str = ""
    skipped_models: dict[str, str] = field(default_factory=dict)
