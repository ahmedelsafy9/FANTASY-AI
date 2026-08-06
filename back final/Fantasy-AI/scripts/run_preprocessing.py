"""CLI entry point: clean the merged historical dataset and save the result.

Usage:
    python -m scripts.run_preprocessing
    python -m scripts.run_preprocessing --input data/raw/vaastav_merged.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.preprocessing.factory import build_default_pipeline_steps
from src.preprocessing.pipeline import PreprocessingPipeline
from src.preprocessing.summary_writer import write_summary

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Clean and normalize the merged historical FPL dataset."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to the merged dataset CSV. Defaults to the Sprint 2 output.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path the cleaned dataset should be written to.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the preprocessing pipeline and save the cleaned dataset.

    Args:
        argv: Optional argument list, primarily for testing.

    Returns:
        int: Process exit code (``0`` on success, ``1`` on failure).
    """
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    input_path = (
        Path(args.input) if args.input else settings.paths.raw_data_dir / "vaastav_merged.csv"
    )
    output_path = (
        Path(args.output)
        if args.output
        else settings.paths.processed_data_dir / "vaastav_cleaned.csv"
    )
    summary_path = settings.paths.processed_data_dir / "preprocessing_summary.json"

    if not input_path.exists():
        logger.error(
            "Input dataset not found at %s. Run scripts.run_historical_ingestion first.",
            input_path,
        )
        return 1

    data = pd.read_csv(input_path, low_memory=False)

    # Detect Vaastav per-season reference data directory (teams.csv,
    # fixtures.csv, players_raw.csv) — used to populate the team column
    # and resolve opponents for older seasons where 'team' is absent.
    vaastav_data_dir = settings.paths.raw_data_dir / "vaastav" / "data"
    if not vaastav_data_dir.exists():
        vaastav_data_dir = None
        logger.info(
            "Vaastav reference data directory not found; fixture-based "
            "opponent resolution will use in-data grouping only."
        )

    steps = build_default_pipeline_steps(
        settings.preprocessing,
        settings.validation,
        vaastav_data_dir=vaastav_data_dir,
    )
    pipeline = PreprocessingPipeline(steps=steps)

    result = pipeline.run(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.data.to_csv(output_path, index=False)
    write_summary(result, summary_path)

    logger.info(
        "Saved cleaned dataset (%d rows, %d columns) to %s.",
        result.rows_after,
        result.data.shape[1],
        output_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
