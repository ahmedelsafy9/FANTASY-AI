"""Learning-to-Rank models grouped by Gameweek (Feedback 5).

Optimizes pairwise / listwise ranking of players within each target GW
using LambdaMART (LGBMRanker / XGBRanker).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

try:
    from lightgbm import LGBMRanker
except ImportError:
    LGBMRanker = None

try:
    from xgboost import XGBRanker
except ImportError:
    XGBRanker = None

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RankerModelResult:
    """Trained ranker model and metadata."""
    model_name: str
    model: object
    feature_cols: list[str] = field(default_factory=list)
    train_medians: dict = field(default_factory=dict)
    spearman: float = 0.0


def make_relevance_labels(y: pd.Series | np.ndarray) -> np.ndarray:
    """Map raw FPL points to integer relevance scores [0, 10] for LambdaMART."""
    arr = np.asarray(y, dtype=float)
    # Negative points -> 0; 0 pts -> 0; 1-2 pts -> 1; 3-5 pts -> 2; 6-7 pts -> 4; 8-9 pts -> 6; 10-12 pts -> 8; 13+ pts -> 10
    rel = np.zeros_like(arr, dtype=int)
    rel[arr >= 1] = 1
    rel[arr >= 3] = 2
    rel[arr >= 6] = 4
    rel[arr >= 8] = 6
    rel[arr >= 10] = 8
    rel[arr >= 13] = 10
    return rel


def build_ranker_estimator(random_state: int = 42) -> tuple[str, object]:
    """Build a ranking estimator using LightGBM Ranker or XGBRanker."""
    if LGBMRanker is not None:
        model = LGBMRanker(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.05,
            random_state=random_state,
            n_jobs=4,
            verbosity=-1,
        )
        return "lightgbm_ranker", model

    if XGBRanker is not None:
        model = XGBRanker(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.05,
            random_state=random_state,
            n_jobs=4,
        )
        return "xgboost_ranker", model

    raise RuntimeError("Neither LightGBM nor XGBoost is installed for ranking.")


def train_gameweek_ranker(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_points",
    season_col: str = "season",
    gw_col: str = "GW",
    random_state: int = 42,
) -> RankerModelResult:
    """Train a Learning-to-Rank model grouped by (season, GW).

    Args:
        df: Training DataFrame.
        feature_cols: Feature columns.
        target_col: Points target.
        season_col: Season column.
        gw_col: Gameweek column.
        random_state: Random seed.

    Returns:
        RankerModelResult with fitted model and metadata.
    """
    avail = [c for c in feature_cols if c in df.columns]
    working = (
        df.dropna(subset=[target_col, season_col, gw_col])
        .sort_values([season_col, gw_col])
        .reset_index(drop=True)
    )

    X = working[avail].apply(pd.to_numeric, errors="coerce")
    medians = X.median().to_dict()
    X = X.fillna(medians).fillna(0)

    y_raw = pd.to_numeric(working[target_col], errors="coerce").fillna(0).values
    y_rel = make_relevance_labels(y_raw)

    # Compute group sizes per (season, GW) query
    groups = working.groupby([season_col, gw_col], sort=False).size().values

    logger.info(
        "Training Gameweek Ranker on %d rows across %d gameweek queries...",
        len(working), len(groups),
    )

    name, model = build_ranker_estimator(random_state)
    model.fit(X, y_rel, group=groups)

    # In-sample ranking correlation
    preds = model.predict(X)
    sp_corr, _ = spearmanr(y_raw, preds)
    spearman = float(sp_corr) if np.isfinite(sp_corr) else 0.0

    logger.info("Gameweek Ranker trained (%s, in-sample Spearman: %.4f).", name, spearman)

    return RankerModelResult(
        model_name=name,
        model=model,
        feature_cols=avail,
        train_medians=medians,
        spearman=spearman,
    )


def predict_ranking_scores(
    ranker_result: RankerModelResult,
    df: pd.DataFrame,
) -> np.ndarray:
    """Generate ranking score predictions.

    Args:
        ranker_result: Trained RankerModelResult.
        df: DataFrame to predict on.

    Returns:
        np.ndarray: Continuous ranking scores.
    """
    if ranker_result.model is None:
        return np.zeros(len(df))

    avail = [c for c in ranker_result.feature_cols if c in df.columns]
    X = df[avail].apply(pd.to_numeric, errors="coerce").fillna(ranker_result.train_medians).fillna(0)
    return ranker_result.model.predict(X)
