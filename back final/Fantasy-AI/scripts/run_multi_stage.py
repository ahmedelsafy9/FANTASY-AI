"""CLI entry point: multi-stage prediction pipeline (Feedback 4).

Usage:
    python -m scripts.run_multi_stage train      # Full walk-forward training
    python -m scripts.run_multi_stage predict    # Next-GW inference
    python -m scripts.run_multi_stage diagnose   # Ablation + diagnostics
    python -m scripts.run_multi_stage full       # All of the above
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Multi-stage prediction pipeline for Fantasy-AI (Feedback 4)."
    )
    parser.add_argument(
        "command",
        choices=["train", "predict", "diagnose", "full"],
        help="Pipeline command to run.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to the engineered dataset CSV.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the multi-stage prediction pipeline.

    Args:
        argv: Optional argument list, primarily for testing.

    Returns:
        int: Process exit code (0 on success, 1 on failure).
    """
    configure_logging()
    args = parse_args(argv)
    settings = get_settings()

    input_path = (
        Path(args.input)
        if args.input
        else settings.paths.processed_data_dir / "vaastav_features.csv"
    )
    ms_dir = settings.paths.models_dir / settings.multi_stage.multi_stage_output_dir

    if not input_path.exists():
        logger.error(
            "Input dataset not found at %s. Run feature engineering first.",
            input_path,
        )
        return 1

    logger.info("Loading engineered dataset from %s...", input_path)
    data = pd.read_csv(input_path, low_memory=False)
    logger.info("Loaded %d rows, %d columns.", len(data), len(data.columns))

    command = args.command

    if command in ("train", "full"):
        return_code = _run_train(data, settings, ms_dir)
        if return_code != 0 and command == "train":
            return return_code

    if command in ("diagnose", "full"):
        _run_diagnose(data, settings, ms_dir)

    if command in ("predict", "full"):
        return_code = _run_predict(data, settings, ms_dir)
        if return_code != 0 and command == "predict":
            return return_code

    return 0


def _run_train(data, settings, ms_dir: Path) -> int:
    """Run the full multi-stage training pipeline."""
    from src.multi_stage.pipeline import (
        run_multi_stage_pipeline,
        save_pipeline_result,
    )

    logger.info("=" * 60)
    logger.info("MULTI-STAGE TRAINING PIPELINE")
    logger.info("=" * 60)

    try:
        result = run_multi_stage_pipeline(
            data,
            min_train_gameweeks=settings.multi_stage.min_train_gameweeks,
            random_state=settings.training.random_state,
            fold_step=settings.multi_stage.fold_step,
        )
    except Exception as exc:
        logger.error("Multi-stage pipeline failed: %s", exc, exc_info=True)
        return 1

    # Save all models and metadata
    save_pipeline_result(result, ms_dir)

    # Log ablation summary
    if result.ablation_results:
        logger.info("=" * 60)
        logger.info("ABLATION STUDY RESULTS")
        logger.info("=" * 60)
        for config_name, metrics in result.ablation_results.items():
            logger.info(
                "  %s [%s]: MAE=%.4f, RMSE=%.4f, R²=%.4f, Spearman=%.4f",
                config_name,
                metrics.get("model", "?"),
                metrics.get("mae", float("nan")),
                metrics.get("rmse", float("nan")),
                metrics.get("r2", float("nan")),
                metrics.get("spearman", float("nan")),
            )
        logger.info("Best configuration: %s", result.points_model_name)

    # Log match model summary
    if result.match_result.best_model_name:
        logger.info("Match model: %s", result.match_result.best_model_name)
        if result.match_result.calibration_metrics:
            logger.info("  Calibration: %s", result.match_result.calibration_metrics)

    # Log contribution model summary
    for target_name, tr in result.contribution_result.target_results.items():
        logger.info(
            "Contribution '%s': %s (MAE=%.4f)",
            target_name, tr.best_model_name, tr.val_mae,
        )

    logger.info("All models saved to %s.", ms_dir)
    return 0


def _run_diagnose(data, settings, ms_dir: Path) -> int:
    """Generate diagnostic and ablation reports."""
    import json
    from src.multi_stage.diagnostics import (
        generate_ablation_report,
        generate_model_selection_report,
        generate_diagnostic_report,
    )

    logger.info("Generating diagnostic reports...")

    # Load pipeline metadata
    meta_path = ms_dir / "pipeline_metadata.json"
    if not meta_path.exists():
        logger.warning("Pipeline metadata not found at %s. Run 'train' first.", meta_path)
        return 1

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    ablation_results = metadata.get("ablation_results", {})
    generate_ablation_report(
        ablation_results,
        ms_dir / "ablation_report.md",
    )

    # Load match and contribution metadata if present
    match_meta_path = ms_dir / "match_model_metadata.json"
    match_meta = json.loads(match_meta_path.read_text(encoding="utf-8")) if match_meta_path.exists() else None

    contrib_meta_path = ms_dir / "contribution_metadata.json"
    contrib_meta = json.loads(contrib_meta_path.read_text(encoding="utf-8")) if contrib_meta_path.exists() else None

    generate_model_selection_report(
        match_result=match_meta,
        contribution_result=contrib_meta,
        ablation_results=ablation_results,
        output_path=ms_dir / "model_selection_report.md",
    )

    logger.info("Reports saved to %s.", ms_dir)
    return 0


