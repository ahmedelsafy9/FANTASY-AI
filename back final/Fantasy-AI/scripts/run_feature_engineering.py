"""CLI entry point: derive features from the cleaned dataset and save the result.

Usage:
    python -m scripts.run_feature_engineering
    python -m scripts.run_feature_engineering --input data/processed/vaastav_cleaned.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.feature_engineering.factory import build_default_feature_steps
from src.feature_engineering.pipeline import FeaturePipeline
from src.feature_engineering.summary_writer import write_summary

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Derive model-ready features from the cleaned FPL dataset."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to the cleaned dataset CSV. Defaults to the Sprint 4 output.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path the engineered dataset should be written to.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the feature engineering pipeline and save the engineered dataset.

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
        else settings.paths.processed_data_dir / "vaastav_cleaned.csv"
    )
    output_path = (
        Path(args.output)
        if args.output
        else settings.paths.processed_data_dir / "vaastav_features.csv"
    )
    summary_path = settings.paths.processed_data_dir / "feature_engineering_summary.json"

    if not input_path.exists():
        logger.error(
            "Input dataset not found at %s. Run scripts.run_preprocessing first.",
            input_path,
        )
        return 1

    data = pd.read_csv(input_path, low_memory=False)
    steps = build_default_feature_steps(settings.feature_engineering)
    pipeline = FeaturePipeline(steps=steps)

    result = pipeline.run(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.data.to_csv(output_path, index=False)
    write_summary(result, summary_path)

    logger.info(
        "Saved engineered dataset (%d rows, %d columns) to %s.",
        result.rows_after,
        result.data.shape[1],
        output_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
