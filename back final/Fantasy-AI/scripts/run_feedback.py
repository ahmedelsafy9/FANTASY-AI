"""CLI entry point: feedback learning system operations.

Usage:
    python -m scripts.run_feedback generate   # Generate feedback for completed GWs
    python -m scripts.run_feedback train      # Train/update residual model
    python -m scripts.run_feedback evaluate   # Walk-forward evaluation
    python -m scripts.run_feedback analyze    # Error analysis and bias discovery
    python -m scripts.run_feedback predict    # Generate predictions with correction
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings
from src.prediction.feedback.feedback_adapter import FeedbackAdapter
from src.prediction.feedback.feedback_analyzer import FeedbackAnalyzer
from src.prediction.feedback.feedback_store import FeedbackStore
from src.prediction.feedback.evaluation import FeedbackEvaluator
from src.prediction.feedback.residual_model import ResidualModel
from src.prediction.feedback.snapshot_store import PredictionSnapshotStore

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Feedback learning system for Fantasy-AI predictions."
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command")

    # Generate feedback
    gen = subparsers.add_parser("generate", help="Generate feedback for completed GWs")
    gen.add_argument("--season", type=str, help="Season (auto-detected if omitted)")
    gen.add_argument("--gw", type=int, help="Specific GW to generate feedback for")

    # Train residual model
    train = subparsers.add_parser("train", help="Train/update the residual model")
    train.add_argument("--season", type=str, help="Season to train on")

    # Evaluate
    evaluate = subparsers.add_parser("evaluate", help="Walk-forward evaluation")
    evaluate.add_argument("--season", type=str, help="Season to evaluate")

    # Analyze
    analyze = subparsers.add_parser("analyze", help="Error analysis and bias discovery")
    analyze.add_argument("--season", type=str, help="Season to analyze")
    analyze.add_argument("--gw", type=int, help="Specific GW to analyze")

    # Predict
    predict = subparsers.add_parser("predict", help="Generate corrected predictions")
    predict.add_argument("--season", type=str, help="Season")
    predict.add_argument("--gw", type=int, help="Target GW")

    return parser.parse_args(argv)


def _get_stores(settings):
    """Create feedback infrastructure instances."""
    snapshot_dir = settings.paths.processed_data_dir / settings.feedback.snapshot_dir_name
    feedback_dir = settings.paths.processed_data_dir / settings.feedback.feedback_dir_name
    model_dir = settings.paths.models_dir / settings.feedback.feedback_model_dir_name

    return (
        PredictionSnapshotStore(snapshot_dir),
        FeedbackStore(feedback_dir),
        ResidualModel(
            model_dir=model_dir,
            n_estimators=settings.feedback.residual_n_estimators,
            max_depth=settings.feedback.residual_max_depth,
            learning_rate=settings.feedback.residual_learning_rate,
        ),
    )


def _detect_season(data: pd.DataFrame) -> str:
    """Detect the current season from data."""
    if "season" in data.columns:
        return str(data["season"].max())
    return "unknown"


def cmd_generate(args: argparse.Namespace, settings) -> int:
    """Generate feedback for completed Gameweeks."""
    snapshot_store, feedback_store, _ = _get_stores(settings)

    # Load raw data for actual results
    raw_path = settings.paths.raw_data_dir / "vaastav_merged.csv"
    if not raw_path.exists():
        logger.error("Raw dataset not found at %s", raw_path)
        return 1

    raw = pd.read_csv(raw_path, low_memory=False)
    season = args.season or _detect_season(raw)

    # Get available snapshots
    snapshots = snapshot_store.list_snapshots()
    season_snapshots = [(s, gw) for s, gw in snapshots if s == season]

    if not season_snapshots:
        logger.info("No prediction snapshots found for season %s.", season)
        return 0

    generated = 0
    for snap_season, snap_gw in season_snapshots:
        if args.gw is not None and snap_gw != args.gw:
            continue

        snapshot = snapshot_store.load_snapshot(snap_season, snap_gw)
        if snapshot is None:
            continue

        # Check if actual data exists for this GW
        season_data = raw[raw["season"] == snap_season] if "season" in raw.columns else raw
        gw_data = season_data[
            pd.to_numeric(season_data["GW"], errors="coerce") == snap_gw
        ] if "GW" in season_data.columns else pd.DataFrame()

        if gw_data.empty:
            logger.info(
                "No actual data yet for %s GW%d — skipping feedback generation.",
                snap_season, snap_gw,
            )
            continue

        feedback_store.generate_feedback(snapshot, gw_data, snap_season, snap_gw)
        generated += 1

    logger.info("Generated feedback for %d Gameweek(s).", generated)
    return 0


def cmd_train(args: argparse.Namespace, settings) -> int:
    """Train the residual model."""
    _, feedback_store, residual_model = _get_stores(settings)

    feedback = feedback_store.load_feedback(season=args.season)
    if feedback.empty:
        logger.info("No feedback available for training.")
        return 0

    adapter = FeedbackAdapter(feedback_store, residual_model, settings.feedback)
    season = args.season or (
        str(feedback["season"].iloc[0]) if "season" in feedback.columns else "unknown"
    )
    max_gw = int(feedback["GW"].max()) if "GW" in feedback.columns else 38

    success = adapter.update_model(season, max_gw)
    if success:
        logger.info("Residual model trained successfully.")
    else:
        logger.info("Residual model training was not possible (insufficient data).")
    return 0


def cmd_evaluate(args: argparse.Namespace, settings) -> int:
    """Run walk-forward evaluation."""
    _, feedback_store, _ = _get_stores(settings)

    feedback = feedback_store.load_feedback(season=args.season)
    if feedback.empty:
        logger.info("No feedback available for evaluation.")
        return 0

    result = FeedbackEvaluator.evaluate_from_feedback(
        feedback, min_gameweeks=settings.feedback.min_feedback_gameweeks
    )

    report = FeedbackEvaluator.format_comparison(result)
    print(report)

    # Save report
    report_path = settings.paths.models_dir / settings.feedback.feedback_model_dir_name / "evaluation_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    logger.info("Evaluation report saved to %s", report_path)

    return 0


def cmd_analyze(args: argparse.Namespace, settings) -> int:
    """Run error analysis."""
    _, feedback_store, _ = _get_stores(settings)

    feedback = feedback_store.load_feedback(season=args.season)
    if feedback.empty:
        logger.info("No feedback available for analysis.")
        return 0

    if args.gw is not None:
        feedback = feedback[pd.to_numeric(feedback["GW"], errors="coerce") == args.gw]

    # Global metrics
    metrics = FeedbackAnalyzer.compute_global_metrics(feedback)
    print("\n=== GLOBAL METRICS ===")
    for k, v in metrics.to_dict().items():
        print(f"  {k}: {v}")

    # Player-level analysis
    player_analysis = FeedbackAnalyzer.player_level_analysis(feedback)
    for category, df in player_analysis.items():
        print(f"\n=== {category.upper()} ===")
        print(df.to_string(index=False))

    # Bias discovery
    biases = FeedbackAnalyzer.discover_biases(feedback)
    if biases:
        print("\n=== DISCOVERED BIASES ===")
        for bias in biases[:15]:
            print(
                f"  {bias.segment_column}={bias.segment_value}: "
                f"mean_error={bias.mean_signed_error:+.3f}, "
                f"MAE={bias.mae:.3f}, n={bias.n}"
            )

    return 0


def cmd_predict(args: argparse.Namespace, settings) -> int:
    """Generate predictions with feedback correction."""
    snapshot_store, feedback_store, residual_model = _get_stores(settings)

    # Load existing predictions
    pred_path = settings.paths.processed_data_dir / "predictions.csv"
    if not pred_path.exists():
        logger.error("No predictions found at %s — run prediction first.", pred_path)
        return 1

    predictions = pd.read_csv(pred_path, low_memory=False)

    # Determine season and GW
    season = args.season
    target_gw = args.gw

    if season is None:
        raw_path = settings.paths.raw_data_dir / "vaastav_merged.csv"
        if raw_path.exists():
            raw = pd.read_csv(raw_path, usecols=["season"], low_memory=False)
            season = str(raw["season"].max())
        else:
            season = "unknown"

    if target_gw is None and "predicted_for_gw" in predictions.columns:
        target_gw = int(predictions["predicted_for_gw"].max())

    if target_gw is None:
        logger.error("Cannot determine target GW — specify --gw.")
        return 1

    # Load residual model
    residual_model.load()

    adapter = FeedbackAdapter(feedback_store, residual_model, settings.feedback)

    pred_col = "predicted_total_points"
    if pred_col not in predictions.columns:
        # Try other column names
        for candidate in predictions.columns:
            if "predicted" in candidate.lower():
                pred_col = candidate
                break

    corrected = adapter.apply_correction(
        predictions, season, target_gw, prediction_column=pred_col
    )

    output_path = settings.paths.processed_data_dir / "predictions_adaptive.csv"
    corrected.to_csv(output_path, index=False)
    logger.info("Adaptive predictions saved to %s", output_path)

    # Print top 20
    if "final_prediction" in corrected.columns:
        top = corrected.nlargest(20, "final_prediction")
        display_cols = [c for c in ("element", "name", "team", "base_prediction",
                                     "feedback_correction", "final_prediction",
                                     "feedback_confidence") if c in top.columns]
        print("\n=== TOP 20 ADAPTIVE PREDICTIONS ===")
        print(top[display_cols].to_string(index=False))

    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the specified feedback command."""
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    commands = {
        "generate": cmd_generate,
        "train": cmd_train,
        "evaluate": cmd_evaluate,
        "analyze": cmd_analyze,
        "predict": cmd_predict,
    }

    if args.command is None:
        print("Usage: python -m scripts.run_feedback {generate|train|evaluate|analyze|predict}")
        return 1

    handler = commands.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}")
        return 1

    return handler(args, settings)


if __name__ == "__main__":
    sys.exit(main())
