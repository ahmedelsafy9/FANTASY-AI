"""Multi-Objective / Multi-Head FPL Player Scoring Model.

Integrates the frozen Score_D multi-objective scoring architecture:
    Score_D = P(play) * E(points | play) * (1 + 0.5 * P(>=6) + 0.25 * P(>=10))

Separates play probability, conditional points, and high-score tail probabilities
while preserving the calibrated ranking power of the production model.
"""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from src.config.logging_config import get_logger
from src.core.exceptions import ModelNotFoundError
from src.prediction.loader import LoadedModel

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Calibration Compatibility
# ---------------------------------------------------------------------------


class ProbabilityCalibrator:
    """Encapsulates a probability calibration method (raw, platt, isotonic).

    Maintains pickle-compatibility with calibrators saved during the
    multi-objective scoring experiment.
    """

    def __init__(self, method: str = "raw"):
        self.method = method
        self.calibrator = None

    def fit(self, probs: np.ndarray, y_true: np.ndarray):
        probs = np.clip(probs, 1e-6, 1.0 - 1e-6)
        if self.method == "platt":
            logits = np.log(probs / (1.0 - probs)).reshape(-1, 1)
            self.calibrator = LogisticRegression(max_iter=1000, random_state=42)
            self.calibrator.fit(logits, y_true)
        elif self.method == "isotonic":
            self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.calibrator.fit(probs, y_true)
        else:
            self.method = "raw"
        return self

    def predict(self, probs: np.ndarray) -> np.ndarray:
        probs = np.clip(probs, 1e-6, 1.0 - 1e-6)
        if self.method == "platt" and self.calibrator is not None:
            logits = np.log(probs / (1.0 - probs)).reshape(-1, 1)
            return self.calibrator.predict_proba(logits)[:, 1]
        elif self.method == "isotonic" and self.calibrator is not None:
            return np.clip(self.calibrator.predict(probs), 0.0, 1.0)
        return probs


# Ensure joblib unpickling can find ProbabilityCalibrator under its original module path
_orig_mod_path = "models.experiments.multi_objective_scoring.calibrator"
if _orig_mod_path not in sys.modules:
    # Ensure intermediate packages exist in sys.modules
    parts = _orig_mod_path.split(".")
    current = ""
    for part in parts:
        current = f"{current}.{part}" if current else part
        if current not in sys.modules:
            sys.modules[current] = types.ModuleType(current)
    sys.modules[_orig_mod_path].ProbabilityCalibrator = ProbabilityCalibrator


# ---------------------------------------------------------------------------
# MultiObjectiveModel
# ---------------------------------------------------------------------------


