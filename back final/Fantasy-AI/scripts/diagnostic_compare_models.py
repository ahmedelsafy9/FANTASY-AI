"""Diagnostic comparison of candidate model predictions.

This script retrains the candidate models using the exact production
training pipeline, keeps every trained model in memory, predicts on the
EXACT SAME chronological test rows, and produces a detailed comparison.

Models compared:
    - XGBoost
    - LightGBM
    - Deep Learning

Outputs:
    1. Per-row prediction comparison CSV.
    2. Statistical summary JSON.
    3. Console diagnostics.

The goal is to determine whether prediction differences between models
are meaningful, especially for FPL Top-N player selection.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd


# Make repository importable when executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.settings import Settings  # noqa: E402
from src.training.dataset import prepare_split_dataset  # noqa: E402
from src.training.factory import build_default_model_specs  # noqa: E402
from src.training.trainer import ModelTrainer  # noqa: E402


REQUIRED_MODELS = (
    "xgboost",
    "lightgbm",
    "deep_learning",
)

TOP_N_VALUES = (10, 20, 30)


def _safe_pearson(a: np.ndarray, b: np.ndarray) -> float:
    """Return Pearson correlation or NaN if correlation is undefined."""
    if len(a) < 2:
        return float("nan")

    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")

    return float(np.corrcoef(a, b)[0, 1])


def _spearman_rank_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Spearman rank correlation without scipy."""
    if len(a) < 2:
        return float("nan")

    ra = pd.Series(a).rank(method="average").to_numpy()
    rb = pd.Series(b).rank(method="average").to_numpy()

    return _safe_pearson(ra, rb)


def _topn_overlap(
    predictions_a: np.ndarray,
    predictions_b: np.ndarray,
    n: int,
) -> float:
    """Fraction of shared rows in the top-N predictions."""
    if len(predictions_a) < n or len(predictions_b) < n:
        return float("nan")

    top_a = set(np.argsort(predictions_a)[-n:])
    top_b = set(np.argsort(predictions_b)[-n:])

    return len(top_a & top_b) / n


def _prediction_summary(
    predictions: np.ndarray,
    actual: np.ndarray,
) -> dict[str, float]:
    """Return prediction distribution and error diagnostics."""
    errors = predictions - actual
    absolute_errors = np.abs(errors)

    return {
        "prediction_mean": float(np.mean(predictions)),
        "prediction_std": float(np.std(predictions)),
        "prediction_min": float(np.min(predictions)),
        "prediction_max": float(np.max(predictions)),
        "actual_mean": float(np.mean(actual)),
        "actual_std": float(np.std(actual)),
        "mean_error": float(np.mean(errors)),
        "mean_absolute_error": float(np.mean(absolute_errors)),
        "max_absolute_error": float(np.max(absolute_errors)),
    }


