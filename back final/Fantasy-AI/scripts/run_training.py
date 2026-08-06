"""CLI entry point: train, evaluate, and compare baseline models; save the best one.

Usage:
    python -m scripts.run_training
    python -m scripts.run_training --input data/processed/vaastav_features.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.training.dataset import prepare_split_dataset
from src.training.factory import build_default_model_specs
from src.training.persistence import save_best_model
from src.training.report_writer import write_comparison_report
from src.training.trainer import ModelTrainer

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Train and compare baseline models on the engineered FPL dataset."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to the engineered dataset CSV. Defaults to the Sprint 5 output.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the training pipeline and save the best model.

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
    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = settings.paths.models_dir / "best_model_metadata.json"
    report_path = settings.paths.models_dir / "model_comparison_report.md"

    if not input_path.exists():
        logger.error(
            "Input dataset not found at %s. Run scripts.run_feature_engineering first.",
            input_path,
        )
        return 1

    data = pd.read_csv(input_path, low_memory=False)

    try:
        split = prepare_split_dataset(data, settings.training)
    except ValueError as exc:
        logger.error("Could not prepare training data: %s", exc)
        return 1

    model_specs, skipped_models = build_default_model_specs(settings.training)
    trainer = ModelTrainer(model_specs=model_specs, settings=settings.training)

    try:
        result = trainer.run(split, skipped_models)
    except RuntimeError as exc:
        logger.error("Training failed: %s", exc)
        return 1

    save_best_model(result, split, model_path, metadata_path)
    write_comparison_report(result, report_path)

    logger.info(
        "Best model: '%s'. Saved to %s. Report at %s.",
        result.best_model_name,
        model_path,
        report_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
