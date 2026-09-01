"""Deterministic and Distribution-Aware FPL Scoring Engine.

Converts predicted football contributions (goals, assists, clean sheets,
minutes/appearance probabilities, goals conceded, saves, cards, bonus) into
expected FPL points strictly using official FPL scoring rules and player
position mechanics.

Also models full point distributions via vectorized Monte Carlo simulation to
extract:
    - Expected Points (E[Points])
    - Floor Points (10th percentile)
    - Median Points (50th percentile)
    - 75th, 85th, 90th, 95th Percentiles
    - Ceiling Points (95th percentile upside)
    - Upside Points (P85 - Expected)
    - Captaincy Score (weighted combination of expectation, upside, and start security)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FPLPointBreakdown:
    """Detailed breakdown of expected FPL point contributions."""

    appearance_points: float
    goal_points: float
    assist_points: float
    clean_sheet_points: float
    goals_conceded_points: float
    save_points: float
    card_points: float
    bonus_points: float
    total_points: float

    def to_dict(self) -> dict[str, float]:
        """Convert breakdown to a dictionary."""
        return {
            "appearance_points": round(self.appearance_points, 4),
            "goal_points": round(self.goal_points, 4),
            "assist_points": round(self.assist_points, 4),
            "clean_sheet_points": round(self.clean_sheet_points, 4),
            "goals_conceded_points": round(self.goals_conceded_points, 4),
            "save_points": round(self.save_points, 4),
            "card_points": round(self.card_points, 4),
            "bonus_points": round(self.bonus_points, 4),
            "total_points": round(self.total_points, 4),
        }


@dataclass(frozen=True)
class FPLDistributionResult:
    """Detailed distribution and upside analysis for a player."""

    expected_points: float
    floor_points: float
    p50_points: float
    p75_points: float
    p85_points: float
    p90_points: float
    p95_points: float
    ceiling_points: float
    upside_points: float
    captaincy_score: float

    def to_dict(self) -> dict[str, float]:
        """Convert distribution result to a dictionary."""
        return {
            "expected_points": round(self.expected_points, 4),
            "floor_points": round(self.floor_points, 4),
            "p50_points": round(self.p50_points, 4),
            "p75_points": round(self.p75_points, 4),
            "p85_points": round(self.p85_points, 4),
            "p90_points": round(self.p90_points, 4),
            "p95_points": round(self.p95_points, 4),
            "ceiling_points": round(self.ceiling_points, 4),
            "upside_points": round(self.upside_points, 4),
            "captaincy_score": round(self.captaincy_score, 4),
        }


class ScoringEngine:
    """Deterministic & Distribution-Aware FPL scoring engine.

    Converts event predictions to expected FPL points and simulates full outcome
    distributions.
    """

    @staticmethod
    def _extract_position_flags(
        data: pd.DataFrame | dict[str, Any] | np.ndarray,
        n_samples: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract or infer one-hot position boolean masks (GKP, DEF, MID, FWD)."""
        if isinstance(data, pd.DataFrame):
            if "is_position_gkp" in data.columns:
                is_gkp = pd.to_numeric(data["is_position_gkp"], errors="coerce").fillna(0.0).to_numpy() > 0.5
                is_def = pd.to_numeric(data.get("is_position_def", 0.0), errors="coerce").fillna(0.0).to_numpy() > 0.5
                is_mid = pd.to_numeric(data.get("is_position_mid", 0.0), errors="coerce").fillna(0.0).to_numpy() > 0.5
                is_fwd = pd.to_numeric(data.get("is_position_fwd", 0.0), errors="coerce").fillna(0.0).to_numpy() > 0.5
                return is_gkp, is_def, is_mid, is_fwd

            if "position" in data.columns:
                pos = data["position"].astype(str).str.upper()
                is_gkp = (pos == "GKP") | (pos == "GK") | (pos == "1")
                is_def = (pos == "DEF") | (pos == "2")
                is_mid = (pos == "MID") | (pos == "3")
                is_fwd = (pos == "FWD") | (pos == "4")
                return is_gkp.to_numpy(), is_def.to_numpy(), is_mid.to_numpy(), is_fwd.to_numpy()

            if "element_type" in data.columns:
                elem = pd.to_numeric(data["element_type"], errors="coerce").fillna(3).astype(int)
                return (elem == 1).to_numpy(), (elem == 2).to_numpy(), (elem == 3).to_numpy(), (elem == 4).to_numpy()

        elif isinstance(data, dict):
            if "is_position_gkp" in data:
                is_gkp = np.asarray(data["is_position_gkp"], dtype=float) > 0.5
                is_def = np.asarray(data.get("is_position_def", 0.0), dtype=float) > 0.5
                is_mid = np.asarray(data.get("is_position_mid", 0.0), dtype=float) > 0.5
                is_fwd = np.asarray(data.get("is_position_fwd", 0.0), dtype=float) > 0.5
                return is_gkp, is_def, is_mid, is_fwd

            if "position" in data:
                pos = np.asarray(data["position"], dtype=str)
                pos_upper = np.char.upper(pos)
                is_gkp = (pos_upper == "GKP") | (pos_upper == "GK") | (pos_upper == "1")
                is_def = (pos_upper == "DEF") | (pos_upper == "2")
                is_mid = (pos_upper == "MID") | (pos_upper == "3")
                is_fwd = (pos_upper == "FWD") | (pos_upper == "4")
                return is_gkp, is_def, is_mid, is_fwd

        # Default fallback if no position provided: MID
        is_gkp = np.zeros(n_samples, dtype=bool)
        is_def = np.zeros(n_samples, dtype=bool)
        is_mid = np.ones(n_samples, dtype=bool)
        is_fwd = np.zeros(n_samples, dtype=bool)
        return is_gkp, is_def, is_mid, is_fwd

    @classmethod
    def calculate_expected_points(
        cls,
        events: dict[str, np.ndarray | list[float] | float],
        positions: pd.DataFrame | dict[str, Any] | np.ndarray | None = None,
    ) -> np.ndarray:
        """Vectorized computation of expected FPL points from event predictions."""
        breakdown_df = cls.calculate_breakdown(events, positions)
        return breakdown_df["predicted_total_points"].to_numpy()

    @classmethod
    def calculate_breakdown(
        cls,
        events: dict[str, np.ndarray | list[float] | float],
        positions: pd.DataFrame | dict[str, Any] | np.ndarray | None = None,
    ) -> pd.DataFrame:
        """Vectorized computation returning the full points breakdown table."""
        sample_val = next(iter(events.values()))
        if np.isscalar(sample_val):
            n_samples = 1
        else:
            n_samples = len(sample_val)  # type: ignore

        def _to_arr(key: str, default: float = 0.0) -> np.ndarray:
            val = events.get(key, default)
            arr = np.asarray(val, dtype=np.float64)
            if arr.ndim == 0:
                arr = np.full(n_samples, fill_value=float(arr), dtype=np.float64)
            return np.nan_to_num(arr, nan=default)

        # 1. Event predictions
        p_play_any = np.clip(_to_arr("p_play_any", 1.0), 0.0, 1.0)
        p_play_60 = np.clip(_to_arr("p_play_60", 0.8), 0.0, 1.0)
        p_play_60 = np.minimum(p_play_60, p_play_any)

        exp_goals = np.maximum(_to_arr("expected_goals", 0.0), 0.0)
        exp_assists = np.maximum(_to_arr("expected_assists", 0.0), 0.0)
        cs_prob = np.clip(_to_arr("clean_sheet_prob", 0.0), 0.0, 1.0)
        exp_gc = np.maximum(_to_arr("expected_goals_conceded", 0.0), 0.0)
        exp_saves = np.maximum(_to_arr("expected_saves", 0.0), 0.0)
        exp_yellow = np.maximum(_to_arr("expected_yellow_cards", 0.0), 0.0)
        exp_red = np.maximum(_to_arr("expected_red_cards", 0.0), 0.0)
        exp_bonus = np.clip(_to_arr("expected_bonus", 0.0), 0.0, 3.0)

        exp_minutes = (p_play_any - p_play_60) * 30.0 + p_play_60 * 85.0
        if "expected_minutes" in events:
            exp_minutes = np.maximum(_to_arr("expected_minutes", exp_minutes), 0.0)

        # 2. Position masks
        if positions is not None:
            is_gkp, is_def, is_mid, is_fwd = cls._extract_position_flags(positions, n_samples)
        else:
            is_gkp, is_def, is_mid, is_fwd = cls._extract_position_flags(events, n_samples)

        is_gkp = is_gkp.astype(float)
        is_def = is_def.astype(float)
        is_mid = is_mid.astype(float)
        is_fwd = is_fwd.astype(float)

        # Playing intensity conditioning: full intensity if starting (>=60m), scaled (30/85) if sub, 0 if benched
        play_intensity = p_play_60 * 1.0 + np.maximum(p_play_any - p_play_60, 0.0) * (30.0 / 85.0)

        # 3. Component Calculations
        app_pts = p_play_any * 1.0 + p_play_60 * 1.0

        goal_mult = 6.0 * is_gkp + 6.0 * is_def + 5.0 * is_mid + 4.0 * is_fwd
        goal_pts = exp_goals * play_intensity * goal_mult

        assist_pts = exp_assists * play_intensity * 3.0

        cs_mult = 4.0 * is_gkp + 4.0 * is_def + 1.0 * is_mid
        cs_pts = cs_prob * p_play_60 * cs_mult

        gc_mult = 1.0 * is_gkp + 1.0 * is_def
        gc_pts = -0.5 * exp_gc * p_play_60 * gc_mult

        save_pts = (exp_saves / 3.0) * p_play_60 * is_gkp

        card_pts = (-1.0 * exp_yellow - 3.0 * exp_red) * play_intensity

        bonus_pts = exp_bonus * play_intensity

        total_pts = (
            app_pts
            + goal_pts
            + assist_pts
            + cs_pts
            + gc_pts
            + save_pts
            + card_pts
            + bonus_pts
        )

        out = pd.DataFrame(
            {
                "predicted_p_play_any": p_play_any,
                "predicted_p_play_60": p_play_60,
                "predicted_expected_minutes": exp_minutes,
                "predicted_goals": exp_goals,
                "predicted_assists": exp_assists,
                "predicted_clean_sheet_prob": cs_prob,
                "predicted_goals_conceded": exp_gc,
                "predicted_saves": exp_saves,
                "predicted_yellow_cards": exp_yellow,
                "predicted_red_cards": exp_red,
                "predicted_bonus": exp_bonus,
                "predicted_appearance_points": app_pts,
                "predicted_goal_points": goal_pts,
                "predicted_assist_points": assist_pts,
                "predicted_clean_sheet_points": cs_pts,
                "predicted_goals_conceded_points": gc_pts,
                "predicted_save_points": save_pts,
                "predicted_card_points": card_pts,
                "predicted_bonus_points": bonus_pts,
                "predicted_total_points": total_pts,
            }
        )

        return out

    @classmethod
    def calculate_distribution(
        cls,
        events: dict[str, np.ndarray | list[float] | float],
        positions: pd.DataFrame | dict[str, Any] | np.ndarray | None = None,
        n_simulations: int = 2000,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """Vectorized simulation of outcome distributions from event models.

        Args:
            events: Predicted event expectations and probabilities.
            positions: Position metadata/indicators.
            n_simulations: Number of Monte Carlo draws per player (default 2000).
            random_state: Seed for reproducible simulation.

        Returns:
            pd.DataFrame with full points breakdown, distribution percentiles
            (floor, p50, p75, p85, p90, p95, ceiling, upside), and captaincy_score.
        """
        breakdown_df = cls.calculate_breakdown(events, positions)
        n_samples = len(breakdown_df)

        rng = np.random.default_rng(random_state)
        S = n_simulations

        # Extract arrays
        p_play_any = breakdown_df["predicted_p_play_any"].to_numpy()
        p_play_60 = breakdown_df["predicted_p_play_60"].to_numpy()
        exp_goals = breakdown_df["predicted_goals"].to_numpy()
        exp_assists = breakdown_df["predicted_assists"].to_numpy()
        cs_prob = breakdown_df["predicted_clean_sheet_prob"].to_numpy()
        exp_gc = breakdown_df["predicted_goals_conceded"].to_numpy()
        exp_saves = breakdown_df["predicted_saves"].to_numpy()
        exp_yellow = breakdown_df["predicted_yellow_cards"].to_numpy()
        exp_red = breakdown_df["predicted_red_cards"].to_numpy()
        exp_bonus = breakdown_df["predicted_bonus"].to_numpy()

        if positions is not None:
            is_gkp, is_def, is_mid, is_fwd = cls._extract_position_flags(positions, n_samples)
        else:
            is_gkp, is_def, is_mid, is_fwd = cls._extract_position_flags(events, n_samples)

        is_gkp = np.atleast_1d(is_gkp).astype(float)
        is_def = np.atleast_1d(is_def).astype(float)
        is_mid = np.atleast_1d(is_mid).astype(float)
        is_fwd = np.atleast_1d(is_fwd).astype(float)

        # 1. Playing time states
        # u ~ Uniform(0, 1) shape (N, S)
        u = rng.random(size=(n_samples, S))
        is_starter = u < p_play_60[:, None]
        is_sub = (u >= p_play_60[:, None]) & (u < p_play_any[:, None])
        is_active = is_starter | is_sub

        # Appearance points
        app_sim = np.where(is_starter, 2.0, np.where(is_sub, 1.0, 0.0))

        # Goals & Assists conditioning on playing time (starter gets full intensity, sub gets ~30/85)
        scale_intensity = np.where(is_starter, 1.0, np.where(is_sub, 30.0 / 85.0, 0.0))

        lam_goals = exp_goals[:, None] * scale_intensity
        goals_sim = rng.poisson(lam_goals)
        goal_mult = 6.0 * is_gkp + 6.0 * is_def + 5.0 * is_mid + 4.0 * is_fwd
        goal_sim_pts = goals_sim * goal_mult[:, None]

        lam_assists = exp_assists[:, None] * scale_intensity
        assists_sim = rng.poisson(lam_assists)
        assist_sim_pts = assists_sim * 3.0

        # Clean Sheet (requires starter >= 60 mins)
        cs_u = rng.random(size=(n_samples, S))
        cs_sim = (cs_u < cs_prob[:, None]) & is_starter
        cs_mult = 4.0 * is_gkp + 4.0 * is_def + 1.0 * is_mid
        cs_sim_pts = cs_sim.astype(float) * cs_mult[:, None]

        # Goals Conceded (-0.5 per GC for GKP/DEF starters)
        lam_gc = exp_gc[:, None] * is_starter.astype(float)
        gc_sim = rng.poisson(lam_gc)
        gc_mult = 1.0 * is_gkp + 1.0 * is_def
        gc_sim_pts = -0.5 * gc_sim * gc_mult[:, None]

        # Saves (+1 per 3 saves for GKP starters)
        lam_saves = exp_saves[:, None] * is_starter.astype(float)
        saves_sim = rng.poisson(lam_saves)
        saves_sim_pts = (saves_sim / 3.0) * is_gkp[:, None]

        # Cards
        y_u = rng.random(size=(n_samples, S))
        r_u = rng.random(size=(n_samples, S))
        yellow_sim = (y_u < exp_yellow[:, None]) & is_active
        red_sim = (r_u < exp_red[:, None]) & is_active
        card_sim_pts = -1.0 * yellow_sim.astype(float) - 3.0 * red_sim.astype(float)

        # Bonus
        lam_bonus = exp_bonus[:, None] * scale_intensity
        bonus_sim = np.minimum(rng.poisson(lam_bonus), 3.0)

        # Total points simulated
        sim_total = (
            app_sim
            + goal_sim_pts
            + assist_sim_pts
            + cs_sim_pts
            + gc_sim_pts
            + saves_sim_pts
            + card_sim_pts
            + bonus_sim
        )

        # 2. Extract percentiles across simulations (axis 1)
        p50 = np.percentile(sim_total, 50, axis=1)
        p75 = np.percentile(sim_total, 75, axis=1)
        p85 = np.percentile(sim_total, 85, axis=1)
        p90 = np.percentile(sim_total, 90, axis=1)
        p95 = np.percentile(sim_total, 95, axis=1)
        floor_pts = np.percentile(sim_total, 10, axis=1)
        ceiling_pts = p95

        exp_pts = breakdown_df["predicted_total_points"].to_numpy()
        upside_pts = np.maximum(p85 - exp_pts, 0.0)

        # Captaincy Score: weighted combination of expectation, upside, and start security
        capt_score = 0.40 * exp_pts + 0.35 * p85 + 0.25 * p90 * p_play_60

        # Attach to result
        result_df = breakdown_df.copy()
        result_df["predicted_expected_points"] = exp_pts
        result_df["predicted_floor_points"] = floor_pts
        result_df["predicted_p50_points"] = p50
        result_df["predicted_p75_points"] = p75
        result_df["predicted_p85_points"] = p85
        result_df["predicted_p90_points"] = p90
        result_df["predicted_p95_points"] = p95
        result_df["predicted_ceiling_points"] = ceiling_pts
        result_df["predicted_upside_points"] = upside_pts
        result_df["captaincy_score"] = capt_score

        # Rankings
        result_df["rank_expected"] = (
            result_df["predicted_expected_points"].rank(ascending=False, method="min").astype(int)
        )
        result_df["rank_upside"] = (
            result_df["predicted_p85_points"].rank(ascending=False, method="min").astype(int)
        )
        result_df["rank_captaincy"] = (
            result_df["captaincy_score"].rank(ascending=False, method="min").astype(int)
        )

        return result_df

    @classmethod
    def score_distribution(
        cls,
        events: dict[str, float],
        position: str | int = "MID",
        n_simulations: int = 2000,
        random_state: int = 42,
    ) -> FPLDistributionResult:
        """Convenience method returning a typed distribution result for a single player."""
        pos_str = str(position).upper()
        pos_dict = {
            "is_position_gkp": 1.0 if pos_str in {"GKP", "GK", "1"} else 0.0,
            "is_position_def": 1.0 if pos_str in {"DEF", "2"} else 0.0,
            "is_position_mid": 1.0 if pos_str in {"MID", "3"} else 0.0,
            "is_position_fwd": 1.0 if pos_str in {"FWD", "4"} else 0.0,
        }
        df = cls.calculate_distribution(
            events,
            positions=pos_dict,
            n_simulations=n_simulations,
            random_state=random_state,
        )
        row = df.iloc[0]

        return FPLDistributionResult(
            expected_points=float(row["predicted_expected_points"]),
            floor_points=float(row["predicted_floor_points"]),
            p50_points=float(row["predicted_p50_points"]),
            p75_points=float(row["predicted_p75_points"]),
            p85_points=float(row["predicted_p85_points"]),
            p90_points=float(row["predicted_p90_points"]),
            p95_points=float(row["predicted_p95_points"]),
            ceiling_points=float(row["predicted_ceiling_points"]),
            upside_points=float(row["predicted_upside_points"]),
            captaincy_score=float(row["captaincy_score"]),
        )

    @classmethod
    def explain_single(
        cls,
        events: dict[str, float],
        position: str | int = "MID",
    ) -> FPLPointBreakdown:
        """Convenience method returning a typed breakdown object for a single player."""
        pos_str = str(position).upper()
        pos_dict = {
            "is_position_gkp": 1.0 if pos_str in {"GKP", "GK", "1"} else 0.0,
            "is_position_def": 1.0 if pos_str in {"DEF", "2"} else 0.0,
            "is_position_mid": 1.0 if pos_str in {"MID", "3"} else 0.0,
            "is_position_fwd": 1.0 if pos_str in {"FWD", "4"} else 0.0,
        }
        df = cls.calculate_breakdown(events, pos_dict)
        row = df.iloc[0]

        return FPLPointBreakdown(
            appearance_points=float(row["predicted_appearance_points"]),
            goal_points=float(row["predicted_goal_points"]),
            assist_points=float(row["predicted_assist_points"]),
            clean_sheet_points=float(row["predicted_clean_sheet_points"]),
            goals_conceded_points=float(row["predicted_goals_conceded_points"]),
            save_points=float(row["predicted_save_points"]),
            card_points=float(row["predicted_card_points"]),
            bonus_points=float(row["predicted_bonus_points"]),
            total_points=float(row["predicted_total_points"]),
        )
