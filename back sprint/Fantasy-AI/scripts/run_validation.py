"""CLI entry point: validate the merged historical dataset and produce a report.

Usage:
    python -m scripts.run_validation
    python -m scripts.run_validation --input data/raw/vaastav_merged.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.validation.factory import build_default_checks
from src.validation.report_writer import write_markdown_report
from src.validation.validator import DatasetValidator

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Validate the merged historical FPL dataset."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to the merged dataset CSV. Defaults to the Sprint 2 output.",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Path the validation report should be written to.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run dataset validation and write a Markdown report.

    Args:
        argv: Optional argument list, primarily for testing.

    Returns:
        int: Process exit code (``0`` if validation passed, ``1`` if
        the dataset failed one or more checks or could not be read).
    """
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    input_path = (
        Path(args.input)
        if args.input
        else settings.paths.raw_data_dir / "vaastav_merged.csv"
    )
    report_path = (
        Path(args.report)
        if args.report
        else settings.paths.raw_data_dir / "validation_report.md"
    )

    if not input_path.exists():
        logger.error(
            "Input dataset not found at %s. Run scripts.run_historical_ingestion first.",
            input_path,
        )
        return 1

    data = pd.read_csv(input_path, low_memory=False)
    checks = build_default_checks(settings.validation)
    validator = DatasetValidator(checks=checks)

    report = validator.validate(data)
    write_markdown_report(report, report_path)

    if report.overall_passed:
        logger.info("Validation PASSED. Report written to %s.", report_path)
        return 0

    logger.warning(
        "Validation FAILED with %d total issue(s). See %s for details.",
        report.total_issue_count,
        report_path,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
