"""Builds one feature row per player representing their next Gameweek state.

Constructs a leakage-free snapshot of each active player's CURRENT-SEASON state
using strictly completed matches in the current season prior to the target Gameweek,
combined with explicit historical priors and upcoming fixture context.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import PredictionError

logger = get_logger(__name__)


def build_next_gameweek_rows(
    data: pd.DataFrame,
    player_id_columns: tuple[str, ...],
    chronological_columns: tuple[str, ...],
    max_valid_gameweek: int,
    target_gameweek: int | None = None,
) -> pd.DataFrame:
    """Build current-season feature rows for every active player for the next Gameweek.

    For a target Gameweek N:
    - Current-season state features (form, rolling stats, minutes, participation,
      workload, EWMA) are computed strictly from completed matches in the current
      season (GW < N).
    - Historical priors (prev_season_points, prev_season_minutes, etc.) are attached
      via stable player identity.
    - Upcoming fixture context (opponent, difficulty, home/away) describes the upcoming match.

    Args:
        data: The full engineered dataset.
        player_id_columns: Candidate columns identifying a player in priority order.
        chronological_columns: Candidate columns defining match order (e.g. ("season", "GW")).
        max_valid_gameweek: The last Gameweek of a season (typically 38).
        target_gameweek: Explicit target Gameweek to build features for. If None,
            inferred as (latest completed GW in current season + 1).

    Returns:
        pd.DataFrame: One row per active current-season player representing their
        entering state for the target Gameweek.

    Raises:
        PredictionError: If required player identifier or chronological columns are missing.
    """
    # ------------------------------------------------------------------
    # 1. Resolve player identifier and chronological columns
    # ------------------------------------------------------------------
    player_id_column = next(
        (c for c in player_id_columns if c in data.columns), None
    )
    if player_id_column is None:
        raise PredictionError(
            f"No player identifier column found among {player_id_columns}."
        )

    sort_columns = [c for c in chronological_columns if c in data.columns]
    if not sort_columns:
        raise PredictionError(
            f"No chronological column found among {chronological_columns}; "
            "cannot determine current season."
        )
    gw_column = sort_columns[-1]

    # ------------------------------------------------------------------
    # 2. Restrict to the current (latest) season
    # ------------------------------------------------------------------
    season_column = sort_columns[0] if len(sort_columns) > 1 else None
    latest_season: str | None = None

    if season_column is not None and season_column in data.columns:
        latest_season = data[season_column].max()
        current_season_data = data[data[season_column] == latest_season].copy()
        logger.info(
            "Restricting prediction candidates to current season '%s' "
            "(%d row(s) out of %d total).",
            latest_season,
            len(current_season_data),
            len(data),
        )
    else:
        current_season_data = data.copy()

    if current_season_data.empty:
        raise PredictionError(
            "No rows found for the current season after filtering. "
            "Ensure the engineered dataset contains current-season data."
        )

    # Get one base template row per player in the current season
    working = current_season_data.sort_values(by=sort_columns, kind="mergesort")
    latest_rows = working.groupby(player_id_column, as_index=False).tail(1).copy()

    # ------------------------------------------------------------------
    # 3. Determine target Gameweek and completed matches cutoff
    # ------------------------------------------------------------------
    if target_gameweek is None:
        current_gw = pd.to_numeric(latest_rows[gw_column], errors="coerce").fillna(1).astype(int)
        predicted_for_gw = (current_gw + 1).where(current_gw < max_valid_gameweek, other=1)
        latest_rows["predicted_for_gw"] = predicted_for_gw.astype("Int64")
    else:
        latest_rows["predicted_for_gw"] = int(target_gameweek)

    logger.info(
        "Built %d next-Gameweek candidate(s) for season '%s'.",
        len(latest_rows),
        latest_season if latest_season is not None else "unknown",
    )

    # ------------------------------------------------------------------
    # 4. If current-season matches exist, update in-season state
    # ------------------------------------------------------------------
    p_indexed = latest_rows.set_index(player_id_column)
    completed_all = current_season_data.sort_values(by=sort_columns, kind="mergesort")

    # Map stat names to output feature prefixes
    rolling_stat_specs = [
        ("total_points", "total_points"),
        ("minutes", "minutes"),
        ("bps", "bps"),
        ("ict_index", "ict_index"),
        ("expected_goals", "xG"),
        ("expected_assists", "xA"),
        ("threat", "threat"),
        ("creativity", "creativity"),
        ("influence", "influence"),
        ("goals_scored", "goals_scored"),
        ("assists", "assists"),
        ("bonus", "bonus"),
        ("key_passes", "key_passes"),
        ("big_chances_created", "big_chances_created"),
        ("big_chances_missed", "big_chances_missed"),
    ]

    for p_id, p_group in completed_all.groupby(player_id_column):
        if p_id not in p_indexed.index:
            continue

        p_target_gw = p_indexed.loc[p_id, "predicted_for_gw"]
        if pd.notna(p_target_gw):
            p_comp = p_group[pd.to_numeric(p_group[gw_column], errors="coerce") < int(p_target_gw)]
        else:
            p_comp = p_group

        if p_comp.empty:
            continue

        # 4.1 In-season rolling stats
        for src_col, out_prefix in rolling_stat_specs:
            if src_col in p_comp.columns:
                num_s = pd.to_numeric(p_comp[src_col], errors="coerce").dropna()
                if not num_s.empty:
                    for w in (3, 5, 10):
                        out_col = f"{out_prefix}_avg_last_{w}"
                        p_indexed.loc[p_id, out_col] = float(num_s.tail(w).mean())

        # 4.2 Participation
        mins = pd.to_numeric(p_comp["minutes"], errors="coerce").fillna(0.0) if "minutes" in p_comp.columns else pd.Series([0.0])
        starts = pd.to_numeric(p_comp["starts"], errors="coerce").fillna(mins >= 60).astype(float) if "starts" in p_comp.columns else (mins >= 60).astype(float)
        last_m = float(mins.iloc[-1]) if not mins.empty else 0.0
        last_start = float(starts.iloc[-1]) if not starts.empty else 0.0

        p_indexed.loc[p_id, "prev_gw_minutes"] = last_m
        p_indexed.loc[p_id, "prev_gw_played"] = 1.0 if last_m > 0 else 0.0
        p_indexed.loc[p_id, "prev_gw_started"] = 1.0 if last_start > 0 else 0.0
        p_indexed.loc[p_id, "prev_gw_bench_unused"] = 1.0 if last_m == 0 else 0.0

        for w in (3, 5):
            p_indexed.loc[p_id, f"starts_last_{w}"] = float(starts.tail(w).mean())
            p_indexed.loc[p_id, f"bench_unused_last_{w}"] = float((mins.tail(w) == 0).astype(float).mean())

        # 4.3 Expected minutes & rotation risk
        mins_5 = mins.tail(5)
        m_mean_5 = float(mins_5.mean())
        m_std_5 = float(mins_5.std()) if len(mins_5) >= 2 else 0.0

        p_indexed.loc[p_id, "minutes_std_last_5"] = m_std_5
        p_indexed.loc[p_id, "minutes_share_last_5"] = m_mean_5 / 90.0
        p_indexed.loc[p_id, "rotation_risk_index"] = m_std_5 / (m_mean_5 + 1.0)
        ewma_val = float(mins.ewm(halflife=3.0, min_periods=1).mean().iloc[-1])
        p_indexed.loc[p_id, "expected_minutes"] = ewma_val

        # Streaks
        cond_starts = (starts > 0).tolist()
        cond_60 = (mins >= 60).tolist()
        cond_90 = (mins >= 89).tolist()

        def _streak_len(bool_list: list[bool]) -> float:
            count = 0
            for val in reversed(bool_list):
                if val:
                    count += 1
                else:
                    break
            return float(count)

        p_indexed.loc[p_id, "consecutive_starts"] = _streak_len(cond_starts)
        p_indexed.loc[p_id, "consecutive_60_plus"] = _streak_len(cond_60)
        p_indexed.loc[p_id, "consecutive_90s"] = _streak_len(cond_90)

        # 4.4 Form index & derived per-90 metrics
        m_avg_5 = p_indexed.loc[p_id, "minutes_avg_last_5"] if "minutes_avg_last_5" in p_indexed.columns else np.nan
        valid_m = max(float(m_avg_5), 1.0) if pd.notna(m_avg_5) and float(m_avg_5) > 0 else 1.0
        has_m = pd.notna(m_avg_5) and float(m_avg_5) > 0

        def _p90(col: str) -> float:
            val = p_indexed.loc[p_id, col] if col in p_indexed.columns else np.nan
            if has_m and pd.notna(val):
                return float(val) / valid_m * 90.0
            return 0.0

        th_p90 = _p90("threat_avg_last_5")
        cr_p90 = _p90("creativity_avg_last_5")
        bps_p90 = _p90("bps_avg_last_5")
        xg_p90 = _p90("xG_avg_last_5")
        xa_p90 = _p90("xA_avg_last_5")
        kp_p90 = _p90("key_passes_avg_last_5")
        bcc_p90 = _p90("big_chances_created_avg_last_5")

        p_indexed.loc[p_id, "threat_per_90_last_5"] = th_p90
        p_indexed.loc[p_id, "creativity_per_90_last_5"] = cr_p90
        p_indexed.loc[p_id, "bps_per_90_last_5"] = bps_p90
        p_indexed.loc[p_id, "xG_per_90_last_5"] = xg_p90
        p_indexed.loc[p_id, "xA_per_90_last_5"] = xa_p90
        p_indexed.loc[p_id, "key_passes_per_90_last_5"] = kp_p90
        p_indexed.loc[p_id, "big_chances_created_per_90_last_5"] = bcc_p90
        p_indexed.loc[p_id, "xGI_per_90_last_5"] = xg_p90 + xa_p90
        p_indexed.loc[p_id, "opportunity_index_last_5"] = 0.4 * xg_p90 + 0.3 * xa_p90 + 0.3 * kp_p90
        p_indexed.loc[p_id, "attacking_threat_index"] = 0.6 * th_p90 + 0.4 * cr_p90

        # Form index
        p3 = p_indexed.loc[p_id, "total_points_avg_last_3"] if "total_points_avg_last_3" in p_indexed.columns else np.nan
        p5 = p_indexed.loc[p_id, "total_points_avg_last_5"] if "total_points_avg_last_5" in p_indexed.columns else np.nan
        p10 = p_indexed.loc[p_id, "total_points_avg_last_10"] if "total_points_avg_last_10" in p_indexed.columns else np.nan

        f_pairs = [(p3, 0.5), (p5, 0.3), (p10, 0.2)]
        valid_pairs = [(v, w) for v, w in f_pairs if pd.notna(v)]
        if valid_pairs:
            total_w = sum(w for _, w in valid_pairs)
            p_indexed.loc[p_id, "form_index"] = sum(float(v) * (w / total_w) for v, w in valid_pairs)

    latest_rows = p_indexed.reset_index()
    max_pred_gw = int(latest_rows["predicted_for_gw"].max()) if "predicted_for_gw" in latest_rows.columns and not latest_rows["predicted_for_gw"].isna().all() else 1
    logger.info(
        "Built %d next-Gameweek row(s) for season '%s' (target GW: %d).",
        len(latest_rows),
        latest_season if latest_season is not None else "unknown",
        max_pred_gw,
    )
    return latest_rows.reset_index(drop=True)
