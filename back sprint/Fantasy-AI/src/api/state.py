"""Builds the API's application state once at startup.

Loading the engineered dataset and trained model, and computing
next-Gameweek predictions, are all relatively expensive — this module
does that work exactly once (at process startup) rather than per
request.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.prediction.loader import LoadedModel, load_model
from src.prediction.next_gameweek import build_next_gameweek_rows
from src.prediction.predictor import PredictionService

logger = get_logger(__name__)


@dataclass
class AppState:
    """Everything the API's route handlers need, computed once at startup.

    Attributes:
        settings: The application settings used to build this state.
        engineered_data: The full engineered dataset (Sprint 5 output).
        loaded_model: The trained model and its reproducibility metadata.
        predictions: Next-Gameweek predictions for every player,
            including every engineered feature column (not just the
            trimmed CSV export columns), so services like the captain
            picker can filter on them.
        player_id_column: The resolved player identifier column name.
    """

    settings: Settings
    engineered_data: pd.DataFrame
    loaded_model: LoadedModel
    predictions: pd.DataFrame
    player_id_column: str


def build_app_state(settings: Settings) -> AppState:
    """Load data and the trained model, and compute predictions, once.

    Args:
        settings: Application settings.

    Returns:
        AppState: The fully populated application state.

    Raises:
        FileNotFoundError: If the engineered dataset is missing.
        src.core.exceptions.ModelNotFoundError: If the model artifact
            or its metadata is missing.
        src.core.exceptions.PredictionError: If next-Gameweek rows
            cannot be built (e.g. no player identifier column).
    """
    features_path = settings.paths.processed_data_dir / "vaastav_features.csv"
    if not features_path.exists():
        raise FileNotFoundError(
            f"Engineered dataset not found at {features_path}. "
            "Run scripts.run_feature_engineering first."
        )

    logger.info("Loading engineered dataset from %s...", features_path)
    engineered_data = pd.read_csv(features_path, low_memory=False)

    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = settings.paths.models_dir / "best_model_metadata.json"
    loaded_model = load_model(model_path, metadata_path)

    next_gw_rows = build_next_gameweek_rows(
        engineered_data,
        player_id_columns=settings.feature_engineering.player_id_columns,
        chronological_columns=settings.feature_engineering.chronological_columns,
        max_valid_gameweek=settings.prediction.max_valid_gameweek,
    )
    prediction_service = PredictionService(loaded_model)
    predictions = prediction_service.predict(next_gw_rows)

    player_id_column = next(
        (c for c in settings.feature_engineering.player_id_columns if c in engineered_data.columns),
        None,
    )
    if player_id_column is None:
        raise ValueError(
            f"No player identifier column found among "
            f"{settings.feature_engineering.player_id_columns}."
        )

    logger.info(
        "API state ready: %d player(s), model '%s'.", len(predictions), loaded_model.model_name
    )
    return AppState(
        settings=settings,
        engineered_data=engineered_data,
        loaded_model=loaded_model,
        predictions=predictions,
        player_id_column=player_id_column,
    )
