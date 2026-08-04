"""Factory assembling the project's default candidate models.

Kept separate from the trainer so the trainer itself never knows which
concrete models exist — only this factory does. XGBoost and LightGBM
are optional dependencies: if either is not installed, that model is
skipped with a logged reason rather than crashing the whole pipeline,
so the baseline still runs (with scikit-learn's built-in models) in
any environment.
"""

from __future__ import annotations

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from src.config.logging_config import get_logger
from src.config.settings import TrainingSettings
from src.training.models import ModelSpec

logger = get_logger(__name__)


def build_default_model_specs(
    settings: TrainingSettings,
) -> tuple[list[ModelSpec], dict[str, str]]:
    """Build the standard set of candidate models for the Sprint 6 baseline.

    Args:
        settings: Training settings controlling each model's
            hyperparameters.

    Returns:
        tuple[list[ModelSpec], dict[str, str]]: The available model
        specs, and a mapping of skipped model name -> reason for any
        model whose library could not be imported.
    """
    specs: list[ModelSpec] = [
        ModelSpec(name="linear_regression", build=lambda: LinearRegression()),
        ModelSpec(
            name="random_forest",
            build=lambda: RandomForestRegressor(
                n_estimators=settings.random_forest_n_estimators,
                max_depth=settings.random_forest_max_depth,
                random_state=settings.random_state,
                n_jobs=-1,
            ),
        ),
    ]
    skipped: dict[str, str] = {}

    try:
        from xgboost import XGBRegressor

        specs.append(
            ModelSpec(
                name="xgboost",
                build=lambda: XGBRegressor(
                    n_estimators=settings.boosted_n_estimators,
                    max_depth=settings.boosted_max_depth,
                    learning_rate=settings.boosted_learning_rate,
                    random_state=settings.random_state,
                    n_jobs=-1,
                ),
            )
        )
    except ImportError as exc:
        reason = f"xgboost is not installed ({exc})."
        logger.warning("Skipping XGBoost: %s", reason)
        skipped["xgboost"] = reason

    try:
        from lightgbm import LGBMRegressor

        specs.append(
            ModelSpec(
                name="lightgbm",
                build=lambda: LGBMRegressor(
                    n_estimators=settings.boosted_n_estimators,
                    max_depth=settings.boosted_max_depth,
                    learning_rate=settings.boosted_learning_rate,
                    random_state=settings.random_state,
                    n_jobs=-1,
                    verbosity=-1,
                ),
            )
        )
    except ImportError as exc:
        reason = f"lightgbm is not installed ({exc})."
        logger.warning("Skipping LightGBM: %s", reason)
        skipped["lightgbm"] = reason

    return specs, skipped
