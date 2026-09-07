"""GW-level expanding walk-forward temporal cross-validation.

Implements strictly chronological train/predict splits at Gameweek granularity.
For every historical GW t:
    Train set:  all data where (season, GW) < (season_t, GW_t)
    Predict:    data at (season_t, GW_t)

A prediction for GW t NEVER uses any information from GW t or later.
Season boundaries are handled correctly via a unified chronological index.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def _season_start_year(season_str: str) -> int | None:
    """Parse '2022-23' into 2022."""
    m = re.match(r"^((?:19|20)\d{2})-\d{2}$", str(season_str).strip())
    return int(m.group(1)) if m else None


def make_temporal_index(df: pd.DataFrame,
                        season_col: str = "season",
                        gw_col: str = "GW") -> pd.Series:
    """Create a sortable integer index: season_start_year * 100 + GW.

    This ensures strict chronological ordering across season boundaries:
      2022-23 GW38 (202238) < 2023-24 GW1 (202301).

    Args:
        df: DataFrame with season and GW columns.
        season_col: Name of the season column.
        gw_col: Name of the gameweek column.

    Returns:
        pd.Series: Integer temporal index aligned with df's index.
    """
    season_years = df[season_col].map(
        lambda s: _season_start_year(s) if pd.notna(s) else None
    )
    gw = pd.to_numeric(df[gw_col], errors="coerce").fillna(0).astype(int)
    return (season_years.fillna(0).astype(int) * 100 + gw).astype(int)


@dataclass
class WalkForwardFold:
    """One fold of a walk-forward cross-validation.

    Attributes:
        fold_id: Sequential fold identifier.
        train_mask: Boolean mask for training rows in the source DataFrame.
        predict_mask: Boolean mask for prediction rows.
        train_temporal_max: The maximum temporal index in the training set.
        predict_temporal_idx: The temporal index of the prediction window.
        season: Season string for the prediction window.
        gw: Gameweek number for the prediction window.
    """
    fold_id: int
    train_mask: np.ndarray
    predict_mask: np.ndarray
    train_temporal_max: int
    predict_temporal_idx: int
    season: str
    gw: int


def generate_walk_forward_folds(
    df: pd.DataFrame,
    min_train_gameweeks: int = 38,
    season_col: str = "season",
    gw_col: str = "GW",
    fold_step: int = 1,
) -> list[WalkForwardFold]:
    """Generate GW-level expanding walk-forward folds.

    For each unique (season, GW) combination in chronological order,
    produces a fold where:
    - Training set = all rows with temporal_index < this fold's temporal_index
    - Prediction set = all rows at this fold's (season, GW)

    When ``fold_step > 1``, consecutive GWs are batched: the model is
    trained once per block of ``fold_step`` GWs, using data strictly
    before the block's first GW, and predicts all GWs in the block.
    Each GW within the block still gets its own fold (with the same
    training mask), preserving per-GW OOF granularity.

    Args:
        df: Full dataset with season and GW columns.
        min_train_gameweeks: Minimum number of distinct (season, GW) pairs
            in the training set before the first prediction fold is generated.
        season_col: Name of the season column.
        gw_col: Name of the gameweek column.
        fold_step: Number of consecutive GWs to batch per model training.
            Default 1 = one model per GW (finest granularity).

    Returns:
        list[WalkForwardFold]: Chronologically ordered folds.
    """
    temporal_idx = make_temporal_index(df, season_col, gw_col)

    # Get unique (season, GW) combinations sorted chronologically
    gw_keys = (
        df[[season_col, gw_col]]
        .drop_duplicates()
        .assign(_tidx=lambda x: make_temporal_index(x, season_col, gw_col))
        .sort_values("_tidx")
        .reset_index(drop=True)
    )

    folds: list[WalkForwardFold] = []
    fold_id = 0
    step = max(1, fold_step)

    i = min_train_gameweeks
    while i < len(gw_keys):
        # The training cutoff is the first GW in this block
        block_start_row = gw_keys.iloc[i]
        block_start_tidx = int(block_start_row["_tidx"])
        train_mask = (temporal_idx < block_start_tidx).values

        if train_mask.sum() == 0:
            i += step
            continue

        # Predict all GWs in this block [i, i+step)
        for j in range(i, min(i + step, len(gw_keys))):
            predict_row = gw_keys.iloc[j]
            predict_tidx = int(predict_row["_tidx"])
            predict_season = str(predict_row[season_col])
            predict_gw = int(predict_row[gw_col])

            predict_mask = (temporal_idx == predict_tidx).values

            if predict_mask.sum() == 0:
                continue

            folds.append(WalkForwardFold(
                fold_id=fold_id,
                train_mask=train_mask,
                predict_mask=predict_mask,
                train_temporal_max=block_start_tidx - 1,
                predict_temporal_idx=predict_tidx,
                season=predict_season,
                gw=predict_gw,
            ))
            fold_id += 1

        i += step

    logger.info(
        "Generated %d walk-forward folds (min_train_gws=%d, "
        "total unique GWs=%d, fold_step=%d).",
        len(folds), min_train_gameweeks, len(gw_keys), step,
    )
    return folds


def run_walk_forward_predictions(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    model_builder,
    min_train_gameweeks: int = 38,
    season_col: str = "season",
    gw_col: str = "GW",
    sample_weight_fn=None,
    fit_kwargs_fn=None,
    fold_step: int = 1,
) -> pd.DataFrame:
    """Run walk-forward predictions and return OOF predictions.

    For each fold, trains a fresh model on all data before the prediction
    window, then predicts the prediction window. Returns a DataFrame
    with predictions aligned to the original rows.

    When ``fold_step > 1``, folds sharing the same training cutoff reuse
    the same model (trained once per block), significantly reducing
    computation.

    Args:
        df: Full dataset.
        feature_cols: Feature column names.
        target_col: Target column name.
        model_builder: Callable returning a fresh unfitted estimator.
        min_train_gameweeks: Minimum training GWs before first fold.
        season_col: Season column name.
        gw_col: GW column name.
        sample_weight_fn: Optional callable(train_df) -> weight array.
        fit_kwargs_fn: Optional callable(model, train_X, train_y) -> dict
            of extra kwargs for model.fit().
        fold_step: Number of consecutive GWs per model training block.

    Returns:
        pd.DataFrame: Copy of df with added column ``f"oof_{target_col}"``
            containing out-of-fold predictions. Rows not covered by any
            fold have NaN.
    """
    folds = generate_walk_forward_folds(
        df, min_train_gameweeks, season_col, gw_col, fold_step=fold_step
    )

    result = df.copy()
    oof_col = f"oof_{target_col}"
    result[oof_col] = np.nan

    available_features = [c for c in feature_cols if c in df.columns]
    if not available_features:
        logger.warning("No feature columns available for walk-forward prediction of %s.", target_col)
        return result

    # Cache: train_temporal_max -> (fitted_model, train_medians)
    model_cache: dict[int, tuple] = {}
    n_trainings = 0

    for fold in folds:
        cache_key = fold.train_temporal_max

        if cache_key not in model_cache:
            # Train a new model for this block
            train_df = df.loc[fold.train_mask]

            X_train = train_df[available_features].apply(pd.to_numeric, errors="coerce")
            y_train = pd.to_numeric(train_df[target_col], errors="coerce")

            valid_mask = y_train.notna()
            X_train = X_train.loc[valid_mask]
            y_train = y_train.loc[valid_mask]

            if len(X_train) < 10:
                model_cache[cache_key] = (None, None)
                continue

            train_medians = X_train.median()
            X_train = X_train.fillna(train_medians).fillna(0)

            model = model_builder()

            fit_kw: dict = {}
            if sample_weight_fn is not None:
                weights = sample_weight_fn(train_df.loc[valid_mask])
                if weights is not None:
                    fit_kw["sample_weight"] = weights

            if fit_kwargs_fn is not None:
                extra = fit_kwargs_fn(model, X_train, y_train)
                if extra:
                    fit_kw.update(extra)

            try:
                model.fit(X_train, y_train, **fit_kw)
                model_cache[cache_key] = (model, train_medians)
                n_trainings += 1
            except Exception as exc:
                logger.warning(
                    "Walk-forward block (max_tidx=%d) training failed: %s",
                    cache_key, exc,
                )
                model_cache[cache_key] = (None, None)
                continue

        cached_model, cached_medians = model_cache[cache_key]
        if cached_model is None:
            continue

        # Predict this fold's window
        pred_df = df.loc[fold.predict_mask]
        X_pred = pred_df[available_features].apply(pd.to_numeric, errors="coerce")
        X_pred = X_pred.fillna(cached_medians).fillna(0)

        try:
            preds = cached_model.predict(X_pred)
            result.loc[fold.predict_mask, oof_col] = preds
        except Exception as exc:
            logger.warning(
                "Walk-forward fold %d (season=%s, GW=%d) prediction failed: %s",
                fold.fold_id, fold.season, fold.gw, exc,
            )

    n_predicted = result[oof_col].notna().sum()
    logger.info(
        "Walk-forward OOF for '%s': %d/%d rows predicted (%.1f%%), "
        "%d model trainings (fold_step=%d).",
        target_col, n_predicted, len(result),
        100 * n_predicted / max(len(result), 1),
        n_trainings, fold_step,
    )
    return result