class MultiObjectiveModel:
    """Multi-Head FPL Player Scoring Model implementing Score_D.

    Heads:
        1. play_model: Probability of player participating (minutes > 0).
        2. points_model: Conditional expected points given the player plays.
        3. p6_model: Probability of a haul (points >= 6).
        4. p10_model: Probability of an extreme haul (points >= 10).

    Frozen parameters:
        alpha = 0.5  (haul weight)
        beta  = 0.25 (extreme haul weight)
        Score_D = P(play) * E(points | play) * (1 + 0.5 * P6 + 0.25 * P10)
    """

    # Frozen experiment parameters
    ALPHA: float = 0.5
    BETA: float = 0.25

    def __init__(
        self,
        play_model: Any,
        points_model: Any,
        p6_model: Any,
        p10_model: Any,
        play_calibrator: Any,
        p6_calibrator: Any,
        p10_calibrator: Any,
        feature_columns: list[str],
        train_medians: dict[str, float],
        alpha: float = ALPHA,
        beta: float = BETA,
    ):
        self.play_model = play_model
        self.points_model = points_model
        self.p6_model = p6_model
        self.p10_model = p10_model

        self.play_calibrator = play_calibrator
        self.p6_calibrator = p6_calibrator
        self.p10_calibrator = p10_calibrator

        self.feature_columns = list(feature_columns)
        self.train_medians = dict(train_medians)
        self.alpha = alpha
        self.beta = beta

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Align columns to the exact expected feature vector and impute medians."""
        X = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            if col in df.columns:
                X[col] = pd.to_numeric(df[col], errors="coerce").fillna(self.train_medians.get(col, 0.0))
            else:
                X[col] = self.train_medians.get(col, 0.0)
        return X[self.feature_columns]

    def predict_raw(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        """Compute all calibrated head predictions and the synthesized Score_D.

        Returns:
            dict containing p_play, exp_pts_if_play, exp_pts, p6, p10, and score_d.
        """
        X = self._prepare_features(df)

        # 1. P(play)
        play_raw = self.play_model.predict_proba(X)[:, 1]
        p_play = np.clip(self.play_calibrator.predict(play_raw), 0.0, 1.0)

        # 2. E(points | play)
        exp_pts_if_play = self.points_model.predict(X)

        # 3. P(points >= 6)
        p6_raw = self.p6_model.predict_proba(X)[:, 1]
        p6 = np.clip(self.p6_calibrator.predict(p6_raw), 0.0, 1.0)

        # 4. P(points >= 10)
        p10_raw = self.p10_model.predict_proba(X)[:, 1]
        p10 = np.clip(self.p10_calibrator.predict(p10_raw), 0.0, 1.0)

        # Unconditional expected points (Score A)
        exp_pts = p_play * exp_pts_if_play

        # Synthesized Score D (Frozen formula)
        score_d = exp_pts * (1.0 + self.alpha * p6 + self.beta * p10)

        return {
            "p_play": p_play,
            "expected_points_if_play": exp_pts_if_play,
            "expected_points": exp_pts,
            "p6": p6,
            "p10": p10,
            "score_d": score_d,
        }

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Standard scikit-learn estimator predict interface.

        Returns Score_D predictions as a 1D float array.
        """
        if isinstance(X, np.ndarray):
            df = pd.DataFrame(X, columns=self.feature_columns[: X.shape[1]])
        else:
            df = X
        raw = self.predict_raw(df)
        return np.asarray(raw["score_d"], dtype=float)

    def predict_breakdown(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Generate structured breakdown matching PredictionService and API expectations.

        Returns a DataFrame indexed like ``rows`` containing both Score_D
        and individual calibrated objective head probabilities.
        """
        raw = self.predict_raw(rows)

        return pd.DataFrame(
            {
                # Backward-compatibility: primary prediction mapped to Score_D
                "predicted_total_points": raw["score_d"],
                "predicted_expected_points": raw["expected_points"],
                # Explicit multi-objective fields requested by API
                "score_d": raw["score_d"],
                "play_probability": raw["p_play"],
                "conditional_expected_points": raw["expected_points_if_play"],
                "p6_probability": raw["p6"],
                "p10_probability": raw["p10"],
                # Canonical aliases for API backwards compatibility
                "predicted_score_d": raw["score_d"],
                "predicted_play_probability": raw["p_play"],
                "predicted_conditional_expected_points": raw["expected_points_if_play"],
                "predicted_p6_probability": raw["p6"],
                "predicted_p10_probability": raw["p10"],
                "predicted_p_play_any": raw["p_play"],
                "captaincy_score": raw["score_d"],
            },
            index=rows.index,
        )


# ---------------------------------------------------------------------------
# Factory Loader
# ---------------------------------------------------------------------------


def load_multi_objective_model(
    experiment_dir: Path | str | None = None,
) -> LoadedModel:
    """Load the trained multi-objective models and calibrators into a LoadedModel.

    Args:
        experiment_dir: Path to ``models/experiments/multi_objective_scoring``.
            If None, resolves relative to repository root.

    Returns:
        LoadedModel: A unified model wrapper compatible with PredictionService.

    Raises:
        ModelNotFoundError: If required model or calibrator files are missing.
    """
    if experiment_dir is None:
        project_root = Path(__file__).resolve().parents[2]
        exp_path = project_root / "models" / "experiments" / "multi_objective_scoring"
    else:
        exp_path = Path(experiment_dir)

    models_dir = exp_path / "models"
    calibrators_dir = exp_path / "calibrators"
    config_file = exp_path / "config.json"
    medians_file = models_dir / "imputer_medians.json"

    # Validate required artifacts
    required_files = [
        models_dir / "play_model.joblib",
        models_dir / "points_model.joblib",
        models_dir / "p6_model.joblib",
        models_dir / "p10_model.joblib",
        calibrators_dir / "play_calibrator.joblib",
        calibrators_dir / "p6_calibrator.joblib",
        calibrators_dir / "p10_calibrator.joblib",
        config_file,
    ]
    for rf in required_files:
        if not rf.exists():
            raise ModelNotFoundError(f"Multi-objective artifact missing: {rf}")

    try:
        config_data = json.loads(config_file.read_text(encoding="utf-8"))
        feature_columns = config_data.get("features", [])
        if not feature_columns:
            raise ValueError("config.json missing 'features' list")
    except Exception as exc:
        raise ModelNotFoundError(f"Could not load multi-objective config from {config_file}: {exc}") from exc

    train_medians: dict[str, float] = {}
    if medians_file.exists():
        try:
            train_medians = json.loads(medians_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not load imputer medians from %s: %s", medians_file, exc)

    try:
        play_model = joblib.load(models_dir / "play_model.joblib")
        points_model = joblib.load(models_dir / "points_model.joblib")
        p6_model = joblib.load(models_dir / "p6_model.joblib")
        p10_model = joblib.load(models_dir / "p10_model.joblib")

        play_calibrator = joblib.load(calibrators_dir / "play_calibrator.joblib")
        p6_calibrator = joblib.load(calibrators_dir / "p6_calibrator.joblib")
        p10_calibrator = joblib.load(calibrators_dir / "p10_calibrator.joblib")
    except Exception as exc:
        raise ModelNotFoundError(f"Failed to load multi-objective model components: {exc}") from exc

    model = MultiObjectiveModel(
        play_model=play_model,
        points_model=points_model,
        p6_model=p6_model,
        p10_model=p10_model,
        play_calibrator=play_calibrator,
        p6_calibrator=p6_calibrator,
        p10_calibrator=p10_calibrator,
        feature_columns=feature_columns,
        train_medians=train_medians,
        alpha=0.5,
        beta=0.25,
    )

    logger.info(
        "Successfully loaded MultiObjectiveModel (Score_D, alpha=0.5, beta=0.25, %d features).",
        len(feature_columns),
    )

    return LoadedModel(
        model=model,
        model_name="multi_objective_score_d",
        feature_columns=feature_columns,
        target_column="total_points",
        train_medians=train_medians,
        metrics={
            "alpha": 0.5,
            "beta": 0.25,
            "ndcg_at_10": 0.3792,
            "spearman": 0.6996,
            "precision_at_10": 0.1182,
        },
    )
