"""Trains and evaluates every candidate model against a prepared split dataset."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from src.config.logging_config import get_logger
from src.config.settings import TrainingSettings
from src.training.dataset import SplitDataset
from src.training.metrics import compute_regression_metrics
from src.training.models import ModelResult, ModelSpec, TrainingResult

logger = get_logger(__name__)

_LOWER_IS_BETTER_METRICS = {"mae", "rmse"}


class ModelTrainer:
    """Fits, evaluates, and selects the best of a set of candidate models.

    Args:
        model_specs: The candidate models to train, injected by the
            caller — the trainer has no knowledge of which concrete
            models exist.
        settings: Training settings, used for the primary selection
            metric.
    """

    def __init__(self, model_specs: list[ModelSpec], settings: TrainingSettings) -> None:
        self._model_specs = model_specs
        self._settings = settings

    def run(self, split: SplitDataset, skipped_models: dict[str, str]) -> TrainingResult:
        """Train and evaluate every candidate model against the prepared split.

        Args:
            split: The prepared, leakage-free train/test split.
            skipped_models: Models that could not even be constructed
                (e.g. missing library), to be carried through into the
                returned :class:`TrainingResult` for transparency.

        Returns:
            TrainingResult: Aggregated results across every
            successfully trained model, with the best model selected.

        Raises:
            RuntimeError: If every candidate model fails to train.
        """
        results: list[ModelResult] = []

        for spec in self._model_specs:
            logger.info("Training model '%s'...", spec.name)
            try:
                model = spec.build()
                start = time.perf_counter()
                model.fit(split.X_train, split.y_train)
                train_seconds = time.perf_counter() - start

                predictions = model.predict(split.X_test)
                metrics = compute_regression_metrics(split.y_test.to_numpy(), predictions)

                results.append(
                    ModelResult(
                        name=spec.name,
                        model=model,
                        metrics=metrics,
                        train_seconds=train_seconds,
                    )
                )
                logger.info(
                    "Model '%s' trained in %.2fs — MAE=%.4f, RMSE=%.4f, R2=%.4f",
                    spec.name,
                    train_seconds,
                    metrics.mae,
                    metrics.rmse,
                    metrics.r2,
                )
            except Exception as exc:  # noqa: BLE001 - one bad model must not sink the run
                logger.error("Model '%s' failed to train: %s", spec.name, exc)
                skipped_models[spec.name] = f"Training failed: {exc}"

        if not results:
            raise RuntimeError("Every candidate model failed to train; no results to report.")

        best = self._select_best(results)

        return TrainingResult(
            generated_at=datetime.now(timezone.utc),
            feature_columns=split.feature_columns,
            target_column=self._settings.target_column,
            train_rows=len(split.X_train),
            test_rows=len(split.X_test),
            results=results,
            best_model_name=best.name,
            skipped_models=skipped_models,
        )

    def _select_best(self, results: list[ModelResult]) -> ModelResult:
        """Select the best model according to the configured primary metric.

        Args:
            results: Successfully trained model results.

        Returns:
            ModelResult: The best-performing model.

        Raises:
            ValueError: If the configured primary metric is unknown.
        """
        metric = self._settings.primary_metric
        if not hasattr(results[0].metrics, metric):
            raise ValueError(f"Unknown primary metric '{metric}'.")

        lower_is_better = metric in _LOWER_IS_BETTER_METRICS
        return min(
            results,
            key=lambda r: getattr(r.metrics, metric) * (1 if lower_is_better else -1),
        )
