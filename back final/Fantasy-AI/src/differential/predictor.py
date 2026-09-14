"""Production predictor for the differential prediction layer.

Generates next-Gameweek breakout predictions and differential scores
by combining calibrated upside probabilities, value efficiency, and
ownership advantage.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import get_settings
from src.prediction.next_gameweek import (
    build_next_gameweek_rows,
    find_latest_completed_gameweek,
)
from src.differential.categories import assign_differential_categories
from src.differential.classifier import (
    load_differential_model,
    prepare_differential_matrix,
    enforce_probability_monotonicity,
    DifferentialModelResult,
)
from src.differential.features import build_differential_features
from src.differential.models import DifferentialPrediction
from src.differential.scoring import compute_scoring_formulas

logger = get_logger(__name__)


def generate_differential_predictions(
    data: pd.DataFrame,
    model_dir: str | Path = "models/differential",
    output_dir: str | Path = "models/differential",
    feedback5_predictions_path: str | Path | None = "models/feedback5/predictions_next_gameweek.csv",
    target_gameweek: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Generate differential rankings and upside predictions for the upcoming Gameweek.

    Args:
        data: Full feature dataset.
        model_dir: Directory where trained differential model artifacts reside.
        output_dir: Output directory for prediction CSV and metadata.
        feedback5_predictions_path: Optional path to existing Feedback 5 predictions.
        target_gameweek: Explicit next GW (if None, inferred dynamically).

    Returns:
        tuple[pd.DataFrame, dict]: (predictions_df, metadata_dict)
    """
    settings = get_settings()
    model_path = Path(model_dir) / "differential_model_8.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Trained differential model not found at {model_path}")

    logger.info("Loading differential model from %s", model_path)
    model_result = load_differential_model(model_path)

    # 1. Build entering rows for next Gameweek
    gw_rows = build_next_gameweek_rows(
        data=data,
        player_id_columns=settings.feature_engineering.player_id_columns,
        chronological_columns=settings.feature_engineering.chronological_columns,
        max_valid_gameweek=settings.prediction.max_valid_gameweek,
        target_gameweek=target_gameweek,
    )
    predicted_gw = int(gw_rows["GW"].iloc[0]) if "GW" in gw_rows.columns and not gw_rows.empty else 1
    logger.info("Prepared %d entering player rows for Gameweek %d.", len(gw_rows), predicted_gw)

    # 2. Engineer differential features on entering rows
    gw_feat = build_differential_features(gw_rows)

    # 3. Model inference: P(>= 8)
    X, _ = prepare_differential_matrix(
        gw_feat,
        feature_cols=model_result.feature_cols,
        train_medians=model_result.train_medians,
    )
    p_8 = model_result.model.predict_proba(X)[:, 1]

    # Check for multi-threshold companion models
    p_dict = {8: p_8}
    for th in (6, 10, 12):
        th_path = Path(model_dir) / f"differential_model_{th}.joblib"
        if th_path.exists():
            try:
                m_th = load_differential_model(th_path)
                X_th, _ = prepare_differential_matrix(
                    gw_feat, feature_cols=m_th.feature_cols, train_medians=m_th.train_medians,
                )
                p_dict[th] = m_th.model.predict_proba(X_th)[:, 1]
            except Exception as e:
                logger.warning("Could not load companion model %d: %s", th, e)
                # Fallback estimation
                factor = 1.6 if th == 6 else (0.5 if th == 10 else 0.25)
                p_dict[th] = np.clip(p_8 * factor, 0.0, 1.0)
        else:
            factor = 1.6 if th == 6 else (0.5 if th == 10 else 0.25)
            p_dict[th] = np.clip(p_8 * factor, 0.0, 1.0)

    # Enforce monotonicity: P(6+) >= P(8+) >= P(10+) >= P(12+)
    mono_probs = enforce_probability_monotonicity(p_dict, thresholds=(6, 8, 10, 12))

    gw_feat["p_6_plus"] = mono_probs[6]
    gw_feat["p_8_plus"] = mono_probs[8]
    gw_feat["p_10_plus"] = mono_probs[10]
    gw_feat["p_12_plus"] = mono_probs[12]

    # Enrich with live FPL bootstrap ownership & photos if available
    bootstrap_path = Path("data/raw/fpl_api/bootstrap_static.json")
    if bootstrap_path.exists():
        try:
            with open(bootstrap_path, "r", encoding="utf-8") as f:
                boot = json.load(f)
            elements = boot.get("elements", [])
            own_map = {e["id"]: float(e.get("selected_by_percent", 0.0)) for e in elements if "id" in e}
            photo_map = {
                e["id"]: f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{e.get('code')}.png"
                for e in elements if "id" in e and e.get("code")
            }
            pos_map = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
            elem_pos_map = {e["id"]: pos_map.get(e.get("element_type"), "MID") for e in elements if "id" in e}

            if "element" in gw_feat.columns:
                mapped_own = gw_feat["element"].map(own_map)
                if mapped_own.notna().any():
                    gw_feat["ownership_pct"] = mapped_own.fillna(5.0)
                    gw_feat["ownership_pct_approx"] = gw_feat["ownership_pct"] / 100.0
                    gw_feat["ownership_percentile"] = gw_feat["ownership_pct_approx"].rank(pct=True)
                gw_feat["photo_url"] = gw_feat["element"].map(photo_map)
                if "position" not in gw_feat.columns or gw_feat["position"].isna().all():
                    gw_feat["position"] = gw_feat["element"].map(elem_pos_map)
            logger.info("Enriched predictions with live FPL bootstrap static data.")
        except Exception as exc:
            logger.warning("Could not enrich with bootstrap static: %s", exc)

    # 4. Compute differential scores
    scored = compute_scoring_formulas(gw_feat, prob_col="p_8_plus")
    # Use score_f3 (sublinear exponent-balanced) or best scoring formula
    gw_feat["differential_score"] = scored["score_f3"]

    # 5. Assign categories
    gw_feat["differential_category"] = assign_differential_categories(
        gw_feat,
        prob_col="p_8_plus",
        ownership_col="ownership_percentile",
        value_col="value",
    )

    # 6. Attach Feedback 5 predicted expected points if available
    gw_feat["predicted_expected_points"] = 0.0
    if feedback5_predictions_path and Path(feedback5_predictions_path).exists():
        try:
            fb5 = pd.read_csv(feedback5_predictions_path)
            id_col = next((c for c in ["element", "player_id", "id"] if c in fb5.columns and c in gw_feat.columns), None)
            ep_col = next((c for c in ["predicted_expected_points", "predicted_points", "expected_points"] if c in fb5.columns), None)
            if id_col and ep_col:
                mapping = dict(zip(fb5[id_col], fb5[ep_col]))
                gw_feat["predicted_expected_points"] = gw_feat[id_col].map(mapping).fillna(0.0)
                logger.info("Joined %d Feedback 5 expected points.", len(mapping))
        except Exception as exc:
            logger.warning("Could not merge Feedback 5 expected points: %s", exc)

    # 7. Format clean output columns
    out_cols = [
        "element", "name", "team", "position", "value",
        "ownership_pct", "ownership_pct_approx", "ownership_percentile",
        "predicted_expected_points",
        "p_6_plus", "p_8_plus", "p_10_plus", "p_12_plus",
        "differential_score", "differential_category",
        "photo_url",
        "GW", "season",
    ]
    present_cols = [c for c in out_cols if c in gw_feat.columns]
    pred_df = gw_feat[present_cols].copy()

    # Rename GW to predicted_gameweek for clarity
    if "GW" in pred_df.columns:
        pred_df.rename(columns={"GW": "predicted_gameweek"}, inplace=True)
    if "value" in pred_df.columns:
        pred_df["price"] = pred_df["value"] / 10.0

    # Sort descending by differential score
    pred_df.sort_values(by="differential_score", ascending=False, inplace=True)
    pred_df.reset_index(drop=True, inplace=True)

    # 8. Save CSV and metadata
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    csv_file = out_p / "predictions_differential.csv"
    pred_df.to_csv(csv_file, index=False)
    logger.info("Saved %d differential predictions to %s", len(pred_df), csv_file)

    meta = {
        "season": str(pred_df["season"].iloc[0]) if "season" in pred_df.columns and not pred_df.empty else "unknown",
        "predicted_gameweek": predicted_gw,
        "count": len(pred_df),
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "elite_differentials_count": int((pred_df["differential_category"] == "Elite Differential").sum()),
        "value_differentials_count": int((pred_df["differential_category"] == "Value Differential").sum()),
        "emerging_differentials_count": int((pred_df["differential_category"] == "Emerging Differential").sum()),
        "model_used": model_result.model_name,
    }
    json_file = out_p / "predictions_differential_metadata.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return pred_df, meta
