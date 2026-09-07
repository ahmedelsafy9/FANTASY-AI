"""Script to execute production predictions after GW3 ingestion.

Verifies:
- current season = 2026-27
- latest completed GW = 3
- prediction target = GW4
- Exports predictions to data/processed/predictions_feedback5.csv
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from src.config.settings import get_settings
from src.prediction.next_gameweek import build_next_gameweek_rows
from src.high_score.classifier import predict_high_score_probabilities
from src.high_score.quantile import predict_quantiles
from src.high_score.hybrid import predict_hybrid_scores

settings = get_settings()
models_dir = settings.paths.models_dir / "high_score"
fpl_dir = Path("data/raw/fpl_api")

# 1. Load historical engineered data
df = pd.read_csv("data/processed/vaastav_features.csv", low_memory=False)

# 2. Ingest real GW2 and GW3 data from live FPL API files
bootstrap = json.loads((fpl_dir / "bootstrap_static.json").read_text(encoding="utf-8"))
team_names = {team["id"]: team.get("name") for team in bootstrap.get("teams", [])}
players = {p["id"]: p for p in bootstrap.get("elements", [])}

def load_live_gw(event_id: int) -> pd.DataFrame:
    live_file = fpl_dir / f"event_{event_id}_live.json"
    if not live_file.exists():
        raise FileNotFoundError(f"Missing live file {live_file}")
    live_data = json.loads(live_file.read_text(encoding="utf-8"))
    rows = []
    for el in live_data.get("elements", []):
        p_id = el.get("id")
        stats = dict(el.get("stats", {}))
        p_info = players.get(p_id, {})
        rows.append({
            "element": p_id,
            "name": p_info.get("web_name"),
            "team": team_names.get(p_info.get("team")),
            "GW": event_id,
            "season": "2026-27",
            "value": p_info.get("now_cost"),
            **stats,
        })
    return pd.DataFrame(rows)

gw2_live = load_live_gw(2)
gw3_live = load_live_gw(3)

# Build unified dataset with completed GW1, GW2, GW3
s26_base = df[df["season"] == "2026-27"].copy()

# Ensure matching columns
gw2_rows = s26_base.copy()
gw2_rows["GW"] = 2
# Update actual stats from gw2_live
gw2_map = gw2_live.set_index("element")
for idx, r in gw2_rows.iterrows():
    p_id = r["element"]
    if p_id in gw2_map.index:
        l_stat = gw2_map.loc[p_id]
        if isinstance(l_stat, pd.DataFrame):
            l_stat = l_stat.iloc[0]
        gw2_rows.at[idx, "total_points"] = l_stat.get("total_points", 0)
        gw2_rows.at[idx, "minutes"] = l_stat.get("minutes", 0)
        gw2_rows.at[idx, "bps"] = l_stat.get("bps", 0)
        gw2_rows.at[idx, "goals_scored"] = l_stat.get("goals_scored", 0)
        gw2_rows.at[idx, "assists"] = l_stat.get("assists", 0)

gw3_rows = s26_base.copy()
gw3_rows["GW"] = 3
gw3_map = gw3_live.set_index("element")
for idx, r in gw3_rows.iterrows():
    p_id = r["element"]
    if p_id in gw3_map.index:
        l_stat = gw3_map.loc[p_id]
        if isinstance(l_stat, pd.DataFrame):
            l_stat = l_stat.iloc[0]
        gw3_rows.at[idx, "total_points"] = l_stat.get("total_points", 0)
        gw3_rows.at[idx, "minutes"] = l_stat.get("minutes", 0)
        gw3_rows.at[idx, "bps"] = l_stat.get("bps", 0)
        gw3_rows.at[idx, "goals_scored"] = l_stat.get("goals_scored", 0)
        gw3_rows.at[idx, "assists"] = l_stat.get("assists", 0)

df_with_gw3 = pd.concat([df, gw2_rows, gw3_rows], ignore_index=True)

# 3. Dynamic target detection
next_rows = build_next_gameweek_rows(
    df_with_gw3,
    player_id_columns=settings.feature_engineering.player_id_columns,
    chronological_columns=settings.feature_engineering.chronological_columns,
    max_valid_gameweek=settings.prediction.max_valid_gameweek,
)

current_season = df_with_gw3["season"].max()
latest_completed_gw = int(df_with_gw3[df_with_gw3["season"] == current_season]["GW"].max())
target_gw = int(next_rows["predicted_for_gw"].mode().iloc[0])

print("\n" + "="*80)
print("INFERENCE VERIFICATION AFTER GW3 INGESTION")
print("="*80)
print(f"Current Season:        {current_season}")
print(f"Latest Completed GW:   {latest_completed_gw}")
print(f"Prediction Target GW:  {target_gw}")

assert current_season == "2026-27", f"Expected 2026-27, got {current_season}"
assert latest_completed_gw == 3, f"Expected 3, got {latest_completed_gw}"
assert target_gw == 4, f"Expected 4, got {target_gw}"

# 4. Load production models
meta = json.loads((models_dir / "model_metadata.json").read_text(encoding="utf-8"))
features = meta["features"]
medians = meta["train_medians"]

m_exp = joblib.load(models_dir / "expected_points_model.joblib")
hs_models = joblib.load(models_dir / "high_score_classifiers.joblib")
q_models = joblib.load(models_dir / "quantile_models.joblib")
blender = joblib.load(models_dir / "hybrid_blender.joblib")

X_inf = next_rows[features].apply(pd.to_numeric, errors="coerce").fillna(medians).fillna(0)

# 5. Predictions
preds_exp = m_exp.predict(X_inf)
hs_probs = predict_high_score_probabilities(hs_models, next_rows)
q_preds = predict_quantiles(q_models, next_rows)

comp_inf = pd.DataFrame({
    "oof_exp": preds_exp,
    "oof_hs6": hs_probs["prob_high_score_6"].values,
    "oof_q85": q_preds["pred_q_85"].values,
    "prob_high_score_6": hs_probs["prob_high_score_6"].values,
    "prob_high_score_10": hs_probs["prob_high_score_10"].values,
})
calibrated_exp, rank_scores = predict_hybrid_scores(blender, comp_inf)

next_rows["predicted_expected_points"] = np.round(calibrated_exp, 2)
next_rows["predicted_total_points"] = np.round(calibrated_exp, 2)
next_rows["predicted_fpl_rank_score"] = np.round(rank_scores, 2)
next_rows["prob_high_score_6"] = np.round(hs_probs["prob_high_score_6"].values, 3)
next_rows["prob_high_score_10"] = np.round(hs_probs["prob_high_score_10"].values, 3)
next_rows["ceiling_p85"] = np.round(q_preds["pred_q_85"].values, 2)

export_cols = [
    c for c in ["element", "name", "team", "value", "predicted_for_gw",
                "predicted_expected_points", "predicted_fpl_rank_score",
                "prob_high_score_6", "prob_high_score_10", "ceiling_p85"]
    if c in next_rows.columns
]

out_csv = settings.paths.processed_data_dir / "predictions_feedback5.csv"
sorted_out = next_rows[export_cols].sort_values("predicted_fpl_rank_score", ascending=False)
sorted_out.to_csv(out_csv, index=False)
print(f"Saved {len(sorted_out)} predictions for GW {target_gw} to {out_csv}")

print("\nTop 10 players by FPL Rank Score for GW 4:")
for _, r in sorted_out.head(10).iterrows():
    print(
        f"  {r.get('name', '?'):<25} | Rank Score: {r.get('predicted_fpl_rank_score', 0):5.2f} | "
        f"Exp Pts: {r.get('predicted_expected_points', 0):5.2f} | P(>=6): {r.get('prob_high_score_6', 0)*100:4.1f}% | "
        f"Ceiling(P85): {r.get('ceiling_p85', 0):5.2f}"
    )
