from pathlib import Path
import json
import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "models"
    / "experiments"
    / "dl_high_score"
    / "experiment_predictions.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "models"
    / "diagnostic"
    / "dl_high_score_analysis"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# EXPERIMENTS
# ============================================================

EXPERIMENTS = [
    "Baseline DL",
    "Exp A: Sample Weighting",
    "Exp B: Huber Loss (beta=4.0)",
    "Exp C: Weighted Huber",
    "Exp E: Magnitude Weighted Huber",
]


BUCKET_ORDER = [
    "<=0",
    "1-2",
    "3-5",
    "6-8",
    "9-12",
    "13-20",
    "21+",
]


# ============================================================
# BUCKET FUNCTION
# ============================================================

def make_bucket(x):

    if x <= 0:
        return "<=0"

    if x <= 2:
        return "1-2"

    if x <= 5:
        return "3-5"

    if x <= 8:
        return "6-8"

    if x <= 12:
        return "9-12"

    if x <= 20:
        return "13-20"

    return "21+"


# ============================================================
# METRICS
# ============================================================

def calculate_bucket_metrics(
    actual,
    prediction,
    bucket,
):

    mask = actual["bucket"] == bucket

    y_true = actual.loc[mask, "actual"].to_numpy()
    y_pred = prediction.loc[mask].to_numpy()

    if len(y_true) == 0:
        return None

    error = y_pred - y_true

    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error ** 2))
    bias = np.mean(error)

    under_prediction_rate = np.mean(
        y_pred < y_true
    )

    return {
        "rows": len(y_true),
        "actual_mean": np.mean(y_true),
        "prediction_mean": np.mean(y_pred),
        "bias": bias,
        "absolute_bias": abs(bias),
        "mae": mae,
        "rmse": rmse,
        "under_prediction_rate": under_prediction_rate,
    }


# ============================================================
# HIGH SCORE METRICS
# ============================================================

