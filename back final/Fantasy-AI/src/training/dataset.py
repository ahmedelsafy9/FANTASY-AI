"""Dataset preparation for model training: feature selection, chronological
train/test splitting, leakage-free missing-value imputation, and recency
weighting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import TrainingSettings


logger = get_logger(__name__)


def select_feature_columns(
    data: pd.DataFrame,
    settings: TrainingSettings,
) -> list[str]:
    """Select numeric feature columns, excluding target and identifier columns.

    A column is selected if it is numeric or boolean, is not the target
    column, is not explicitly excluded, and is not a normalization join-key
    column ending in "_normalized".
    """

    excluded = (
        set(settings.excluded_feature_columns)
        | {settings.target_column}
    )

    feature_columns = [
        column
        for column in data.columns
        if (
            column not in excluded
            and not column.endswith("_normalized")
            and (
                pd.api.types.is_numeric_dtype(data[column])
                or pd.api.types.is_bool_dtype(data[column])
            )
        )
    ]

    logger.info(
        "Selected %d feature column(s): %s",
        len(feature_columns),
        feature_columns,
    )

    return feature_columns


@dataclass
class SplitDataset:
    """A chronologically split, imputed, model-ready dataset.

    Attributes:
        X_train: Training feature matrix.
        y_train: Training target vector.
        X_test: Held-out feature matrix.
        y_test: Held-out target vector.
        feature_columns: Feature columns used by the model.
        train_medians: Per-column medians computed only from training data.
        train_weights: Sample weights used to give more importance to
            recent seasons during training.
    """

    X_train: pd.DataFrame
    y_train: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    feature_columns: list[str]
    train_medians: dict[str, float]
    train_weights: pd.Series


def _season_sort_key(season_str: str) -> int | None:
    """Parse a ``YYYY-YY`` season string into its start year for sorting.

    Args:
        season_str: A season identifier, e.g. ``"2022-23"``.

    Returns:
        int | None: The start year (e.g. ``2022``), or ``None`` if the
        string does not match the expected format.
    """
    import re

    match = re.match(r"^((?:19|20)\d{2})-\d{2}$", str(season_str).strip())
    if match is None:
        return None
    return int(match.group(1))


def _build_recency_weights(
    train_df: pd.DataFrame,
    all_data: pd.DataFrame,
    settings: TrainingSettings,
) -> pd.Series:
    """Build leakage-safe recency weights for training rows.

    The latest season is determined from the FULL dataset, before the
    chronological train/test split.

    Weight policy (``"linear"`` strategy):

        Each season is assigned a weight that linearly interpolates
        between ``settings.season_weight_min`` (oldest) and
        ``settings.season_weight_max`` (newest).

    Important:
        Only training rows receive weights. Test rows are never weighted.

    If the latest season exists only in the test set, there will naturally
    be no max-weight rows in the training set. This is intentional and
    prevents test data from influencing training.
    """

    weights = pd.Series(
        1.0,
        index=train_df.index,
        dtype="float64",
    )

    if "season" not in all_data.columns:
        logger.warning(
            "Column 'season' not found. "
            "Using uniform training weights."
        )
        return weights

    # -----------------------------------------------------------------
    # Parse season strings into sortable start-years
    # -----------------------------------------------------------------

    all_season_values = all_data["season"].dropna().unique()

    season_to_key: dict[str, int] = {}
    for season_val in all_season_values:
        key = _season_sort_key(season_val)
        if key is not None:
            season_to_key[str(season_val)] = key

    if not season_to_key:
        logger.warning(
            "Column 'season' exists but contains no parseable "
            "season strings (expected format 'YYYY-YY', e.g. '2022-23'). "
            "Found values: %s. Using uniform training weights.",
            list(all_season_values[:10]),
        )
        return weights

    # Sort seasons chronologically by start year
    sorted_seasons = sorted(
        season_to_key.keys(),
        key=lambda s: season_to_key[s],
    )

    logger.info(
        "Detected %d season(s) in full dataset: %s",
        len(sorted_seasons),
        sorted_seasons,
    )

    # -----------------------------------------------------------------
    # Compute weight for each season using configured strategy
    # -----------------------------------------------------------------

    weight_max = settings.season_weight_max
    weight_min = settings.season_weight_min
    n_seasons = len(sorted_seasons)

    season_weight_map: dict[str, float] = {}

    if n_seasons == 1:
        # Only one season — give it the maximum weight
        season_weight_map[sorted_seasons[0]] = weight_max
    else:
        # Linear interpolation from min (oldest) to max (newest)
        for i, season in enumerate(sorted_seasons):
            fraction = i / (n_seasons - 1)
            weight = weight_min + fraction * (weight_max - weight_min)
            season_weight_map[season] = round(weight, 4)

    for season, weight in season_weight_map.items():
        logger.info(
            "  Season '%s' -> weight %.4f",
            season,
            weight,
        )

    # -----------------------------------------------------------------
    # Apply weights to training rows only
    # -----------------------------------------------------------------

    train_seasons = train_df["season"].astype(str)

    for season, weight in season_weight_map.items():
        mask = train_seasons == season
        weights.loc[mask] = weight

    # -----------------------------------------------------------------
    # Detailed logging
    # -----------------------------------------------------------------

    unique_weights = sorted(weights.unique())
    weight_counts = {
        f"{w:.4f}": int((weights == w).sum())
        for w in unique_weights
    }

    logger.info(
        "Applied recency weighting (strategy=%s): "
        "min_weight=%.4f, max_weight=%.4f, "
        "weight_distribution=%s.",
        settings.season_weight_strategy,
        float(weights.min()),
        float(weights.max()),
        weight_counts,
    )

    # Check if latest season is missing from training set
    latest_season = sorted_seasons[-1]
    train_latest_count = int(
        (train_seasons == latest_season).sum()
    )

    if train_latest_count == 0:
        logger.warning(
            "Latest season '%s' is not present in the training set. "
            "No max-weight training rows will exist because the latest "
            "season belongs entirely to the chronological test set.",
            latest_season,
        )

    return weights


def prepare_split_dataset(
    data: pd.DataFrame,
    settings: TrainingSettings,
) -> SplitDataset:
    """Select features, split chronologically, impute missing values,
    and apply recency weighting.

    The split remains chronological:

        older data -> training
        newest data -> test

    Training samples are weighted by season recency using a configurable
    strategy (see ``TrainingSettings.season_weight_strategy``):

        newest season  -> ``season_weight_max``  (default 3.0)
        oldest season  -> ``season_weight_min``  (default 1.0)
        intermediate   -> linearly interpolated

    The latest season is identified from the FULL dataset before splitting.

    The test set is never weighted.

    This allows the model to learn from historical seasons while giving
    more influence to the most recent training seasons.
    """

    # ---------------------------------------------------------------
    # 1. Validate target
    # ---------------------------------------------------------------

    if settings.target_column not in data.columns:
        raise ValueError(
            f"Target column '{settings.target_column}' not found in dataset."
        )

    working = data.dropna(
        subset=[settings.target_column]
    ).copy()

    if working.empty:
        raise ValueError(
            "No rows remain after dropping missing targets."
        )

    # ---------------------------------------------------------------
    # 2. Chronological sorting
    # ---------------------------------------------------------------

    sort_columns = [
        column
        for column in settings.chronological_columns
        if column in working.columns
    ]

    if sort_columns:
        working = (
            working
            .sort_values(
                by=sort_columns,
                kind="mergesort",
            )
            .reset_index(drop=True)
        )
    else:
        logger.warning(
            "None of the chronological columns %s are present; "
            "using existing row order for the train/test split.",
            settings.chronological_columns,
        )

    # ---------------------------------------------------------------
    # 3. Select model features
    # ---------------------------------------------------------------

    feature_columns = select_feature_columns(
        working,
        settings,
    )

    if not feature_columns:
        raise ValueError(
            "No usable feature columns were selected from the dataset."
        )

    # ---------------------------------------------------------------
    # 4. Chronological train/test split
    # ---------------------------------------------------------------

    split_index = int(
        len(working) * (1 - settings.test_fraction)
    )

    split_index = max(
        1,
        min(
            split_index,
            len(working) - 1,
        ),
    )

    train_df = working.iloc[:split_index].copy()
    test_df = working.iloc[split_index:].copy()

    logger.info(
        "Chronological split created: "
        "train=%d row(s), test=%d row(s).",
        len(train_df),
        len(test_df),
    )

    # ---------------------------------------------------------------
    # 5. Recency weighting
    # ---------------------------------------------------------------
    #
    # IMPORTANT:
    # Determine latest season from the FULL dataset.
    #
    # This avoids the old problem where "latest season" was calculated
    # only from train_df.
    #
    # Weights are configurable via TrainingSettings:
    #   season_weight_max  (newest season, default 3.0)
    #   season_weight_min  (oldest season, default 1.0)
    #   season_weight_strategy (default "linear")
    #
    # Only training rows receive these weights.
    # ---------------------------------------------------------------

    train_weights = _build_recency_weights(
        train_df=train_df,
        all_data=working,
        settings=settings,
    )

    # ---------------------------------------------------------------
    # 6. Convert features to numeric
    # ---------------------------------------------------------------

    X_train = (
        train_df[feature_columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
    )

    X_test = (
        test_df[feature_columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
    )

    # ---------------------------------------------------------------
    # 7. Leakage-free median imputation
    # ---------------------------------------------------------------

    raw_medians = (
        X_train
        .median(
            numeric_only=True,
        )
        .to_dict()
    )
    train_medians = {
        col: float(raw_medians[col])
        if col in raw_medians and pd.notna(raw_medians[col])
        else 0.0
        for col in feature_columns
    }

    if not X_train.empty:
        fallback_median = float(
            np.nanmedian(
                X_train.to_numpy(
                    dtype="float64"
                )
            )
        )
    else:
        fallback_median = 0.0

    X_train = (
        X_train
        .fillna(train_medians)
        .fillna(fallback_median)
    )

    X_test = (
        X_test
        .fillna(train_medians)
        .fillna(fallback_median)
    )

    # ---------------------------------------------------------------
    # 8. Target
    # ---------------------------------------------------------------

    y_train = pd.to_numeric(
        train_df[settings.target_column],
        errors="coerce",
    )

    y_test = pd.to_numeric(
        test_df[settings.target_column],
        errors="coerce",
    )

    # ---------------------------------------------------------------
    # 9. Reset indexes so X/y/weights line up cleanly
    # ---------------------------------------------------------------

    X_train = X_train.reset_index(drop=True)
    X_test = X_test.reset_index(drop=True)

    y_train = y_train.reset_index(drop=True)
    y_test = y_test.reset_index(drop=True)

    train_weights = train_weights.reset_index(drop=True)

    # ---------------------------------------------------------------
    # 10. Final validation
    # ---------------------------------------------------------------

    if len(X_train) != len(train_weights):
        raise ValueError(
            "Training weights length does not match X_train length: "
            f"{len(train_weights)} weights vs "
            f"{len(X_train)} training rows."
        )

    if not np.isfinite(
        train_weights.to_numpy(
            dtype="float64"
        )
    ).all():
        raise ValueError(
            "Training weights contain non-finite values."
        )

    if (
        train_weights <= 0
    ).any():
        raise ValueError(
            "Training weights must all be greater than zero."
        )

    # ---------------------------------------------------------------
    # 11. Logging
    # ---------------------------------------------------------------

    logger.info(
        "Prepared chronological split: "
        "%d train row(s), %d test row(s), %d feature(s).",
        len(X_train),
        len(X_test),
        len(feature_columns),
    )

    logger.info(
        "Final training weights: "
        "total=%.2f, min=%.2f, max=%.2f.",
        float(train_weights.sum()),
        float(train_weights.min()),
        float(train_weights.max()),
    )

    # ---------------------------------------------------------------
    # 12. Return
    # ---------------------------------------------------------------

    return SplitDataset(
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        feature_columns=feature_columns,
        train_medians={
            key: float(value)
            for key, value in train_medians.items()
        },
        train_weights=train_weights,
    )