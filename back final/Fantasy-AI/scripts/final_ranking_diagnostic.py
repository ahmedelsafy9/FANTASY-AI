from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

DEFAULT_PREDICTIONS = Path("models/diagnostic_model_comparison.csv")
DEFAULT_OUTPUT_CSV = Path("models/final_ranking_diagnostic.csv")
DEFAULT_OUTPUT_JSON = Path("models/final_ranking_diagnostic_summary.json")

MODELS = ["xgboost", "lightgbm", "deep_learning"]

TOP_NS = [10, 20, 30]
HIGH_SCORE_THRESHOLDS = [6.0, 10.0]
LOW_SCORE_THRESHOLD = 2.0


# ============================================================
# HELPERS
# ============================================================

def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first matching column name."""
    normalized = {str(c).strip().lower(): c for c in df.columns}

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]

    return None


def spearman_corr(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Spearman correlation without scipy."""
    if len(y_true) == 0:
        return float("nan")

    true_rank = pd.Series(y_true).rank(method="average").to_numpy()
    pred_rank = pd.Series(y_pred).rank(method="average").to_numpy()

    if np.std(true_rank) == 0 or np.std(pred_rank) == 0:
        return float("nan")

    return float(np.corrcoef(true_rank, pred_rank)[0, 1])


def top_n_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n: int,
) -> dict[str, float]:
    """
    Compare model Top-N against actual Top-N.

    Precision:
        How many predicted Top-N are actually in the real Top-N.

    Recall:
        How many actual Top-N players were successfully captured.

    Both are identical numerically here because both sets have size N,
    but we keep both names because they are useful operationally.
    """
    if len(y_true) < n:
        return {
            "precision": float("nan"),
            "recall": float("nan"),
            "overlap": float("nan"),
        }

    true_top = set(np.argsort(y_true)[-n:])
    pred_top = set(np.argsort(y_pred)[-n:])

    overlap = len(true_top & pred_top)
    score = overlap / n

    return {
        "precision": float(score),
        "recall": float(score),
        "overlap": float(overlap),
    }


def high_score_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    """
    Evaluate detection of high-scoring players.

    Actual high-score:
        y_true >= threshold

    Predicted high-score:
        y_pred >= threshold
    """
    actual_mask = y_true >= threshold
    predicted_mask = y_pred >= threshold

    actual_count = int(actual_mask.sum())
    predicted_count = int(predicted_mask.sum())

    if actual_count == 0:
        return {
            "actual_count": 0,
            "predicted_count": predicted_count,
            "recall": float("nan"),
            "precision": float("nan"),
            "bias": float("nan"),
            "mae": float("nan"),
        }

    true_positive = int((actual_mask & predicted_mask).sum())

    recall = true_positive / actual_count

    if predicted_count > 0:
        precision = true_positive / predicted_count
    else:
        precision = 0.0

    errors = y_pred[actual_mask] - y_true[actual_mask]

    return {
        "actual_count": actual_count,
        "predicted_count": predicted_count,
        "recall": float(recall),
        "precision": float(precision),
        "bias": float(np.mean(errors)),
        "mae": float(np.mean(np.abs(errors))),
    }


def bucket_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    lower: float | None,
    upper: float | None,
) -> dict[str, float]:
    """Calculate metrics for an actual-score bucket."""
    mask = np.ones(len(y_true), dtype=bool)

    if lower is not None:
        mask &= y_true >= lower

    if upper is not None:
        mask &= y_true < upper

    count = int(mask.sum())

    if count == 0:
        return {
            "rows": 0,
            "actual_mean": float("nan"),
            "prediction_mean": float("nan"),
            "bias": float("nan"),
            "mae": float("nan"),
            "rmse": float("nan"),
            "under_prediction_rate": float("nan"),
        }

    errors = y_pred[mask] - y_true[mask]

    return {
        "rows": count,
        "actual_mean": float(np.mean(y_true[mask])),
        "prediction_mean": float(np.mean(y_pred[mask])),
        "bias": float(np.mean(errors)),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "under_prediction_rate": float(np.mean(errors < 0)),
    }