def calculate_threshold_metrics(
    actual,
    prediction,
    threshold,
):

    actual_positive = actual >= threshold
    predicted_positive = prediction >= threshold

    actual_count = actual_positive.sum()
    predicted_count = predicted_positive.sum()

    true_positive = (
        actual_positive
        & predicted_positive
    ).sum()

    recall = (
        true_positive / actual_count
        if actual_count > 0
        else np.nan
    )

    precision = (
        true_positive / predicted_count
        if predicted_count > 0
        else np.nan
    )

    return {
        "actual_count": int(actual_count),
        "predicted_count": int(predicted_count),
        "recall": recall,
        "precision": precision,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("DEEP LEARNING HIGH-SCORE UNDERPREDICTION ANALYSIS")
    print("=" * 80)

    print(f"\nInput:")
    print(INPUT_FILE)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Could not find:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print(
        f"\nLoaded rows: {len(df):,}"
    )

    print(
        "\nExperiments detected:"
    )

    for experiment in EXPERIMENTS:
        print(f"  - {experiment}")

    # --------------------------------------------------------
    # Prepare actual values
    # --------------------------------------------------------

    actual_df = pd.DataFrame()

    actual_df["actual"] = pd.to_numeric(
        df["actual_points"],
        errors="coerce",
    )

    actual_df = actual_df.dropna()

    actual_df["bucket"] = (
        actual_df["actual"]
        .apply(make_bucket)
    )

    # --------------------------------------------------------
    # Bucket analysis
    # --------------------------------------------------------

    all_bucket_results = []

    for experiment in EXPERIMENTS:

        print(
            f"\nAnalyzing {experiment}..."
        )

        prediction = pd.to_numeric(
            df.loc[
                actual_df.index,
                experiment
            ],
            errors="coerce",
        )

        valid_mask = prediction.notna()

        actual_valid = actual_df.loc[
            valid_mask
        ]

        prediction_valid = prediction.loc[
            valid_mask
        ]

        for bucket in BUCKET_ORDER:

            metrics = calculate_bucket_metrics(
                actual_valid,
                prediction_valid,
                bucket,
            )

            if metrics is None:
                continue

            metrics["model"] = experiment
            metrics["bucket"] = bucket

            all_bucket_results.append(
                metrics
            )

    bucket_df = pd.DataFrame(
        all_bucket_results
    )

    bucket_df = bucket_df[
        [
            "model",
            "bucket",
            "rows",
            "actual_mean",
            "prediction_mean",
            "bias",
            "absolute_bias",
            "mae",
            "rmse",
            "under_prediction_rate",
        ]
    ]

    bucket_file = (
        OUTPUT_DIR
        / "all_bucket_metrics.csv"
    )

    bucket_df.to_csv(
        bucket_file,
        index=False,
    )

    # --------------------------------------------------------
    # Print bucket results
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("BUCKET PERFORMANCE")
    print("=" * 80)

    for experiment in EXPERIMENTS:

        print(
            f"\n--- {experiment} ---"
        )

        result = bucket_df[
            bucket_df["model"] == experiment
        ]

        print(
            result[
                [
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

    # --------------------------------------------------------
    # Bias comparison
    # --------------------------------------------------------

    bias_table = bucket_df.pivot(
        index="bucket",
        columns="model",
        values="bias",
    )

    bias_table = bias_table.reindex(
        BUCKET_ORDER
    )

    bias_table.to_csv(
        OUTPUT_DIR
        / "bias_by_bucket.csv"
    )

    # --------------------------------------------------------
    # Absolute bias improvement vs baseline
    # --------------------------------------------------------

    baseline_abs = bucket_df[
        bucket_df["model"] == "Baseline DL"
    ][
        [
            "bucket",
            "absolute_bias",
        ]
    ].rename(
        columns={
            "absolute_bias":
            "baseline_absolute_bias"
        }
    )

    comparison = bucket_df.merge(
        baseline_abs,
        on="bucket",
        how="left",
    )

    comparison[
        "absolute_bias_improvement"
    ] = (
        comparison["baseline_absolute_bias"]
        - comparison["absolute_bias"]
    )

    comparison[
        "absolute_bias_improvement_pct"
    ] = (
        comparison[
            "absolute_bias_improvement"
        ]
        / comparison[
            "baseline_absolute_bias"
        ]
        * 100
    )

    comparison_file = (
        OUTPUT_DIR
        / "bias_improvement_vs_baseline.csv"
    )

    comparison.to_csv(
        comparison_file,
        index=False,
    )

    # --------------------------------------------------------
    # High-score analysis
    # --------------------------------------------------------

    high_buckets = [
        "6-8",
        "9-12",
        "13-20",
        "21+",
    ]

    high_score_df = comparison[
        comparison["bucket"].isin(
            high_buckets
        )
    ].copy()

    print("\n")
    print("=" * 80)
    print("HIGH-SCORE BIAS IMPROVEMENT")
    print("=" * 80)

    for experiment in EXPERIMENTS:

        if experiment == "Baseline DL":
            continue

        result = high_score_df[
            high_score_df["model"]
            == experiment
        ]

        print(
            f"\n--- {experiment} ---"
        )

        print(
            result[
                [
                    "bucket",
                    "baseline_absolute_bias",
                    "absolute_bias",
                    "absolute_bias_improvement",
                    "absolute_bias_improvement_pct",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.4f}",
            )
        )

    # --------------------------------------------------------
    # Threshold metrics
    # --------------------------------------------------------

    threshold_results = []

    for experiment in EXPERIMENTS:

        prediction = pd.to_numeric(
            df[experiment],
            errors="coerce",
        )

        mask = (
            actual_df["actual"].notna()
            & prediction.notna()
        )

        actual = (
            actual_df.loc[mask, "actual"]
            .to_numpy()
        )

        pred = (
            prediction.loc[mask]
            .to_numpy()
        )

        row = {
            "model": experiment
        }

        for threshold in [6, 10]:

            metrics = calculate_threshold_metrics(
                actual,
                pred,
                threshold,
            )

            row[
                f">={threshold}_actual_count"
            ] = metrics["actual_count"]

            row[
                f">={threshold}_predicted_count"
            ] = metrics["predicted_count"]

            row[
                f">={threshold}_recall"
            ] = metrics["recall"]

            row[
                f">={threshold}_precision"
            ] = metrics["precision"]

        threshold_results.append(row)

    threshold_df = pd.DataFrame(
        threshold_results
    )

    threshold_file = (
        OUTPUT_DIR
        / "high_score_threshold_metrics.csv"
    )

    threshold_df.to_csv(
        threshold_file,
        index=False,
    )

    print("\n")
    print("=" * 80)
    print("HIGH-SCORE THRESHOLD METRICS")
    print("=" * 80)

    print(
        threshold_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # --------------------------------------------------------
    # Determine best model for high scores
    # --------------------------------------------------------

    high_bias_summary = []

    for experiment in EXPERIMENTS:

        result = high_score_df[
            high_score_df["model"]
            == experiment
        ]

        mean_abs_bias = (
            result["absolute_bias"]
            .mean()
        )

        mean_mae = (
            result["mae"]
            .mean()
        )

        underprediction = (
            result["under_prediction_rate"]
            .mean()
        )

        high_bias_summary.append(
            {
                "model": experiment,
                "mean_high_score_absolute_bias":
                    mean_abs_bias,
                "mean_high_score_mae":
                    mean_mae,
                "mean_high_score_underprediction_rate":
                    underprediction,
            }
        )

    high_summary = pd.DataFrame(
        high_bias_summary
    )

    high_summary = high_summary.sort_values(
        "mean_high_score_absolute_bias"
    )

    high_summary.to_csv(
        OUTPUT_DIR
        / "high_score_model_ranking.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Final answer
    # --------------------------------------------------------

    baseline_high_bias = high_summary[
        high_summary["model"]
        == "Baseline DL"
    ][
        "mean_high_score_absolute_bias"
    ].iloc[0]

    weighted_huber_high_bias = high_summary[
        high_summary["model"]
        == "Exp C: Weighted Huber"
    ][
        "mean_high_score_absolute_bias"
    ].iloc[0]

    weighted_huber_improvement = (
        (
            baseline_high_bias
            - weighted_huber_high_bias
        )
        / baseline_high_bias
        * 100
    )

    baseline_ge10 = threshold_df[
        threshold_df["model"]
        == "Baseline DL"
    ][
        ">=10_recall"
    ].iloc[0]

    weighted_huber_ge10 = threshold_df[
        threshold_df["model"]
        == "Exp C: Weighted Huber"
    ][
        ">=10_recall"
    ].iloc[0]

    # --------------------------------------------------------
    # Summary JSON
    # --------------------------------------------------------

    summary = {
        "baseline_high_score_mean_absolute_bias":
            float(baseline_high_bias),

        "weighted_huber_high_score_mean_absolute_bias":
            float(weighted_huber_high_bias),

        "weighted_huber_high_score_bias_improvement_pct":
            float(weighted_huber_improvement),

        "baseline_ge10_recall":
            float(baseline_ge10),

        "weighted_huber_ge10_recall":
            float(weighted_huber_ge10),

        "high_score_bias_improved":
            bool(
                weighted_huber_high_bias
                < baseline_high_bias
            ),

        "ge10_recall_improved":
            bool(
                weighted_huber_ge10
                > baseline_ge10
            ),

        "output_files": {
            "all_bucket_metrics":
                str(bucket_file),

            "bias_improvement":
                str(comparison_file),

            "threshold_metrics":
                str(threshold_file),

            "high_score_ranking":
                str(
                    OUTPUT_DIR
                    / "high_score_model_ranking.csv"
                ),
        },
    }

    with open(
        OUTPUT_DIR
        / "analysis_summary.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
        )

    # --------------------------------------------------------
    # Final console result
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("FINAL CONCLUSION")
    print("=" * 80)

    print(
        f"\nBaseline DL mean absolute bias "
        f"(high-score buckets): "
        f"{baseline_high_bias:.4f}"
    )

    print(
        f"Weighted Huber mean absolute bias: "
        f"{weighted_huber_high_bias:.4f}"
    )

    print(
        f"\nWeighted Huber high-score bias "
        f"improvement: "
        f"{weighted_huber_improvement:.2f}%"
    )

    print(
        f"\n>=10 recall:"
        f"\n  Baseline DL:       {baseline_ge10:.4f}"
        f"\n  Weighted Huber:    {weighted_huber_ge10:.4f}"
    )

    if (
        weighted_huber_high_bias
        < baseline_high_bias
        and weighted_huber_ge10
        > baseline_ge10
    ):

        print(
            "\nRESULT: YES"
        )

        print(
            "Weighted Huber improved both "
            "high-score bias and >=10 recall."
        )

    elif (
        weighted_huber_high_bias
        < baseline_high_bias
    ):

        print(
            "\nRESULT: PARTIAL"
        )

        print(
            "Weighted Huber reduced high-score "
            "underprediction, but >=10 recall "
            "did not improve."
        )

    else:

        print(
            "\nRESULT: NO"
        )

        print(
            "Weighted Huber did not reduce "
            "high-score underprediction."
        )

    print("\nGenerated files:")

    print(
        OUTPUT_DIR
        / "all_bucket_metrics.csv"
    )

    print(
        OUTPUT_DIR
        / "bias_by_bucket.csv"
    )

    print(
        OUTPUT_DIR
        / "bias_improvement_vs_baseline.csv"
    )

    print(
        OUTPUT_DIR
        / "high_score_threshold_metrics.csv"
    )

    print(
        OUTPUT_DIR
        / "high_score_model_ranking.csv"
    )

    print(
        OUTPUT_DIR
        / "analysis_summary.json"
    )

    print("\nDone.")


if __name__ == "__main__":
    main()