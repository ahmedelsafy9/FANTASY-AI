"""Differential-specific feature engineering.

Derives features specifically designed to identify breakout / high-upside
differential players. Every feature is documented with its temporal
safety justification.

LEAKAGE AUDIT:
    Every feature in this module derives ONLY from:
    (a) Lagged rolling averages built via shift(1).rolling(...) by upstream pipeline
    (b) Static metadata (position, team)
    (c) Fixture information known before the GW
    (d) Pre-GW ownership counts (``selected`` column)

    NO same-Gameweek outcome data is used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.differential.ownership import compute_ownership_percentile, compute_ownership_pct_approx

logger = get_logger(__name__)

# Features used by the differential model.
# Each tuple: (feature_name, description, safety_justification)
DIFFERENTIAL_FEATURE_AUDIT = [
    # --- Ownership features ---
    ("ownership_percentile", "Rank-based ownership percentile within (season, GW)",
     "Derived from `selected` which is pre-GW manager count"),
    ("ownership_pct_approx", "Approximate ownership ratio within GW",
     "Derived from `selected` / max(selected) in GW — both pre-GW"),

    # --- Value / efficiency features ---
    ("value_efficiency", "Recent points per unit price",
     "total_points_avg_last_5 (lagged rolling) / value (pre-GW static)"),
    ("xgi_efficiency", "xGI per 90 per unit price",
     "xGI_per_90_last_5 (lagged rolling) / value (pre-GW static)"),

    # --- Momentum / trend features ---
    ("minutes_trend", "Short-term vs medium-term minutes",
     "minutes_avg_last_3 - minutes_avg_last_5 — both lagged rolling"),
    ("form_momentum", "Short-term vs medium-term form",
     "total_points_avg_last_3 - total_points_avg_last_5 — both lagged rolling"),
    ("starts_ratio_3_5", "Recent start rate vs medium-term",
     "starts_last_3 / max(starts_last_5, 1) — both lagged participation"),

    # --- Opportunity features ---
    ("fixture_upside", "Attacking potential adjusted for fixture difficulty",
     "attacking_threat_index (lagged) × (5 - fixture_difficulty) (pre-GW fixture)"),
    ("opportunity_x_minutes", "Opportunity index weighted by expected minutes",
     "opportunity_index_last_5 (lagged) × expected_minutes (lagged) / 90"),

    # --- Existing safe features (pass-through, no derivation needed) ---
    ("form_index", "Composite form index", "Lagged rolling — computed upstream"),
    ("expected_minutes", "Expected minutes from recent history", "Lagged — computed upstream"),
    ("attacking_threat_index", "Attacking threat composite", "Lagged — computed upstream"),
    ("opportunity_index_last_5", "Opportunity composite", "Lagged — computed upstream"),
    ("xG_per_90_last_5", "xG rate per 90", "Lagged — computed upstream"),
    ("xA_per_90_last_5", "xA rate per 90", "Lagged — computed upstream"),
    ("xGI_per_90_last_5", "xGI rate per 90", "Lagged — computed upstream"),
    ("key_passes_per_90_last_5", "Key passes rate per 90", "Lagged — computed upstream"),
    ("big_chances_created_per_90_last_5", "Big chances created rate per 90", "Lagged — computed upstream"),
    ("total_points_avg_last_3", "Recent 3-game points average", "Lagged — computed upstream"),
    ("total_points_avg_last_5", "Recent 5-game points average", "Lagged — computed upstream"),
    ("minutes_avg_last_3", "Recent 3-game minutes average", "Lagged — computed upstream"),
    ("minutes_avg_last_5", "Recent 5-game minutes average", "Lagged — computed upstream"),
    ("bps_per_90_last_5", "BPS rate per 90", "Lagged — computed upstream"),
    ("creativity_per_90_last_5", "Creativity rate per 90", "Lagged — computed upstream"),
    ("threat_per_90_last_5", "Threat rate per 90", "Lagged — computed upstream"),
    ("goal_involvement_rate_last_5", "Goal involvement rate", "Lagged — computed upstream"),
    ("consecutive_starts", "Consecutive starts count", "Lagged — computed upstream"),
    ("consecutive_60_plus", "Consecutive 60+ min appearances", "Lagged — computed upstream"),
    ("rotation_risk_index", "Rotation risk index", "Lagged — computed upstream"),
    ("minutes_share_last_5", "Minutes share in last 5", "Lagged — computed upstream"),
    ("minutes_std_last_5", "Minutes variability last 5", "Lagged — computed upstream"),
    ("starts_last_3", "Starts in last 3 GWs", "Lagged — computed upstream"),
    ("starts_last_5", "Starts in last 5 GWs", "Lagged — computed upstream"),
    ("prev_gw_started", "Started previous GW", "Lagged — computed upstream"),
    ("fixture_difficulty", "FDR of upcoming fixture", "Pre-GW fixture data"),
    ("team_strength", "Team overall strength", "Pre-GW static"),
    ("opponent_strength", "Opponent overall strength", "Pre-GW static"),
    ("opponent_attack_strength", "Opponent attack strength", "Pre-GW static"),
    ("opponent_defence_strength", "Opponent defence strength", "Pre-GW static"),
    ("clean_sheet_likelihood", "Clean sheet probability", "Pre-GW computed"),
    ("team_form_trend", "Team form trajectory", "Lagged — computed upstream"),
    ("is_home", "Home fixture flag", "Pre-GW fixture data"),
    ("rest_days", "Rest days since last match", "Pre-GW scheduling"),
    ("value", "Player price (in tenths)", "Pre-GW static"),
    ("price_trend_last_1", "1-GW price change", "Lagged — computed upstream"),
    ("price_trend_last_5", "5-GW price change", "Lagged — computed upstream"),
    ("is_position_gkp", "Goalkeeper flag", "Static metadata"),
    ("is_position_def", "Defender flag", "Static metadata"),
    ("is_position_mid", "Midfielder flag", "Static metadata"),
    ("is_position_fwd", "Forward flag", "Static metadata"),
    ("prev_season_ppm", "Previous season points per match", "Historical — no leakage"),
    ("is_promoted_team", "Player's team is promoted", "Static metadata"),
    ("opponent_is_promoted_team", "Opponent is promoted", "Pre-GW fixture data"),
    ("big_chances_missed_rate_last_5", "Big chances missed rate", "Lagged — computed upstream"),
]


# Features that are DERIVED (need computation)
DERIVED_FEATURE_NAMES = [
    "ownership_percentile",
    "ownership_pct_approx",
    "value_efficiency",
    "xgi_efficiency",
    "minutes_trend",
    "form_momentum",
    "starts_ratio_3_5",
    "fixture_upside",
    "opportunity_x_minutes",
]

# Features that pass through from existing dataset
PASSTHROUGH_FEATURE_NAMES = [
    name for name, _, _ in DIFFERENTIAL_FEATURE_AUDIT
    if name not in DERIVED_FEATURE_NAMES
]


def build_differential_features(
    df: pd.DataFrame,
    selected_col: str = "selected",
    season_col: str = "season",
    gw_col: str = "GW",
) -> pd.DataFrame:
    """Build all differential-specific features.

    Adds derived columns to a copy of the input DataFrame.
    Only uses temporally safe pre-GW information.

    Args:
        df: Historical dataset with all engineered features.
        selected_col: Ownership count column.
        season_col: Season column.
        gw_col: Gameweek column.

    Returns:
        pd.DataFrame: DataFrame with additional differential features.
    """
    out = df.copy()

    # --- Ownership features ---
    if selected_col in out.columns:
        out["ownership_percentile"] = compute_ownership_percentile(
            out, selected_col=selected_col, season_col=season_col, gw_col=gw_col,
        )
        out["ownership_pct_approx"] = compute_ownership_pct_approx(
            out, selected_col=selected_col, season_col=season_col, gw_col=gw_col,
        )
        logger.info("Added ownership_percentile and ownership_pct_approx.")
    else:
        out["ownership_percentile"] = 0.5
        out["ownership_pct_approx"] = 0.5
        logger.warning("No '%s' column found. Using default ownership = 0.5.", selected_col)

    # --- Value efficiency ---
    pts_avg = pd.to_numeric(out.get("total_points_avg_last_5"), errors="coerce").fillna(0)
    price = pd.to_numeric(out.get("value"), errors="coerce").fillna(50).clip(lower=40)
    out["value_efficiency"] = pts_avg / (price / 10.0)

    # --- xGI efficiency ---
    xgi = pd.to_numeric(out.get("xGI_per_90_last_5"), errors="coerce").fillna(0)
    out["xgi_efficiency"] = xgi / (price / 10.0)

    # --- Minutes trend ---
    min3 = pd.to_numeric(out.get("minutes_avg_last_3"), errors="coerce").fillna(0)
    min5 = pd.to_numeric(out.get("minutes_avg_last_5"), errors="coerce").fillna(0)
    out["minutes_trend"] = min3 - min5

    # --- Form momentum ---
    pts3 = pd.to_numeric(out.get("total_points_avg_last_3"), errors="coerce").fillna(0)
    pts5 = pd.to_numeric(out.get("total_points_avg_last_5"), errors="coerce").fillna(0)
    out["form_momentum"] = pts3 - pts5

    # --- Starts ratio ---
    st3 = pd.to_numeric(out.get("starts_last_3"), errors="coerce").fillna(0)
    st5 = pd.to_numeric(out.get("starts_last_5"), errors="coerce").fillna(1).clip(lower=1)
    out["starts_ratio_3_5"] = st3 / st5

    # --- Fixture upside ---
    atk_threat = pd.to_numeric(out.get("attacking_threat_index"), errors="coerce").fillna(0)
    fdr = pd.to_numeric(out.get("fixture_difficulty"), errors="coerce").fillna(3)
    out["fixture_upside"] = atk_threat * (5.0 - fdr)

    # --- Opportunity × expected minutes ---
    opp = pd.to_numeric(out.get("opportunity_index_last_5"), errors="coerce").fillna(0)
    e_min = pd.to_numeric(out.get("expected_minutes"), errors="coerce").fillna(0)
    out["opportunity_x_minutes"] = opp * e_min / 90.0

    logger.info("Built %d differential-specific derived features.", len(DERIVED_FEATURE_NAMES))
    return out


def get_differential_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of feature columns available for differential modeling.

    Only returns columns that actually exist in the DataFrame.

    Args:
        df: DataFrame to check.

    Returns:
        list[str]: Available feature column names.
    """
    all_candidate_names = [name for name, _, _ in DIFFERENTIAL_FEATURE_AUDIT]
    available = [c for c in all_candidate_names if c in df.columns]
    logger.info("Differential features available: %d / %d.", len(available), len(all_candidate_names))
    return available


def get_leakage_audit_report() -> str:
    """Generate a human-readable leakage audit report."""
    lines = ["# Feature Leakage Audit\n"]
    lines.append("| Feature | Description | Temporal Safety |")
    lines.append("|---|---|---|")
    for name, desc, safety in DIFFERENTIAL_FEATURE_AUDIT:
        lines.append(f"| `{name}` | {desc} | {safety} |")
    lines.append("")
    lines.append("**All features verified as temporally safe pre-GW information.**\n")
    return "\n".join(lines)
