"""CLI entry point: refresh data, re-run the pipeline, version results, and
optionally retrain.

Usage:
    python -m scripts.run_automation
    python -m scripts.run_automation --retrain
    python -m scripts.run_automation --no-live
"""

from __future__ import annotations

import argparse
import sys

from src.automation.update_pipeline import AutomationOrchestrator
from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Refresh the dataset, re-run the pipeline, version results, "
        "and optionally retrain."
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Retrain candidate models and promote the winner only if it improves "
        "on the current best model.",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Skip pulling the latest Gameweek from the live FPL API; refresh "
        "historical data only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline including retraining, but do NOT promote "
        "the new model to best_model. Useful for validating the pipeline "
        "without affecting production.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run one full automation cycle.

    Args:
        argv: Optional argument list, primarily for testing.

    Returns:
        int: Process exit code (always ``0`` — partial failures, such
        as live ingestion being unavailable, are logged and recorded
        in the run's notes rather than treated as a hard error).
    """
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    orchestrator = AutomationOrchestrator(settings)
    result = orchestrator.run(
        retrain=args.retrain,
        ingest_live=not args.no_live,
        dry_run=args.dry_run,
    )

    logger.info("=== Automation Run Summary ===")
    logger.info("Historical data updated: %s", result.historical_data_updated)
    logger.info("Live Gameweek ingested: %s", result.live_gameweek_ingested)
    logger.info("Raw data version: %s (changed=%s)", result.raw_data_version, result.raw_data_changed)
    logger.info("Engineered data version: %s", result.engineered_data_version)
    if result.dry_run:
        logger.info("Mode: DRY RUN (no promotion)")
    if result.retrain_attempted:
        logger.info(
            "Retrain: attempted=True, promoted=%s, new_version=%s",
            result.retrain_promoted,
            result.new_model_version,
        )
        if result.promotion_reason:
            logger.info("Promotion reason: %s", result.promotion_reason)
    for note in result.notes:
        logger.info("Note: %s", note)

    return 0


if __name__ == "__main__":
    sys.exit(main())
