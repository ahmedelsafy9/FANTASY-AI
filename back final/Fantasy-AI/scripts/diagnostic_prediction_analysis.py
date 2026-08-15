"""
Deep Learning prediction diagnostic.

Analyzes why Deep Learning predictions differ from XGBoost/LightGBM.

It:
1. Loads the real engineered dataset.
2. Reproduces the exact production training pipeline.
3. Trains XGBoost, LightGBM and Deep Learning.
4. Compares prediction distributions.
5. Measures bias by actual-points buckets.
6. Measures errors for high-point players.
7. Checks whether DL is systematically under-predicting.
8. Finds the largest DL errors.
9. Compares model ranking agreement.
10. Writes a detailed CSV + JSON diagnostic report.

Run:

python scripts/diagnostic_prediction_analysis.py \
    --engineered-csv "data\processed\vaastav_features.csv"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make repo importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.settings import Settings
from src.training.dataset import prepare_split_dataset
from src.training.factory import build_default_model_specs
from src.training.ranking_metrics import high_score_recall, top_n_recall
from src.training.trainer import ModelTrainer


MODELS = ("xgboost", "lightgbm", "deep_learning_weighted_huber")


def safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2:
        return float("nan")

    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")

    return float(np.corrcoef(a, b)[0, 1])


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    return safe_corr(ra, rb)


def summarize_predictions(name: str, pred: np.ndarray, y: np.ndarray) -> dict:
    error = pred - y
    abs_error = np.abs(error)
    ss_res = np.sum(error ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2_score = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")

    return {
        "model": name,
        "prediction_mean": float(np.mean(pred)),
        "prediction_std": float(np.std(pred)),
        "prediction_min": float(np.min(pred)),
        "prediction_max": float(np.max(pred)),
        "actual_mean": float(np.mean(y)),
        "actual_std": float(np.std(y)),
        "bias_mean_pred_minus_actual": float(np.mean(error)),
        "mae": float(np.mean(abs_error)),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "r2": r2_score,
        "spearman": float(spearman(pred, y)),
        "under_prediction_rate": float(np.mean(error < 0)),
        "over_prediction_rate": float(np.mean(error > 0)),
        "high_score_recall": float(high_score_recall(y, pred, threshold=6.0, pred_threshold=6.0)),
        "top_10_recall": float(top_n_recall(y, pred, n=10)),
        "top_20_recall": float(top_n_recall(y, pred, n=20)),
        "top_30_recall": float(top_n_recall(y, pred, n=30)),
    }


def bucket_analysis(
    model_name: str,
    pred: np.ndarray,
    y: np.ndarray,
) -> pd.DataFrame:

    df = pd.DataFrame(
        {
            "actual": y,
            "prediction": pred,
        }
    )

    # Actual-point buckets
    bins = [-np.inf, 0, 2, 5, 8, 12, 20, 50, np.inf]
    labels = [
        "<=0",
        "1-2",
        "3-5",
        "6-8",
        "9-12",
        "13-20",
        "21-50",
        "50+",
    ]

    df["actual_bucket"] = pd.cut(
        df["actual"],
        bins=bins,
        labels=labels,
    )

    grouped = []

    for bucket, g in df.groupby("actual_bucket", observed=False):

        if len(g) == 0:
            continue

        error = g["prediction"] - g["actual"]

        grouped.append(
            {
                "model": model_name,
                "bucket": str(bucket),
                "rows": int(len(g)),
                "actual_mean": float(g["actual"].mean()),
                "prediction_mean": float(g["prediction"].mean()),
                "bias": float(error.mean()),
                "mae": float(error.abs().mean()),
                "rmse": float(np.sqrt(np.mean(error ** 2))),
                "under_prediction_rate": float((error < 0).mean()),
            }
        )

    return pd.DataFrame(grouped)


def main() -> None:

    parser = argparse.ArgumentParser(
        description="Deep Learning prediction diagnostic"
    )

    parser.add_argument(
        "--engineered-csv",
        type=Path,
        required=True,
        help="Real engineered dataset used by production training.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/dl_prediction_diagnostic"),
        help="Directory for diagnostic outputs.",
    )

    args = parser.parse_args()

    if not args.engineered_csv.exists():
        print(
            f"ERROR: dataset not found: {args.engineered_csv}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("DEEP LEARNING PREDICTION DIAGNOSTIC")
    print("=" * 80)

    settings = Settings()

    print(f"\nDataset: {args.engineered_csv}")

    data = pd.read_csv(
        args.engineered_csv,
        low_memory=False,
    )

    print(f"Loaded rows: {len(data):,}")

    # ---------------------------------------------------------
    # EXACT SAME SPLIT AS PRODUCTION
    # ---------------------------------------------------------

    split = prepare_split_dataset(
        data,
        settings.training,
    )

    print(
        f"Train rows: {len(split.X_train):,}"
    )

    print(
        f"Test rows:  {len(split.X_test):,}"
    )

    # ---------------------------------------------------------
    # EXACT SAME MODEL FACTORY
    # ---------------------------------------------------------

    specs, skipped = build_default_model_specs(
        settings.training
    )

    available = {
        spec.name
        for spec in specs
    }

    missing = [
        model
        for model in MODELS
        if model not in available
    ]

    if missing:
        print(
            f"\nWARNING: missing models: {missing}"
        )

    trainer = ModelTrainer(
        model_specs=specs,
        settings=settings.training,
    )

    print("\nTraining models...\n")

    result = trainer.run(
        split,
        dict(skipped),
    )

    trained = {
        r.name: r
        for r in result.results
    }

    available_models = [
        model
        for model in MODELS
        if model in trained
    ]

    if len(available_models) < 2:
        print(
            "ERROR: fewer than two models trained successfully."
        )
        raise SystemExit(1)

    # ---------------------------------------------------------
    # SAME TEST ROWS
    # ---------------------------------------------------------

    X_test = split.X_test
    y_test = split.y_test.to_numpy()

    predictions = {}

    for model_name in available_models:

        print(
            f"Generating {model_name} predictions..."
        )

        predictions[model_name] = (
            trained[model_name]
            .model
            .predict(X_test)
        )

    # ---------------------------------------------------------
    # BASIC MODEL SUMMARY
    # ---------------------------------------------------------

    summaries = []

    for model_name in available_models:

        summaries.append(
            summarize_predictions(
                model_name,
                predictions[model_name],
                y_test,
            )
        )

    summary_df = pd.DataFrame(
        summaries
    )

    print("\n")
    print("=" * 80)
    print("PREDICTION SUMMARY")
    print("=" * 80)

    print(
        summary_df.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------
    # BUCKET ANALYSIS
    # ---------------------------------------------------------

    bucket_frames = []

    for model_name in available_models:

        bucket_frames.append(
            bucket_analysis(
                model_name,
                predictions[model_name],
                y_test,
            )
        )

    bucket_df = pd.concat(
        bucket_frames,
        ignore_index=True,
    )

    print("\n")
    print("=" * 80)
    print("ERROR BY ACTUAL POINTS")
    print("=" * 80)

    print(
        bucket_df.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------
    # DEEP LEARNING SPECIFIC ANALYSIS
    # ---------------------------------------------------------

    if "deep_learning" in predictions:

        dl = predictions["deep_learning"]

        dl_error = dl - y_test

        print("\n")
        print("=" * 80)
        print("DEEP LEARNING DIAGNOSTIC")
        print("=" * 80)

        print(
            f"Mean prediction:        {np.mean(dl):.4f}"
        )

        print(
            f"Mean actual:            {np.mean(y_test):.4f}"
        )

        print(
            f"Mean bias:              {np.mean(dl_error):.4f}"
        )

        print(
            f"Under-prediction rate:  {np.mean(dl_error < 0):.2%}"
        )

        print(
            f"Over-prediction rate:   {np.mean(dl_error > 0):.2%}"
        )

        print(
            f"DL max prediction:      {np.max(dl):.4f}"
        )

        print(
            f"Actual max:             {np.max(y_test):.4f}"
        )

        # High-point players
        high_mask = y_test >= 10

        if np.any(high_mask):

            high_actual = y_test[high_mask]
            high_pred = dl[high_mask]

            high_error = high_pred - high_actual

            print("\nHigh-point players (actual >= 10):")

            print(
                f"Rows:                   {len(high_actual):,}"
            )

            print(
                f"Actual mean:            {np.mean(high_actual):.4f}"
            )

            print(
                f"DL mean:                {np.mean(high_pred):.4f}"
            )

            print(
                f"Bias:                   {np.mean(high_error):.4f}"
            )

            print(
                f"MAE:                    {np.mean(np.abs(high_error)):.4f}"
            )

            print(
                f"Under-prediction rate:  {np.mean(high_error < 0):.2%}"
            )

        # -----------------------------------------------------
        # EXTREME UNDER-PREDICTIONS
        # -----------------------------------------------------

        under_idx = np.argsort(
            dl_error
        )[:50]

        under_df = pd.DataFrame(
            {
                "test_index": X_test.index.to_numpy()[
                    under_idx
                ],
                "actual": y_test[under_idx],
                "deep_learning": dl[under_idx],
                "error": dl_error[under_idx],
                "abs_error": np.abs(
                    dl_error[under_idx]
                ),
            }
        )

        # -----------------------------------------------------
        # EXTREME OVER-PREDICTIONS
        # -----------------------------------------------------

        over_idx = np.argsort(
            dl_error
        )[-50:][::-1]

        over_df = pd.DataFrame(
            {
                "test_index": X_test.index.to_numpy()[
                    over_idx
                ],
                "actual": y_test[over_idx],
                "deep_learning": dl[over_idx],
                "error": dl_error[over_idx],
                "abs_error": np.abs(
                    dl_error[over_idx]
                ),
            }
        )

        # -----------------------------------------------------
        # ADD XGB/LGBM PREDICTIONS
        # -----------------------------------------------------

        for model_name in (
            "xgboost",
            "lightgbm",
        ):

            if model_name in predictions:

                under_df[
                    model_name
                ] = predictions[
                    model_name
                ][under_idx]

                over_df[
                    model_name
                ] = predictions[
                    model_name
                ][over_idx]

        under_df.to_csv(
            args.output_dir
            / "deep_learning_biggest_under_predictions.csv",
            index=False,
        )

        over_df.to_csv(
            args.output_dir
            / "deep_learning_biggest_over_predictions.csv",
            index=False,
        )

        print("\n")
        print("=" * 80)
        print("BIGGEST DL UNDER-PREDICTIONS")
        print("=" * 80)

        print(
            under_df.head(20).to_string(
                index=False
            )
        )

    # ---------------------------------------------------------
    # MODEL AGREEMENT
    # ---------------------------------------------------------

    agreement = []

    pairs = [
        ("xgboost", "lightgbm"),
        ("xgboost", "deep_learning"),
        ("lightgbm", "deep_learning"),
    ]

    for a, b in pairs:

        if a not in predictions:
            continue

        if b not in predictions:
            continue

        pa = predictions[a]
        pb = predictions[b]

        agreement.append(
            {
                "model_a": a,
                "model_b": b,
                "pearson": safe_corr(pa, pb),
                "spearman": spearman(pa, pb),
                "mean_difference": float(
                    np.mean(pa - pb)
                ),
                "mean_absolute_difference": float(
                    np.mean(np.abs(pa - pb))
                ),
                "max_absolute_difference": float(
                    np.max(np.abs(pa - pb))
                ),
            }
        )

    agreement_df = pd.DataFrame(
        agreement
    )

    print("\n")
    print("=" * 80)
    print("MODEL AGREEMENT")
    print("=" * 80)

    print(
        agreement_df.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------
    # RANKING QUALITY
    # ---------------------------------------------------------

    ranking = []

    actual_rank = pd.Series(
        y_test
    ).rank(
        ascending=False
    ).to_numpy()

    for model_name in available_models:

        pred_rank = pd.Series(
            predictions[model_name]
        ).rank(
            ascending=False
        ).to_numpy()

        ranking.append(
            {
                "model": model_name,
                "spearman_prediction_vs_actual": spearman(
                    predictions[model_name],
                    y_test,
                ),
                "rank_spearman": safe_corr(
                    pred_rank,
                    actual_rank,
                ),
            }
        )

    ranking_df = pd.DataFrame(
        ranking
    )

    print("\n")
    print("=" * 80)
    print("RANKING QUALITY")
    print("=" * 80)

    print(
        ranking_df.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------
    # SAVE RESULTS
    # ---------------------------------------------------------

    summary_df.to_csv(
        args.output_dir
        / "prediction_summary.csv",
        index=False,
    )

    bucket_df.to_csv(
        args.output_dir
        / "error_by_actual_bucket.csv",
        index=False,
    )

    agreement_df.to_csv(
        args.output_dir
        / "model_agreement.csv",
        index=False,
    )

    ranking_df.to_csv(
        args.output_dir
        / "ranking_quality.csv",
        index=False,
    )

    diagnostic_json = {
        "dataset": str(
            args.engineered_csv
        ),
        "train_rows": int(
            len(split.X_train)
        ),
        "test_rows": int(
            len(split.X_test)
        ),
        "models": available_models,
        "prediction_summary": summaries,
        "model_agreement": agreement,
        "ranking_quality": ranking,
    }

    with open(
        args.output_dir
        / "diagnostic_report.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            diagnostic_json,
            f,
            indent=2,
        )

    print("\n")
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

    print(
        f"\nResults saved to:"
        f"\n{args.output_dir}"
    )


if __name__ == "__main__":
    main()