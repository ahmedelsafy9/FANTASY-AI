"""CLI entry point: predict the next Gameweek for every player and export the result.

Usage:
    python -m scripts.run_prediction
    python -m scripts.run_prediction --input data/processed/vaastav_features.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.core.exceptions import FantasyAIError
from src.prediction.export import export_predictions
from src.prediction.loader import load_model
from src.prediction.next_gameweek import build_next_gameweek_rows
from src.prediction.predictor import PredictionService

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Predict next-Gameweek points for every player using the trained model."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to the engineered dataset CSV. Defaults to the Sprint 5 output.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path predictions.csv should be written to.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the prediction pipeline and export predictions.csv.

    Args:
        argv: Optional argument list, primarily for testing.

    Returns:
        int: Process exit code (``0`` on success, ``1`` on failure).
    """
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    input_path = (
        Path(args.input)
        if args.input
        else settings.paths.processed_data_dir / "vaastav_features.csv"
    )
    output_path = (
        Path(args.output) if args.output else settings.paths.processed_data_dir / "predictions.csv"
    )
    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = settings.paths.models_dir / "best_model_metadata.json"

    if not input_path.exists():
        logger.error(
            "Input dataset not found at %s. Run scripts.run_feature_engineering first.",
            input_path,
        )
        return 1

    try:
        loaded_model = load_model(model_path, metadata_path)
    except FantasyAIError as exc:
        logger.error("Could not load model: %s. Run scripts.run_training first.", exc)
        return 1

    data = pd.read_csv(input_path, low_memory=False)

    try:
        next_gw_rows = build_next_gameweek_rows(
            data,
            player_id_columns=settings.feature_engineering.player_id_columns,
            chronological_columns=settings.feature_engineering.chronological_columns,
            max_valid_gameweek=settings.prediction.max_valid_gameweek,
        )
        service = PredictionService(loaded_model)
        predictions = service.predict(next_gw_rows)
    except FantasyAIError as exc:
        logger.error("Prediction failed: %s", exc)
        return 1

    prediction_column = f"predicted_{loaded_model.target_column}"
    export_predictions(
        predictions,
        id_columns=settings.prediction.export_id_columns,
        prediction_column=prediction_column,
        output_path=output_path,
    )

    logger.info(
        "Predicted %s for %d player(s) using model '%s'. Saved to %s.",
        loaded_model.target_column,
        len(predictions),
        loaded_model.model_name,
        output_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
