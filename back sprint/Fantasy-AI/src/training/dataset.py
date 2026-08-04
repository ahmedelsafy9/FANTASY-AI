"""Dataset preparation for model training: feature selection, chronological
train/test splitting, and leakage-free missing-value imputation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import TrainingSettings

logger = get_logger(__name__)


def select_feature_columns(data: pd.DataFrame, settings: TrainingSettings) -> list[str]:
    """Select numeric feature columns, excluding the target and identifier columns.

    A column is selected if it is numeric or boolean, is not the
    target column, is not explicitly excluded, and is not a
    normalization join-key column (any column ending in
    ``"_normalized"``, added by the preprocessing layer for entity
    matching rather than modeling).

    Args:
        data: The engineered dataset to select feature columns from.
        settings: Training settings providing the target column and
            explicit exclusion list.

    Returns:
        list[str]: The selected feature column names, in the order
        they appear in ``data``.
    """
    excluded = set(settings.excluded_feature_columns) | {settings.target_column}
    feature_columns = [
        column
        for column in data.columns
        if column not in excluded
        and not column.endswith("_normalized")
        and (pd.api.types.is_numeric_dtype(data[column]) or pd.api.types.is_bool_dtype(data[column]))
    ]
    logger.info("Selected %d feature column(s): %s", len(feature_columns), feature_columns)
    return feature_columns


@dataclass
class SplitDataset:
    """A chronologically split, imputed, model-ready dataset.

    Attributes:
        X_train: Training feature matrix.
        y_train: Training target vector.
        X_test: Held-out feature matrix.
        y_test: Held-out target vector.
        feature_columns: The feature columns used, in column order.
        train_medians: Per-column medians computed on the training
            split only, used to impute both splits (persisted so the
            prediction layer can apply the same imputation).
    """

    X_train: pd.DataFrame
    y_train: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    feature_columns: list[str]
    train_medians: dict[str, float]


def prepare_split_dataset(
    data: pd.DataFrame, settings: TrainingSettings
) -> SplitDataset:
    """Select features, split chronologically, and impute missing values.

    The split is chronological (not random/shuffled): the dataset is
    sorted by the configured chronological columns and the most recent
    ``test_fraction`` of rows become the test set. This mirrors how the
    model will actually be used — predicting future Gameweeks from
    past ones — and avoids the optimistic bias a random split would
    introduce by leaking future information into training.

    Missing feature values are imputed with the **training-set**
    median for each column, then applied to both splits — computing
    the median from the full dataset (including the test set) would
    itself be a subtle form of leakage.

    Args:
        data: The engineered dataset (from Sprint 5) to prepare.
        settings: Training settings controlling target/feature
            selection and split behavior.

    Returns:
        SplitDataset: The prepared, leakage-free train/test split.

    Raises:
        ValueError: If the target column is missing, or if the
            dataset has too few rows to form both splits.
    """
    if settings.target_column not in data.columns:
        raise ValueError(f"Target column '{settings.target_column}' not found in dataset.")

    working = data.dropna(subset=[settings.target_column]).copy()
    if working.empty:
        raise ValueError("No rows remain after dropping missing targets.")

    sort_columns = [c for c in settings.chronological_columns if c in working.columns]
    if sort_columns:
        working = working.sort_values(by=sort_columns, kind="mergesort").reset_index(drop=True)
    else:
        logger.warning(
            "None of the chronological columns %s are present; using existing row order "
            "for the train/test split.",
            settings.chronological_columns,
        )

    feature_columns = select_feature_columns(working, settings)
    if not feature_columns:
        raise ValueError("No usable feature columns were selected from the dataset.")

    split_index = int(len(working) * (1 - settings.test_fraction))
    split_index = max(1, min(split_index, len(working) - 1))

    train_df = working.iloc[:split_index]
    test_df = working.iloc[split_index:]

    X_train = train_df[feature_columns].apply(pd.to_numeric, errors="coerce")
    X_test = test_df[feature_columns].apply(pd.to_numeric, errors="coerce")

    train_medians = X_train.median(numeric_only=True).to_dict()
    fallback_median = float(np.nanmedian(X_train.to_numpy(dtype="float64"))) if not X_train.empty else 0.0

    X_train = X_train.fillna(train_medians).fillna(fallback_median)
    X_test = X_test.fillna(train_medians).fillna(fallback_median)

    y_train = pd.to_numeric(train_df[settings.target_column], errors="coerce")
    y_test = pd.to_numeric(test_df[settings.target_column], errors="coerce")

    logger.info(
        "Prepared chronological split: %d train row(s), %d test row(s), %d feature(s).",
        len(X_train),
        len(X_test),
        len(feature_columns),
    )

    return SplitDataset(
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        feature_columns=feature_columns,
        train_medians={k: float(v) for k, v in train_medians.items()},
    )