def _pairwise_comparison(
    name_a: str,
    pred_a: np.ndarray,
    name_b: str,
    pred_b: np.ndarray,
) -> dict[str, float | str]:
    """Compare predictions and rankings for two models."""
    difference = pred_a - pred_b

    return {
        "model_a": name_a,
        "model_b": name_b,
        "pearson": _safe_pearson(pred_a, pred_b),
        "spearman": _spearman_rank_corr(pred_a, pred_b),
        "mean_difference": float(np.mean(difference)),
        "mean_absolute_difference": float(np.mean(np.abs(difference))),
        "max_absolute_difference": float(np.max(np.abs(difference))),
        "top_10_overlap": _topn_overlap(pred_a, pred_b, 10),
        "top_20_overlap": _topn_overlap(pred_a, pred_b, 20),
        "top_30_overlap": _topn_overlap(pred_a, pred_b, 30),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare XGBoost, LightGBM, and Deep Learning predictions "
            "on the exact same chronological test rows."
        )
    )

    parser.add_argument(
        "--engineered-csv",
        type=Path,
        default=None,
        help=(
            "Path to the real engineered dataset CSV. "
            "If omitted, the project's default path is used."
        ),
    )

    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(
            "models/diagnostic_model_comparison.csv"
        ),
        help="Detailed per-row comparison output.",
    )

    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path(
            "models/diagnostic_model_summary.json"
        ),
        help="Statistical comparison summary.",
    )

    parser.add_argument(
        "--id-columns",
        type=str,
        default=(
            "name,team,opponent_team,kickoff_time,GW,season"
        ),
        help=(
            "Comma-separated context columns to carry into output "
            "when available."
        ),
    )

    args = parser.parse_args()

    # ---------------------------------------------------------------
    # 1. Load real production dataset
    # ---------------------------------------------------------------
    settings = Settings()

    engineered_path = args.engineered_csv or (
        settings.paths.data_dir
        / "processed"
        / "engineered_dataset.csv"
    )

    if not engineered_path.exists():
        print(
            f"ERROR: engineered dataset not found at "
            f"{engineered_path}\n\n"
            "This diagnostic refuses to use synthetic data.\n"
            "Run feature engineering first or provide "
            "--engineered-csv explicitly.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"Using engineered dataset: {engineered_path}")

    data = pd.read_csv(
        engineered_path,
        low_memory=False,
    )

    print(f"Loaded {len(data):,} dataset rows.")

    # ---------------------------------------------------------------
    # 2. Prepare EXACT production split
    # ---------------------------------------------------------------
    split = prepare_split_dataset(
        data,
        settings.training,
    )

    print(
        "Prepared chronological split: "
        f"train={len(split.X_train):,}, "
        f"test={len(split.X_test):,}"
    )

    # ---------------------------------------------------------------
    # 3. Build EXACT production model specs
    # ---------------------------------------------------------------
    specs, skipped = build_default_model_specs(
        settings.training
    )

    present = {spec.name for spec in specs}

    missing_required = [
        model
        for model in REQUIRED_MODELS
        if model not in present
    ]

    if missing_required:
        print(
            "WARNING: required models unavailable:",
            missing_required,
            file=sys.stderr,
        )

        for model in missing_required:
            reason = skipped.get(model, "unknown reason")
            print(
                f"  {model}: {reason}",
                file=sys.stderr,
            )

    trainer = ModelTrainer(
        model_specs=specs,
        settings=settings.training,
    )

    # ---------------------------------------------------------------
    # 4. Train ALL candidate models and retain them
    # ---------------------------------------------------------------
    print("\nTraining candidate models...")

    result = trainer.run(
        split,
        dict(skipped),
    )

    trained = {
        model_result.name: model_result
        for model_result in result.results
    }

    have = [
        model
        for model in REQUIRED_MODELS
        if model in trained
    ]

    if len(have) < 2:
        print(
            "ERROR: fewer than two candidate models trained "
            "successfully. Comparison is impossible.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(
        "\nSuccessfully trained:",
        ", ".join(have),
    )

    # ---------------------------------------------------------------
    # 5. Predict on EXACT SAME X_test
    # ---------------------------------------------------------------
    X_test = split.X_test

    predictions: dict[str, np.ndarray] = {}

    for name in have:
        print(f"Generating predictions: {name}")

        prediction = trained[name].model.predict(X_test)

        prediction = np.asarray(
            prediction,
            dtype=float,
        ).reshape(-1)

        if len(prediction) != len(X_test):
            raise RuntimeError(
                f"Model '{name}' returned {len(prediction)} predictions "
                f"for {len(X_test)} test rows."
            )

        predictions[name] = prediction

    # ---------------------------------------------------------------
    # 6. Recover test-row context
    # ---------------------------------------------------------------
    out = pd.DataFrame(
        index=np.arange(len(X_test))
    )

    working = data.dropna(
        subset=[settings.training.target_column]
    ).copy()

    sort_cols = [
        column
        for column in settings.training.chronological_columns
        if column in working.columns
    ]

    if sort_cols:
        working = (
            working
            .sort_values(
                by=sort_cols,
                kind="mergesort",
            )
            .reset_index(drop=True)
        )

    split_index = len(split.X_train)

    test_context = (
        working
        .iloc[
            split_index:
            split_index + len(X_test)
        ]
        .reset_index(drop=True)
    )

    id_columns = [
        column.strip()
        for column in args.id_columns.split(",")
        if column.strip()
    ]

    for column in id_columns:
        if column in test_context.columns:
            out[column] = test_context[column].to_numpy()

    # Actual target
    actual = np.asarray(
        split.y_test,
        dtype=float,
    ).reshape(-1)

    out["actual_points"] = actual

    # ---------------------------------------------------------------
    # 7. Add predictions
    # ---------------------------------------------------------------
    for name, prediction in predictions.items():
        out[f"{name}_prediction"] = prediction

    prediction_columns = [
        f"{name}_prediction"
        for name in have
    ]

    # Simple ensemble diagnostics
    out["mean_prediction"] = (
        out[prediction_columns]
        .mean(axis=1)
    )

    # ---------------------------------------------------------------
    # 8. Per-model errors
    # ---------------------------------------------------------------
    for name in have:
        prediction_column = f"{name}_prediction"

        out[f"{name}_error"] = (
            out[prediction_column]
            - out["actual_points"]
        )

        out[f"{name}_absolute_error"] = (
            out[prediction_column]
            .sub(out["actual_points"])
            .abs()
        )

    # ---------------------------------------------------------------
    # 9. Ranking
    # ---------------------------------------------------------------
    for name in have:
        prediction_column = f"{name}_prediction"

        out[f"prediction_rank_{name}"] = (
            out[prediction_column]
            .rank(
                ascending=False,
                method="min",
            )
            .astype(int)
        )

    # ---------------------------------------------------------------
    # 10. Pairwise differences
    # ---------------------------------------------------------------
    pairwise_results: list[dict[str, float | str]] = []

    for name_a, name_b in combinations(have, 2):
        pred_a = predictions[name_a]
        pred_b = predictions[name_b]

        difference_column = (
            f"{name_a}_minus_{name_b}"
        )

        out[difference_column] = (
            pred_a - pred_b
        )

        pairwise_results.append(
            _pairwise_comparison(
                name_a,
                pred_a,
                name_b,
                pred_b,
            )
        )

    # ---------------------------------------------------------------
    # 11. Rank agreement against actual points
    # ---------------------------------------------------------------
    ranking_results: dict[str, dict[str, float]] = {}

    for name in have:
        prediction = predictions[name]

        ranking_results[name] = {
            "spearman_prediction_vs_actual": (
                _spearman_rank_corr(
                    prediction,
                    actual,
                )
            ),
        }

    # ---------------------------------------------------------------
    # 12. Model metrics
    # ---------------------------------------------------------------
    model_metrics: dict[str, dict[str, float]] = {}

    for name in have:
        metrics = trained[name].metrics

        model_metrics[name] = {
            "mae": float(metrics.mae),
            "rmse": float(metrics.rmse),
            "r2": float(metrics.r2),
        }

    # ---------------------------------------------------------------
    # 13. Prediction distributions
    # ---------------------------------------------------------------
    prediction_distributions = {
        name: _prediction_summary(
            predictions[name],
            actual,
        )
        for name in have
    }

    # ---------------------------------------------------------------
    # 14. Top-N player comparison
    # ---------------------------------------------------------------
    top_n_results: dict[str, dict[str, list[int]]] = {}

    for name in have:
        prediction = predictions[name]

        top_n_results[name] = {}

        for n in TOP_N_VALUES:
            if len(prediction) < n:
                continue

            top_indices = (
                np.argsort(prediction)[-n:][::-1]
            )

            top_n_results[name][str(n)] = (
                top_indices.tolist()
            )

    # ---------------------------------------------------------------
    # 15. Save detailed CSV
    # ---------------------------------------------------------------
    args.output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        args.output_csv,
        index=False,
    )

    print(
        f"\nWrote detailed comparison: "
        f"{args.output_csv}"
    )

    # ---------------------------------------------------------------
    # 16. Save statistical JSON
    # ---------------------------------------------------------------
    summary = {
        "dataset": str(engineered_path),
        "test_rows": len(X_test),
        "feature_count": X_test.shape[1],
        "models": have,
        "metrics": model_metrics,
        "prediction_distributions": (
            prediction_distributions
        ),
        "ranking": ranking_results,
        "pairwise_comparisons": pairwise_results,
        "top_n_indices": top_n_results,
    }

    args.summary_json.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.summary_json.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            summary,
            handle,
            indent=2,
        )

    print(
        f"Wrote statistical summary: "
        f"{args.summary_json}"
    )

    # ===============================================================
    # CONSOLE REPORT
    # ===============================================================

    print("\n" + "=" * 72)
    print("HELD-OUT TEST SET METRICS")
    print("=" * 72)

    metric_table = []

    for name in have:
        metrics = model_metrics[name]

        metric_table.append(
            {
                "model": name,
                "MAE": metrics["mae"],
                "RMSE": metrics["rmse"],
                "R2": metrics["r2"],
            }
        )

    metric_df = pd.DataFrame(
        metric_table
    ).sort_values(
        by="MAE"
    )

    print(
        metric_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ---------------------------------------------------------------
    # Prediction distribution
    # ---------------------------------------------------------------
    print("\n" + "=" * 72)
    print("PREDICTION DISTRIBUTIONS")
    print("=" * 72)

    for name in have:
        stats = prediction_distributions[name]

        print(
            f"\n{name}:"
            f"\n  mean = {stats['prediction_mean']:.4f}"
            f"\n  std  = {stats['prediction_std']:.4f}"
            f"\n  min  = {stats['prediction_min']:.4f}"
            f"\n  max  = {stats['prediction_max']:.4f}"
            f"\n  MAE  = {stats['mean_absolute_error']:.4f}"
            f"\n  bias = {stats['mean_error']:.4f}"
        )

    # ---------------------------------------------------------------
    # Pairwise model agreement
    # ---------------------------------------------------------------
    print("\n" + "=" * 72)
    print("PAIRWISE MODEL AGREEMENT")
    print("=" * 72)

    for comparison in pairwise_results:
        a = comparison["model_a"]
        b = comparison["model_b"]

        print(
            f"\n{a} vs {b}:"
            f"\n  Pearson:             "
            f"{comparison['pearson']:.4f}"
            f"\n  Spearman:            "
            f"{comparison['spearman']:.4f}"
            f"\n  Mean difference:     "
            f"{comparison['mean_difference']:.4f}"
            f"\n  Mean |difference|:   "
            f"{comparison['mean_absolute_difference']:.4f}"
            f"\n  Max |difference|:    "
            f"{comparison['max_absolute_difference']:.4f}"
            f"\n  Top-10 overlap:      "
            f"{comparison['top_10_overlap']:.2%}"
            f"\n  Top-20 overlap:      "
            f"{comparison['top_20_overlap']:.2%}"
            f"\n  Top-30 overlap:      "
            f"{comparison['top_30_overlap']:.2%}"
        )

    # ---------------------------------------------------------------
    # Ranking correlation against actual target
    # ---------------------------------------------------------------
    print("\n" + "=" * 72)
    print("PREDICTION RANKING VS ACTUAL POINTS")
    print("=" * 72)

    for name in have:
        correlation = (
            ranking_results[name]
            ["spearman_prediction_vs_actual"]
        )

        print(
            f"{name:15s}: "
            f"Spearman={correlation:.4f}"
        )

    # ---------------------------------------------------------------
    # Biggest DL disagreements
    # ---------------------------------------------------------------
    if "deep_learning" in predictions:
        print("\n" + "=" * 72)
        print("BIGGEST DEEP LEARNING DISAGREEMENTS")
        print("=" * 72)

        for other in have:
            if other == "deep_learning":
                continue

            difference = np.abs(
                predictions["deep_learning"]
                - predictions[other]
            )

            largest_indices = np.argsort(
                difference
            )[-10:][::-1]

            print(
                f"\nDeep Learning vs {other}:"
            )

            for idx in largest_indices:
                row = out.iloc[idx]

                context = []

                for column in (
                    "name",
                    "team",
                    "opponent_team",
                    "GW",
                    "season",
                ):
                    if column in out.columns:
                        context.append(
                            f"{column}={row[column]}"
                        )

                print(
                    "  "
                    + ", ".join(context)
                    + " | "
                    + f"DL={predictions['deep_learning'][idx]:.3f} "
                    + f"{other}={predictions[other][idx]:.3f} "
                    + f"actual={actual[idx]:.3f}"
                )

    print("\n" + "=" * 72)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()