# ============================================================
# DATA LOADING
# ============================================================

def load_predictions(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        raise FileNotFoundError(
            f"\nPrediction file not found:\n{path}\n\n"
            "Run diagnostic_compare_models.py once first."
        )

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError("Prediction CSV is empty.")

    actual_col = find_column(
        df,
        [
            "actual",
            "actual_points",
            "target",
            "y_true",
            "total_points",
        ],
    )

    if actual_col is None:
        raise ValueError(
            "Could not find actual target column.\n"
            f"Available columns:\n{list(df.columns)}"
        )

    return df, actual_col


# ============================================================
# MODEL COLUMN DISCOVERY
# ============================================================

def get_prediction_column(
    df: pd.DataFrame,
    model: str,
) -> str | None:
    candidates = [
        model,
        f"{model}_prediction",
        f"{model}_pred",
        f"prediction_{model}",
        f"{model}_predictions",
    ]

    return find_column(df, candidates)


# ============================================================
# MODEL ANALYSIS
# ============================================================

def analyze_model(
    df: pd.DataFrame,
    actual_col: str,
    model: str,
) -> tuple[dict, list[dict]]:
    prediction_col = get_prediction_column(df, model)

    if prediction_col is None:
        raise ValueError(
            f"Could not find prediction column for '{model}'.\n"
            f"Available columns:\n{list(df.columns)}"
        )

    work = df[[actual_col, prediction_col]].copy()

    work[actual_col] = pd.to_numeric(
        work[actual_col],
        errors="coerce",
    )

    work[prediction_col] = pd.to_numeric(
        work[prediction_col],
        errors="coerce",
    )

    work = work.dropna()

    y_true = work[actual_col].to_numpy(dtype=float)
    y_pred = work[prediction_col].to_numpy(dtype=float)

    errors = y_pred - y_true

    result = {
        "model": model,
        "rows": int(len(work)),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "bias": float(np.mean(errors)),
        "spearman": spearman_corr(y_true, y_pred),
        "prediction_mean": float(np.mean(y_pred)),
        "actual_mean": float(np.mean(y_true)),
        "prediction_std": float(np.std(y_pred)),
        "actual_std": float(np.std(y_true)),
        "prediction_min": float(np.min(y_pred)),
        "prediction_max": float(np.max(y_pred)),
        "actual_min": float(np.min(y_true)),
        "actual_max": float(np.max(y_true)),
        "overall_under_prediction_rate": float(
            np.mean(errors < 0)
        ),
        "overall_over_prediction_rate": float(
            np.mean(errors > 0)
        ),
    }

    # --------------------------------------------------------
    # TOP-N
    # --------------------------------------------------------

    for n in TOP_NS:
        metrics = top_n_metrics(y_true, y_pred, n)

        result[f"top_{n}_overlap"] = metrics["overlap"]
        result[f"top_{n}_precision"] = metrics["precision"]
        result[f"top_{n}_recall"] = metrics["recall"]

    # --------------------------------------------------------
    # HIGH-SCORE
    # --------------------------------------------------------

    for threshold in HIGH_SCORE_THRESHOLDS:
        metrics = high_score_metrics(
            y_true,
            y_pred,
            threshold,
        )

        key = str(int(threshold))

        result[f"actual_ge_{key}_count"] = metrics["actual_count"]
        result[f"predicted_ge_{key}_count"] = metrics["predicted_count"]
        result[f"high_score_{key}_recall"] = metrics["recall"]
        result[f"high_score_{key}_precision"] = metrics["precision"]
        result[f"high_score_{key}_bias"] = metrics["bias"]
        result[f"high_score_{key}_mae"] = metrics["mae"]

    # --------------------------------------------------------
    # BUCKETS
    # --------------------------------------------------------

    buckets = [
        ("<=0", None, 1),
        ("1-2", 1, 3),
        ("3-5", 3, 6),
        ("6-8", 6, 9),
        ("9-12", 9, 13),
        ("13-20", 13, 21),
        ("21+", 21, None),
    ]

    bucket_rows = []

    for bucket_name, lower, upper in buckets:
        metrics = bucket_metrics(
            y_true,
            y_pred,
            lower,
            upper,
        )

        bucket_rows.append(
            {
                "model": model,
                "bucket": bucket_name,
                **metrics,
            }
        )

    return result, bucket_rows


# ============================================================
# RECOMMENDATION
# ============================================================

def safe_value(value):
    if value is None:
        return -np.inf

    try:
        value = float(value)
    except Exception:
        return -np.inf

    if np.isnan(value):
        return -np.inf

    return value


def choose_best_models(summary: list[dict]) -> dict:
    """
    Produce separate recommendations:

    1. Best absolute points model:
       RMSE first, then high-score recall.

    2. Best ranking model:
       Top-20 recall first, then Spearman.

    3. Best high-score detector:
       >=10 recall first, then >=10 precision.
    """

    best_rmse = min(
        summary,
        key=lambda x: safe_value(x.get("rmse", np.inf)),
    )

    best_ranking = max(
        summary,
        key=lambda x: (
            safe_value(x.get("top_20_recall")),
            safe_value(x.get("spearman")),
        ),
    )

    best_high_score = max(
        summary,
        key=lambda x: (
            safe_value(x.get("high_score_10_recall")),
            safe_value(x.get("high_score_10_precision")),
        ),
    )

    return {
        "best_points_model_by_rmse": best_rmse["model"],
        "best_ranking_model": best_ranking["model"],
        "best_high_score_detector": best_high_score["model"],
    }


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Final ranking and high-score diagnostic. "
            "Does NOT train models."
        )
    )

    parser.add_argument(
        "--predictions",
        default=str(DEFAULT_PREDICTIONS),
        help="Prediction CSV generated by diagnostic_compare_models.py",
    )

    parser.add_argument(
        "--output-csv",
        default=str(DEFAULT_OUTPUT_CSV),
    )

    parser.add_argument(
        "--output-json",
        default=str(DEFAULT_OUTPUT_JSON),
    )

    args = parser.parse_args()

    predictions_path = Path(args.predictions)
    output_csv = Path(args.output_csv)
    output_json = Path(args.output_json)

    print("=" * 80)
    print("FINAL FPL RANKING + HIGH-SCORE DIAGNOSTIC")
    print("=" * 80)
    print()
    print(f"Prediction source: {predictions_path}")
    print()

    df, actual_col = load_predictions(predictions_path)

    print(f"Loaded rows: {len(df):,}")
    print(f"Actual target column: {actual_col}")
    print()

    summary = []
    bucket_rows = []

    for model in MODELS:
        print(f"Analyzing {model}...")

        result, buckets = analyze_model(
            df,
            actual_col,
            model,
        )

        summary.append(result)
        bucket_rows.extend(buckets)

    summary_df = pd.DataFrame(summary)

    # ========================================================
    # METRICS
    # ========================================================

    print()
    print("=" * 80)
    print("OVERALL + RANKING METRICS")
    print("=" * 80)

    display_columns = [
        "model",
        "mae",
        "rmse",
        "bias",
        "spearman",
        "top_10_recall",
        "top_20_recall",
        "top_30_recall",
        "high_score_6_recall",
        "high_score_10_recall",
        "high_score_10_precision",
    ]

    print(
        summary_df[display_columns].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ========================================================
    # HIGH SCORE
    # ========================================================

    print()
    print("=" * 80)
    print("HIGH-SCORE DETECTION")
    print("=" * 80)

    high_score_columns = [
        "model",
        "actual_ge_6_count",
        "predicted_ge_6_count",
        "high_score_6_recall",
        "high_score_6_precision",
        "high_score_6_bias",
        "high_score_6_mae",
        "actual_ge_10_count",
        "predicted_ge_10_count",
        "high_score_10_recall",
        "high_score_10_precision",
        "high_score_10_bias",
        "high_score_10_mae",
    ]

    print(
        summary_df[high_score_columns].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ========================================================
    # BUCKET ANALYSIS
    # ========================================================

    bucket_df = pd.DataFrame(bucket_rows)

    print()
    print("=" * 80)
    print("ERROR BY ACTUAL POINTS")
    print("=" * 80)

    print(
        bucket_df[
            [
                "model",
                "bucket",
                "rows",
                "actual_mean",
                "prediction_mean",
                "bias",
                "mae",
                "rmse",
                "under_prediction_rate",
            ]
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    recommendations = choose_best_models(summary)

    print()
    print("=" * 80)
    print("MODEL RECOMMENDATION")
    print("=" * 80)

    print(
        f"Best points model by RMSE: "
        f"{recommendations['best_points_model_by_rmse']}"
    )

    print(
        f"Best ranking model: "
        f"{recommendations['best_ranking_model']}"
    )

    print(
        f"Best high-score detector (>=10): "
        f"{recommendations['best_high_score_detector']}"
    )

    # ========================================================
    # ENSEMBLE CHECK
    # ========================================================

    dl_row = summary_df[
        summary_df["model"] == "deep_learning"
    ]

    xgb_row = summary_df[
        summary_df["model"] == "xgboost"
    ]

    if not dl_row.empty and not xgb_row.empty:
        dl_top20 = float(
            dl_row.iloc[0]["top_20_recall"]
        )

        xgb_top20 = float(
            xgb_row.iloc[0]["top_20_recall"]
        )

        dl_high10 = float(
            dl_row.iloc[0]["high_score_10_recall"]
        )

        xgb_high10 = float(
            xgb_row.iloc[0]["high_score_10_recall"]
        )

        print()
        print("=" * 80)
        print("DL vs XGBOOST DECISION")
        print("=" * 80)

        print(
            f"DL Top-20 recall:       {dl_top20:.4f}"
        )
        print(
            f"XGBoost Top-20 recall:  {xgb_top20:.4f}"
        )
        print(
            f"DL >=10 recall:         {dl_high10:.4f}"
        )
        print(
            f"XGBoost >=10 recall:    {xgb_high10:.4f}"
        )

        if (
            dl_top20 > xgb_top20
            and dl_high10 >= xgb_high10
        ):
            print()
            print(
                "RESULT: Deep Learning shows evidence "
                "of a genuine ranking/high-score advantage."
            )
            print(
                "An ensemble/tiebreaker strategy is worth testing."
            )

        elif (
            xgb_top20 > dl_top20
            and xgb_high10 > dl_high10
        ):
            print()
            print(
                "RESULT: XGBoost currently dominates both "
                "ranking and high-score detection."
            )
            print(
                "Do NOT add Deep Learning to production yet."
            )

        else:
            print()
            print(
                "RESULT: Mixed evidence."
            )
            print(
                "Keep XGBoost/DL separate and avoid "
                "a blind ensemble."
            )

    # ========================================================
    # SAVE
    # ========================================================

    output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_json.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined_rows = []

    for row in summary:
        row_copy = dict(row)
        row_copy["row_type"] = "summary"
        combined_rows.append(row_copy)

    for row in bucket_rows:
        row_copy = dict(row)
        row_copy["row_type"] = "bucket"
        combined_rows.append(row_copy)

    pd.DataFrame(combined_rows).to_csv(
        output_csv,
        index=False,
    )

    json_payload = {
        "source": str(predictions_path),
        "actual_column": actual_col,
        "recommendations": recommendations,
        "models": summary,
        "buckets": bucket_rows,
    }

    with output_json.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            json_payload,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    print()
    print(f"CSV:  {output_csv}")
    print(f"JSON: {output_json}")
    print()


if __name__ == "__main__":
    main()