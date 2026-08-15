"""Trains and evaluates every candidate model against a prepared split dataset."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import numpy as np

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

    def __init__(
        self,
        model_specs: list[ModelSpec],
        settings: TrainingSettings,
    ) -> None:
        self._model_specs = model_specs
        self._settings = settings

    def run(
        self,
        split: SplitDataset,
        skipped_models: dict[str, str],
    ) -> TrainingResult:
        """Train and evaluate every candidate model.

        Training uses season-based sample weights.

        The weights are prepared by ``prepare_split_dataset`` using a
        configurable strategy (default: linear interpolation from
        ``season_weight_min`` to ``season_weight_max``).

        The test set remains completely unweighted.

        Args:
            split: Prepared, leakage-free train/test dataset.
            skipped_models: Models that could not be constructed.

        Returns:
            TrainingResult: Aggregated model results with the best model.

        Raises:
            RuntimeError: If every candidate model fails to train.
        """

        results: list[ModelResult] = []

        # -----------------------------------------------------------
        # Validate training weights
        # -----------------------------------------------------------

        train_weights = getattr(
            split,
            "train_weights",
            None,
        )

        if train_weights is None:
            logger.warning(
                "No training sample weights found. "
                "Training will use uniform weights."
            )

        elif len(train_weights) != len(split.X_train):
            raise ValueError(
                "Training weights length does not match training data: "
                f"{len(train_weights)} weights for "
                f"{len(split.X_train)} training rows."
            )

        else:
            logger.info(
                "Using recency-weighted training samples: "
                "rows=%d, total_weight=%.2f, "
                "min_weight=%.2f, max_weight=%.2f.",
                len(train_weights),
                float(train_weights.sum()),
                float(train_weights.min()),
                float(train_weights.max()),
            )

            unique_weights = sorted(train_weights.unique())
            weight_counts = {
                f"{w:.4f}x": int((train_weights == w).sum())
                for w in unique_weights
            }
            logger.info(
                "Weight distribution: %s",
                weight_counts,
            )

        # -----------------------------------------------------------
        # Train every candidate model
        # -----------------------------------------------------------

        for spec in self._model_specs:
            logger.info(
                "Training model '%s'...",
                spec.name,
            )

            try:
                model = spec.build()

                start = time.perf_counter()

                # ---------------------------------------------------
                # IMPORTANT:
                #
                # Recent training seasons receive higher influence
                # through sample_weight.
                #
                # The actual feature values are NOT modified.
                # The test set is NOT weighted.
                # ---------------------------------------------------

                if train_weights is not None:
                    model.fit(
                        split.X_train,
                        split.y_train,
                        sample_weight=train_weights.to_numpy(
                            dtype="float64"
                        ),
                    )
                else:
                    model.fit(
                        split.X_train,
                        split.y_train,
                    )

                train_seconds = (
                    time.perf_counter() - start
                )

                # ---------------------------------------------------
                # Evaluate on the untouched chronological test set
                # ---------------------------------------------------

                predictions = model.predict(
                    split.X_test
                )

                metrics = compute_regression_metrics(
                    split.y_test.to_numpy(),
                    predictions,
                )

                results.append(
                    ModelResult(
                        name=spec.name,
                        model=model,
                        metrics=metrics,
                        train_seconds=train_seconds,
                        predictions=np.asarray(predictions).ravel(),
                    )
                )

                logger.info(
                    "Model '%s' trained in %.2fs — "
                    "MAE=%.4f, RMSE=%.4f, R2=%.4f",
                    spec.name,
                    train_seconds,
                    metrics.mae,
                    metrics.rmse,
                    metrics.r2,
                )

            except Exception as exc:
                # One failed model should not stop the entire
                # training pipeline.
                logger.error(
                    "Model '%s' failed to train: %s",
                    spec.name,
                    exc,
                )

                skipped_models[
                    spec.name
                ] = f"Training failed: {exc}"

        # -----------------------------------------------------------
        # Make sure at least one model succeeded
        # -----------------------------------------------------------

        if not results:
            raise RuntimeError(
                "Every candidate model failed to train; "
                "no results to report."
            )

        # -----------------------------------------------------------
        # Select best model
        # -----------------------------------------------------------

        y_test_arr = split.y_test.to_numpy()
        composite_scores = []

        if self._settings.promotion_strategy == "composite":
            best, composite_scores = self._select_best_composite(
                results, y_test_arr
            )
        else:
            best = self._select_best_legacy(results)

        logger.info(
            "Selected best model '%s' (strategy='%s').",
            best.name,
            self._settings.promotion_strategy,
        )

        # -----------------------------------------------------------
        # Return complete training result
        # -----------------------------------------------------------

        return TrainingResult(
            generated_at=datetime.now(timezone.utc),
            feature_columns=split.feature_columns,
            target_column=self._settings.target_column,
            train_rows=len(split.X_train),
            test_rows=len(split.X_test),
            results=results,
            best_model_name=best.name,
            skipped_models=skipped_models,
            y_test=y_test_arr,
            composite_scores=composite_scores,
        )

    def _select_best_composite(
        self,
        results: list[ModelResult],
        y_test: np.ndarray,
    ) -> tuple[ModelResult, list]:
        """Select the best model using FPL-aware composite scoring.

        Args:
            results: Successfully trained model results.
            y_test: Ground-truth test targets.

        Returns:
            tuple[ModelResult, list]: The best model and all composite
            scores.
        """
        from src.training.promotion_scorer import select_best_model_fpl

        logger.info(
            "Selecting best model using composite FPL scoring..."
        )

        candidate_names = [r.name for r in results]
        candidate_predictions = [r.predictions for r in results]

        best_idx, all_scores = select_best_model_fpl(
            candidate_names=candidate_names,
            candidate_predictions=candidate_predictions,
            y_test=y_test,
            weights=self._settings.promotion_metric_weights,
            gates=self._settings.promotion_gates,
        )

        return results[best_idx], all_scores

    def _select_best_legacy(
        self,
        results: list[ModelResult],
    ) -> ModelResult:
        """Select the best model according to the configured primary metric.

        This is the legacy single-metric selection, preserved for
        backward compatibility.

        Args:
            results: Successfully trained model results.

        Returns:
            ModelResult: The best-performing model.

        Raises:
            ValueError: If the configured primary metric is unknown.
        """

        metric = self._settings.primary_metric

        if not hasattr(
            results[0].metrics,
            metric,
        ):
            raise ValueError(
                f"Unknown primary metric '{metric}'."
            )

        lower_is_better = (
            metric in _LOWER_IS_BETTER_METRICS
        )

        return min(
            results,
            key=lambda result: (
                getattr(
                    result.metrics,
                    metric,
                )
                * (
                    1
                    if lower_is_better
                    else -1
                )
            ),
        )