def _run_predict(data, settings, ms_dir: Path) -> int:
    """Generate next-GW predictions using the trained pipeline."""
    import json
    import joblib

    logger.info("Generating next-GW predictions...")

    # Load the points model
    points_model_path = ms_dir / "points_model.joblib"
    meta_path = ms_dir / "pipeline_metadata.json"

    if not points_model_path.exists() or not meta_path.exists():
        logger.error("Models not found. Run 'train' first.")
        return 1

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    points_model = joblib.load(points_model_path)
    feature_cols = metadata.get("points_feature_cols", [])
    train_medians = metadata.get("train_medians", {})

    # Build next-GW rows
    from src.prediction.next_gameweek import build_next_gameweek_rows

    try:
        next_gw_rows = build_next_gameweek_rows(
            data,
            player_id_columns=settings.feature_engineering.player_id_columns,
            chronological_columns=settings.feature_engineering.chronological_columns,
            max_valid_gameweek=settings.prediction.max_valid_gameweek,
        )
    except Exception as exc:
        logger.error("Failed to build next-GW rows: %s", exc)
        return 1

    # Try loading match model for inference
    match_model_path = ms_dir / "match_model.joblib"
    if match_model_path.exists():
        try:
            from src.multi_stage.match_model import (
                build_match_dataset,
                map_match_predictions_to_players,
            )
            match_model = joblib.load(match_model_path)
            match_meta = json.loads(
                (ms_dir / "match_model_metadata.json").read_text(encoding="utf-8")
            )
            match_features = match_meta.get("feature_cols", [])

            match_df = build_match_dataset(data)
            if not match_df.empty and match_features:
                latest_team = match_df.sort_values(["season", "GW"]).groupby("team").tail(1)
                avail = [c for c in match_features if c in latest_team.columns]
                if avail:
                    X_m = latest_team[avail].apply(pd.to_numeric, errors="coerce").fillna(0)
                    latest_team["oof_goals_pred"] = match_model.predict(X_m)
                    next_gw_rows = map_match_predictions_to_players(next_gw_rows, latest_team)
        except Exception as exc:
            logger.warning("Match model inference failed: %s", exc)

    # Try loading contribution models for inference
    from src.multi_stage.contribution_model import CONTRIBUTION_TARGETS
    for target_name, target_config in CONTRIBUTION_TARGETS.items():
        contrib_path = ms_dir / f"contrib_{target_name}_model.joblib"
        if contrib_path.exists():
            try:
                contrib_model = joblib.load(contrib_path)
                contrib_meta = json.loads(
                    (ms_dir / "contribution_metadata.json").read_text(encoding="utf-8")
                )
                target_meta = contrib_meta.get(target_name, {})
                contrib_features = target_meta.get("feature_cols", [])
                avail = [c for c in contrib_features if c in next_gw_rows.columns]
                if avail:
                    X_c = next_gw_rows[avail].apply(pd.to_numeric, errors="coerce").fillna(0)
                    output_name = target_config["output_name"]
                    next_gw_rows[output_name] = contrib_model.predict(X_c)
            except Exception as exc:
                logger.warning("Contribution model '%s' inference failed: %s", target_name, exc)

    # Fill missing multi-stage columns with NaN
    from src.multi_stage.pipeline import MATCH_PREDICTION_COLS, CONTRIBUTION_PREDICTION_COLS
    for col in MATCH_PREDICTION_COLS + CONTRIBUTION_PREDICTION_COLS:
        if col not in next_gw_rows.columns:
            next_gw_rows[col] = float("nan")

    # Run points model
    available = [c for c in feature_cols if c in next_gw_rows.columns]
    if available:
        X_pts = next_gw_rows[available].apply(pd.to_numeric, errors="coerce")
        X_pts = X_pts.fillna(train_medians).fillna(0)
        preds = points_model.predict(X_pts)
        next_gw_rows["predicted_total_points"] = preds
        next_gw_rows["predicted_expected_points"] = preds
    else:
        logger.error("No matching feature columns for points model!")
        return 1

    # Export
    output_path = settings.paths.processed_data_dir / "predictions_multi_stage.csv"
    id_cols = list(settings.prediction.export_id_columns)
    export_cols = [c for c in id_cols if c in next_gw_rows.columns]
    export_cols.extend([
        "predicted_total_points", "predicted_for_gw",
    ])
    # Add multi-stage prediction columns if present
    for col in MATCH_PREDICTION_COLS + CONTRIBUTION_PREDICTION_COLS:
        if col in next_gw_rows.columns:
            export_cols.append(col)

    export_cols = [c for c in export_cols if c in next_gw_rows.columns]
    out = next_gw_rows[export_cols].sort_values("predicted_total_points", ascending=False)
    out.to_csv(output_path, index=False)

    target_gw = "?"
    if "predicted_for_gw" in next_gw_rows.columns:
        gw_vals = next_gw_rows["predicted_for_gw"].dropna()
        if not gw_vals.empty:
            target_gw = int(gw_vals.mode().iloc[0])

    logger.info(
        "Predictions for GW %s: %d players. Saved to %s.",
        target_gw, len(out), output_path,
    )
    logger.info("Top 10 predicted players:")
    top10 = out.head(10)
    for _, row in top10.iterrows():
        name = row.get("name", "?")
        pts = row.get("predicted_total_points", 0)
        logger.info("  %s: %.2f pts", name, pts)

    return 0


if __name__ == "__main__":
    sys.exit(main())
