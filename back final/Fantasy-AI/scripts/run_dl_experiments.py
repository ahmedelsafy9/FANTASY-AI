"""Run structured Deep Learning experiments for high-score prediction improvements.

Experiments:
1. Baseline DL (SmoothL1Loss beta=1.0)
2. Exp A: Sample Weighting (Discrete point buckets)
3. Exp B: Huber Loss (SmoothL1Loss beta=4.0)
4. Exp C: Weighted Huber Loss (Huber beta=4.0 + Discrete sample weights)
5. Exp D/E: Optimal Loss + Weighting combination evaluated on Validation set,
   then evaluated ONCE on held-out test set.

All outputs are saved to `models/experiments/dl_high_score/`.
"""

from __future__ import annotations

import json
import time
import sys
from pathlib import Path

# Make repository importable when executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.config.settings import get_settings
from src.training.dataset import prepare_split_dataset
from src.training.deep_learning import TabularMLPRegressor, DeepLearningConfig, _build_mlp
from src.training.ranking_metrics import high_score_recall, top_n_recall


OUTPUT_DIR = Path("models/experiments/dl_high_score")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def calculate_metrics_dict(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true_arr = np.asarray(y_true, dtype=np.float64).ravel()
    y_pred_arr = np.asarray(y_pred, dtype=np.float64).ravel()

    error = y_pred_arr - y_true_arr
    abs_error = np.abs(error)
    ss_res = np.sum(error ** 2)
    ss_tot = np.sum((y_true_arr - np.mean(y_true_arr)) ** 2)
    r2_val = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")

    # Spearman correlation
    if len(y_true_arr) >= 2 and np.std(y_true_arr) > 0 and np.std(y_pred_arr) > 0:
        r_true = pd.Series(y_true_arr).rank().to_numpy()
        r_pred = pd.Series(y_pred_arr).rank().to_numpy()
        spearman_val = float(np.corrcoef(r_true, r_pred)[0, 1])
    else:
        spearman_val = float("nan")

    # High score precision (>=10)
    mask_10 = y_true_arr >= 10.0
    if mask_10.sum() > 0:
        prec_10 = float((y_pred_arr[mask_10] >= 10.0).mean())
    else:
        prec_10 = float("nan")

    return {
        "mae": float(np.mean(abs_error)),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "bias": float(np.mean(error)),
        "r2": r2_val,
        "spearman": spearman_val,
        "top_10_recall": float(top_n_recall(y_true_arr, y_pred_arr, n=10)),
        "top_20_recall": float(top_n_recall(y_true_arr, y_pred_arr, n=20)),
        "ge_6_recall": float(high_score_recall(y_true_arr, y_pred_arr, threshold=6.0, pred_threshold=6.0)),
        "ge_10_recall": float(high_score_recall(y_true_arr, y_pred_arr, threshold=10.0, pred_threshold=10.0)),
        "ge_10_precision": prec_10,
    }


def compute_bucket_diagnostics(y_true: np.ndarray, y_pred: np.ndarray, model_name: str) -> list[dict]:
    df = pd.DataFrame({"actual": y_true, "prediction": y_pred})
    bins = [-np.inf, 0, 2, 5, 8, 12, 20, np.inf]
    labels = ["<=0", "1-2", "3-5", "6-8", "9-12", "13-20", "21+"]
    df["bucket"] = pd.cut(df["actual"], bins=bins, labels=labels)

    rows = []
    for b_label, group in df.groupby("bucket", observed=False):
        if len(group) == 0:
            continue
        err = group["prediction"].to_numpy() - group["actual"].to_numpy()
        rows.append({
            "model": model_name,
            "bucket": str(b_label),
            "rows": int(len(group)),
            "actual_mean": float(group["actual"].mean()),
            "prediction_mean": float(group["prediction"].mean()),
            "bias": float(err.mean()),
            "mae": float(np.abs(err).mean()),
            "rmse": float(np.sqrt(np.mean(err ** 2))),
            "underprediction_rate": float((err < 0).mean()),
        })
    return rows


def get_discrete_sample_weights(y: np.ndarray) -> np.ndarray:
    w = np.ones(len(y), dtype=np.float32)
    w[(y >= 3) & (y <= 5)] = 1.2
    w[(y >= 6) & (y <= 8)] = 1.5
    w[(y >= 9) & (y <= 12)] = 2.0
    w[(y >= 13) & (y <= 20)] = 2.5
    w[y >= 21] = 3.0
    return w


def main():
    settings = get_settings()
    input_path = settings.paths.processed_data_dir / 'vaastav_features.csv'
    data = pd.read_csv(input_path, low_memory=False)
    split = prepare_split_dataset(data, settings.training)

    X_train = split.X_train.to_numpy(dtype=np.float32)
    y_train = split.y_train.to_numpy(dtype=np.float32)
    w_train_recency = split.train_weights.to_numpy(dtype=np.float32)

    X_test = split.X_test.to_numpy(dtype=np.float32)
    y_test = split.y_test.to_numpy(dtype=np.float32)

    print("=" * 80)
    print("RUNNING DEEP LEARNING EXPERIMENTS")
    print("=" * 80)

    experiments = [
        {
            "name": "Baseline DL",
            "loss_beta": 1.0,
            "weight_strategy": "recency_only",
            "high_score_power": 0.0,
        },
        {
            "name": "Exp A: Sample Weighting",
            "loss_beta": 1.0,
            "weight_strategy": "discrete_buckets",
            "high_score_power": 0.0,
        },
        {
            "name": "Exp B: Huber Loss (beta=4.0)",
            "loss_beta": 4.0,
            "weight_strategy": "recency_only",
            "high_score_power": 0.0,
        },
        {
            "name": "Exp C: Weighted Huber",
            "loss_beta": 4.0,
            "weight_strategy": "discrete_buckets",
            "high_score_power": 0.0,
        },
        {
            "name": "Exp E: Magnitude Weighted Huber",
            "loss_beta": 4.0,
            "weight_strategy": "magnitude_power",
            "high_score_power": 0.5,
        },
    ]

    all_val_metrics = []
    all_test_metrics = []
    all_bucket_rows = []
    test_preds_dict = {}

    for exp in experiments:
        exp_name = exp["name"]
        print(f"\n---> Training: {exp_name}...")

        # Construct sample weights
        if exp["weight_strategy"] == "recency_only":
            effective_weights = w_train_recency
        elif exp["weight_strategy"] == "discrete_buckets":
            effective_weights = w_train_recency * get_discrete_sample_weights(y_train)
        elif exp["weight_strategy"] == "magnitude_power":
            effective_weights = w_train_recency * (1.0 + exp["high_score_power"] * np.clip(y_train, 0, None))
        else:
            effective_weights = w_train_recency

        cfg = DeepLearningConfig(
            hidden_layers=settings.training.dl_hidden_layers,
            dropout=settings.training.dl_dropout,
            learning_rate=settings.training.dl_learning_rate,
            weight_decay=settings.training.dl_weight_decay,
            batch_size=settings.training.dl_batch_size,
            epochs=settings.training.dl_epochs,
            patience=settings.training.dl_patience,
            use_batch_norm=settings.training.dl_use_batch_norm,
            loss_beta=exp["loss_beta"],
            high_score_weight_power=exp["high_score_power"],
            random_state=settings.training.random_state,
        )

        model = TabularMLPRegressor(config=cfg)

        # Fit model
        start_time = time.perf_counter()
        model.fit(X_train, y_train, sample_weight=effective_weights)
        train_time = time.perf_counter() - start_time

        # Get validation predictions (internal chronological 15% validation split)
        n_total = len(X_train)
        n_val = max(1, int(n_total * 0.15))
        n_tr = n_total - n_val

        X_val_tr = X_train[n_tr:]
        y_val_tr = y_train[n_tr:]

        val_preds = model.predict(X_val_tr)
        val_metrics = calculate_metrics_dict(y_val_tr, val_preds)
        val_metrics["model"] = exp_name
        val_metrics["train_seconds"] = train_time
        all_val_metrics.append(val_metrics)

        # Get test predictions (held-out test set evaluated ONCE)
        test_preds = model.predict(X_test)
        test_preds_dict[exp_name] = test_preds
        test_metrics = calculate_metrics_dict(y_test, test_preds)
        test_metrics["model"] = exp_name
        test_metrics["train_seconds"] = train_time
        all_test_metrics.append(test_metrics)

        # Bucket metrics
        b_rows = compute_bucket_diagnostics(y_test, test_preds, exp_name)
        all_bucket_rows.extend(b_rows)

        print(f"     Val RMSE: {val_metrics['rmse']:.4f} | Test RMSE: {test_metrics['rmse']:.4f} | Test MAE: {test_metrics['mae']:.4f} | >=10 Recall: {test_metrics['ge_10_recall']:.4f}")

    # Convert to DataFrames
    val_df = pd.DataFrame(all_val_metrics)
    test_df = pd.DataFrame(all_test_metrics)
    bucket_df = pd.DataFrame(all_bucket_rows)

    # Save CSVs
    val_df.to_csv(OUTPUT_DIR / "validation_metrics.csv", index=False)
    test_df.to_csv(OUTPUT_DIR / "test_metrics.csv", index=False)
    bucket_df.to_csv(OUTPUT_DIR / "bucket_diagnostics.csv", index=False)

    # Save predictions CSV
    preds_df = pd.DataFrame({"actual_points": y_test})
    for name, preds in test_preds_dict.items():
        preds_df[name] = preds
    preds_df.to_csv(OUTPUT_DIR / "experiment_predictions.csv", index=False)

    # Output Summary JSON
    summary_json = {
        "validation_metrics": val_df.to_dict(orient="records"),
        "test_metrics": test_df.to_dict(orient="records"),
    }
    with open(OUTPUT_DIR / "experiment_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    # Save markdown summary report
    md_lines = [
        "# Deep Learning High-Score Experiments Report",
        "",
        "## Validation Set Performance (Model Selection)",
        "",
        "```",
        val_df.to_string(index=False),
        "```",
        "",
        "## Test Set Performance (Final Evaluation)",
        "",
        "```",
        test_df.to_string(index=False),
        "```",
        "",
        "## Bucket Diagnostics (Test Set)",
        "",
        "```",
        bucket_df.to_string(index=False),
        "```",
    ]

    with open(OUTPUT_DIR / "experiment_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print("\n" + "=" * 80)
    print("EXPERIMENTS COMPLETE")
    print("=" * 80)
    print(f"Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
