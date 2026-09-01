"""Run historical walk-forward evaluation of Base DL vs Adaptive DL."""

import pandas as pd
import numpy as np
from pathlib import Path
from src.config.settings import get_settings
from src.prediction.feedback.snapshot_store import PredictionSnapshotStore
from src.prediction.feedback.feedback_store import FeedbackStore
from src.prediction.feedback.residual_model import ResidualModel
from src.prediction.feedback.feedback_adapter import FeedbackAdapter
from src.prediction.feedback.evaluation import FeedbackEvaluator
from src.training.deep_learning import TabularMLPRegressor, DeepLearningConfig
from src.training.dataset import select_feature_columns

def run_historical_dl_evaluation():
    settings = get_settings()
    features_path = settings.paths.processed_data_dir / "vaastav_features.csv"
    if not features_path.exists():
        print("Features file not found.")
        return

    print("Loading engineered features...")
    df = pd.read_csv(features_path, low_memory=False)
    
    # We will evaluate on season 2025-26 (Gameweeks 1 to 38)
    eval_season = "2025-26"
    train_df = df[df["season"] < eval_season].copy()
    test_df = df[df["season"] == eval_season].copy()
    
    print(f"Train rows (pre-{eval_season}): {len(train_df)}")
    print(f"Eval rows ({eval_season}): {len(test_df)}")
    
    feature_cols = select_feature_columns(train_df, settings.training)
    print(f"Selected {len(feature_cols)} feature columns.")
    
    # Impute missing values
    medians = train_df[feature_cols].median()
    X_train = train_df[feature_cols].fillna(medians).values.astype(np.float32)
    y_train = train_df[settings.training.target_column].fillna(0.0).values.astype(np.float32)
    
    # Train Base DL model
    print("Training Base Deep Learning (Weighted Huber) model...")
    dl_config = DeepLearningConfig(
        hidden_layers=[128, 64, 32],
        epochs=15,
        batch_size=256,
        learning_rate=0.001,
        loss_type="weighted_huber",
        random_state=42
    )
    dl_model = TabularMLPRegressor(config=dl_config)
    dl_model.fit(X_train, y_train)
    print("Base DL model training complete.")
    
    # Setup temporary feedback stores for historical eval
    eval_dir = settings.paths.processed_data_dir / "eval_historical"
    snap_dir = eval_dir / "snapshots"
    fb_dir = eval_dir / "feedback"
    snap_store = PredictionSnapshotStore(snap_dir)
    fb_store = FeedbackStore(fb_dir)
    
    # Generate predictions for each GW of 2025-26
    gws = sorted(test_df["GW"].unique())
    print(f"Evaluating across {len(gws)} Gameweeks (GW{min(gws)} to GW{max(gws)})...")
    
    for gw in gws:
        gw_df = test_df[test_df["GW"] == gw].copy()
        X_gw = gw_df[feature_cols].fillna(medians).values.astype(np.float32)
        base_preds = dl_model.predict(X_gw)
        
        pred_df = gw_df[["element", "name", "team", "position"]].copy()
        pred_df["predicted_total_points"] = base_preds
        
        snap_store.save_snapshot(
            predictions=pred_df,
            season=eval_season,
            target_gw=int(gw),
            model_name="deep_learning_weighted_huber",
            model_version="historical_eval_v1",
            prediction_column="predicted_total_points"
        )
        
        snap = snap_store.load_snapshot(eval_season, int(gw))
        fb_store.generate_feedback(snap, gw_df, eval_season, int(gw))
        
    all_fb = fb_store.load_feedback(season=eval_season)
    print(f"Total historical feedback records generated: {len(all_fb)}")
    
    result = FeedbackEvaluator.evaluate_from_feedback(all_fb, min_gameweeks=3)
    comparison_text = FeedbackEvaluator.format_comparison(result)
    print("\n" + comparison_text)
    
    out_file = settings.paths.models_dir / "feedback" / "dl_walk_forward_evaluation.txt"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(comparison_text, encoding="utf-8")
    print(f"\nSaved evaluation report to {out_file}")

if __name__ == "__main__":
    run_historical_dl_evaluation()
