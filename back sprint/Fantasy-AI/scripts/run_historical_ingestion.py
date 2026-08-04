"""CLI entry point: download, merge, and report on the Vaastav historical dataset.

Usage:
    python -m scripts.run_historical_ingestion
    python -m scripts.run_historical_ingestion --seasons 2022-23,2023-24
"""

from __future__ import annotations

import argparse
import sys

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.historical_dataset_service import HistoricalDatasetService
from src.data_collection.sources.vaastav_source import VaastavDataSource

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Download and merge the Vaastav historical FPL dataset."
    )
    parser.add_argument(
        "--seasons",
        type=str,
        default="",
        help=(
            "Comma-separated list of seasons to restrict ingestion to "
            "(e.g. '2022-23,2023-24'). Defaults to all detected seasons."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the historical dataset ingestion pipeline.

    Args:
        argv: Optional argument list, primarily for testing.

    Returns:
        int: Process exit code (``0`` on success, ``1`` on failure).
    """
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    seasons = tuple(s.strip() for s in args.seasons.split(",") if s.strip())
    seasons = seasons or settings.data_sources.vaastav_seasons

    source = VaastavDataSource(
        repo_url=settings.data_sources.vaastav_repo_url,
        seasons=seasons,
        timeout_seconds=settings.data_sources.request_timeout_seconds,
        max_retries=settings.data_sources.request_max_retries,
    )
    service = HistoricalDatasetService(data_source=source)

    download_dir = settings.paths.raw_data_dir / "vaastav"
    raw_dataset_path = settings.paths.raw_data_dir / "vaastav_merged.csv"
    report_path = settings.paths.raw_data_dir / "vaastav_metadata_report.md"

    try:
        result = service.build(
            download_dir=download_dir,
            raw_dataset_path=raw_dataset_path,
            report_path=report_path,
        )
    except FantasyAIError as exc:
        logger.error("Historical dataset ingestion failed: %s", exc)
        return 1

    logger.info(
        "Done. %d rows across %d seasons saved to %s. Report at %s.",
        result.row_count,
        len(result.seasons),
        result.raw_dataset_path,
        result.report_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
