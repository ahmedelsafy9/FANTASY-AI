"""Router: GET /differentials/next-gameweek.

Serves precomputed differential and breakout player predictions
for the upcoming Gameweek.
"""

from __future__ import annotations

import math
from typing import Any
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import DifferentialListResponse, DifferentialPlayerResponse
from src.config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/differentials", tags=["differentials"])


def _clean_val(v: Any, default: Any = None) -> Any:
    """Helper to ensure NaN/Inf values don't break JSON serialization."""
    if v is None:
        return default
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return default
    return v


@router.get("/next-gameweek", response_model=DifferentialListResponse)
def get_next_gameweek_differentials(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Max players to return"),
    category: str | None = Query(default=None, description="Filter by category (e.g. 'Elite Differential')"),
    position: str | None = Query(default=None, description="Filter by position (e.g. 'MID', 'FWD')"),
    max_price: float | None = Query(default=None, ge=3.5, le=16.0, description="Max price in £M"),
    max_ownership: float | None = Query(default=None, ge=0.0, le=100.0, description="Max ownership percentage"),
) -> DifferentialListResponse:
    """Return top differential picks for the next Gameweek ranked by differential score.

    Combines high upside probability with low ownership and price efficiency.
    """
    app_state = getattr(request.app.state, "fantasy_ai_state", None)
    if app_state is None:
        raise HTTPException(status_code=503, detail="Application state is not ready.")

    diff_df: pd.DataFrame | None = getattr(app_state, "differential_predictions", None)
    season = getattr(app_state, "season", None)
    latest_completed_gw = getattr(app_state, "latest_completed_gameweek", None)
    predicted_gw = getattr(app_state, "predicted_gameweek", None)
    generated_at = getattr(app_state, "generated_at", None)

    # Fallback to main predictions if differential predictions not yet built
    if diff_df is None or diff_df.empty:
        logger.info("Differential predictions not loaded. Synthesizing from main predictions pool...")
        preds = getattr(app_state, "predictions", None)
        if preds is None or preds.empty:
            return DifferentialListResponse(
                count=0,
                season=season,
                latest_completed_gameweek=latest_completed_gw,
                predicted_gameweek=predicted_gw,
                generated_at=generated_at,
                predictions=[],
            )
        # Synthesize on the fly
        work_df = preds.copy()
        if "differential_score" not in work_df.columns:
            from src.differential.features import build_differential_features
            from src.differential.categories import assign_differential_categories
            from src.differential.scoring import compute_scoring_formulas

            work_df = build_differential_features(work_df)
            p8 = work_df.get("prob_high_score_8", work_df.get("p_8_plus", 0.1))
            work_df["p_8_plus"] = pd.to_numeric(p8, errors="coerce").fillna(0.1)
            work_df["p_6_plus"] = pd.to_numeric(work_df.get("prob_high_score_6", 0.2), errors="coerce").fillna(0.2)
            work_df["p_10_plus"] = pd.to_numeric(work_df.get("prob_high_score_10", 0.05), errors="coerce").fillna(0.05)
            work_df["p_12_plus"] = pd.to_numeric(work_df.get("prob_high_score_12", 0.02), errors="coerce").fillna(0.02)
            scored = compute_scoring_formulas(work_df, prob_col="p_8_plus")
            work_df["differential_score"] = scored["score_f3"]
            work_df["differential_category"] = assign_differential_categories(work_df)
            work_df.sort_values(by="differential_score", ascending=False, inplace=True)
        diff_df = work_df

    filtered = diff_df.copy()

    # Apply filters
    if category:
        filtered = filtered[filtered["differential_category"].astype(str).str.lower() == category.strip().lower()]

    if position and "position" in filtered.columns:
        filtered = filtered[filtered["position"].astype(str).str.upper() == position.strip().upper()]

    if max_price is not None:
        price_series = filtered["price"] if "price" in filtered.columns else filtered["value"] / 10.0
        filtered = filtered[price_series <= max_price]

    if max_ownership is not None and "ownership_pct_approx" in filtered.columns:
        filtered = filtered[filtered["ownership_pct_approx"] * 100.0 <= max_ownership]

    top_rows = filtered.head(limit)

    results: list[DifferentialPlayerResponse] = []
    for _, row in top_rows.iterrows():
        elem = int(row["element"]) if pd.notna(row.get("element")) else None
        name = str(row.get("name", "Unknown"))
        team = str(row.get("team", ""))
        pos = str(row.get("position", "")) if pd.notna(row.get("position")) else None

        price = None
        if "price" in row and pd.notna(row["price"]):
            price = round(float(row["price"]), 1)
        elif "value" in row and pd.notna(row["value"]):
            price = round(float(row["value"]) / 10.0, 1)

        val = float(row["value"]) if pd.notna(row.get("value")) else None

        own_pct = None
        if "ownership_pct_approx" in row and pd.notna(row["ownership_pct_approx"]):
            own_pct = round(float(row["ownership_pct_approx"]) * 100.0, 1)
        elif "ownership_pct" in row and pd.notna(row["ownership_pct"]):
            own_pct = round(float(row["ownership_pct"]), 1)

        own_pctl = float(row["ownership_percentile"]) if pd.notna(row.get("ownership_percentile")) else None

        ep = None
        for ep_col in ["predicted_expected_points", "predicted_points", "predicted_total_points"]:
            if ep_col in row and pd.notna(row[ep_col]):
                ep = round(float(row[ep_col]), 2)
                break

        p6 = round(float(row["p_6_plus"]), 3) if pd.notna(row.get("p_6_plus")) else None
        p8 = round(float(row["p_8_plus"]), 3) if pd.notna(row.get("p_8_plus")) else None
        p10 = round(float(row["p_10_plus"]), 3) if pd.notna(row.get("p_10_plus")) else None
        p12 = round(float(row["p_12_plus"]), 3) if pd.notna(row.get("p_12_plus")) else None

        diff_score = round(float(row.get("differential_score", 0.0)), 2)
        diff_cat = str(row.get("differential_category", "Standard Differential"))
        pred_gw = int(row["predicted_gameweek"]) if pd.notna(row.get("predicted_gameweek")) else predicted_gw
        photo = str(row.get("photo_url")) if pd.notna(row.get("photo_url")) else None

        results.append(DifferentialPlayerResponse(
            element=elem,
            name=name,
            team=team,
            position=pos,
            price=price,
            value=val,
            ownership_pct=own_pct,
            ownership_percentile=own_pctl,
            predicted_expected_points=ep,
            p_6_plus=p6,
            p_8_plus=p8,
            p_10_plus=p10,
            p_12_plus=p12,
            differential_score=diff_score,
            differential_category=diff_cat,
            predicted_gameweek=pred_gw,
            photo_url=photo,
        ))

    return DifferentialListResponse(
        count=len(results),
        season=season,
        latest_completed_gameweek=latest_completed_gw,
        predicted_gameweek=predicted_gw,
        generated_at=generated_at,
        predictions=results,
    )
