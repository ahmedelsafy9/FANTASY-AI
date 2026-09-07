"""Service for next-Gameweek match predictions using the existing Match Model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import poisson

from src.api.schemas import (
    MatchPlayerImpact,
    MatchPrediction,
    MatchPredictionResponse,
)
from src.api.state import AppState
from src.config.logging_config import get_logger
from src.data_collection.services.team_mapping_service import TeamMappingService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.multi_stage.match_model import (
    MATCH_FEATURE_COLS,
    build_match_dataset,
    goals_to_probabilities,
    load_match_model,
)
from src.prediction.next_gameweek import find_latest_completed_gameweek

logger = get_logger(__name__)


class MatchPredictionService:
    """Orchestrates match predictions using the existing trained Match Model."""

    def __init__(self, app_state: AppState) -> None:
        self._state = app_state
        self._match_model: object | None = None
        self._feature_cols: list[str] = list(MATCH_FEATURE_COLS)
        self._team_stats: pd.DataFrame | None = None
        self._team_id_to_name: dict[int, str] = {}
        self._team_name_to_badge: dict[str, str] = {}
        self._fixtures_cache: list[dict[str, Any]] | None = None

        self._initialize()

    def _initialize(self) -> None:
        """Load model and build team stat lookups once."""
        settings = self._state.settings

        # 1. Load trained match model
        model_dir = settings.paths.models_dir / "multi_stage"
        if not (model_dir / "match_model.joblib").exists():
            model_dir = Path("models/multi_stage")

        try:
            model, meta = load_match_model(model_dir)
            self._match_model = model
            if meta and "feature_cols" in meta:
                self._feature_cols = meta["feature_cols"]
            logger.info("MatchPredictionService: loaded model from %s.", model_dir)
        except Exception as exc:
            logger.warning("MatchPredictionService: could not load match model: %s", exc)

        # 2. Build team mapping
        try:
            live_dir = settings.paths.raw_data_dir / "fpl_api"
            bootstrap_path = live_dir / "bootstrap_static.json"
            if bootstrap_path.exists():
                bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
                teams_raw = bootstrap.get("teams", [])
                cache_path = (
                    settings.paths.external_data_dir
                    / settings.fixture_aware.team_mapping_cache_path
                )
                mapping_service = TeamMappingService(cache_path)
                self._team_id_to_name = mapping_service.build_mapping(teams_raw)
                for t in teams_raw:
                    name = t.get("name")
                    code = t.get("code")
                    if name and code:
                        self._team_name_to_badge[name] = (
                            f"https://resources.premierleague.com/premierleague/badges/70/t{code}.png"
                        )
        except Exception as exc:
            logger.warning("MatchPredictionService: team mapping init failed: %s", exc)

        # Supplement badges from player predictions if available
        if hasattr(self._state, "predictions") and not self._state.predictions.empty:
            preds = self._state.predictions
            if "team" in preds.columns and "team_logo_url" in preds.columns:
                badge_map = (
                    preds[["team", "team_logo_url"]]
                    .dropna()
                    .drop_duplicates()
                    .set_index("team")["team_logo_url"]
                    .to_dict()
                )
                self._team_name_to_badge.update(badge_map)

        # 3. Build team historical stats for match features
        try:
            if hasattr(self._state, "engineered_data") and not self._state.engineered_data.empty:
                match_df = build_match_dataset(self._state.engineered_data)
                if not match_df.empty:
                    self._team_stats = (
                        match_df.sort_values(["season", "GW"])
                        .groupby("team")
                        .tail(1)
                        .set_index("team")
                    )
        except Exception as exc:
            logger.warning("MatchPredictionService: team stats calculation failed: %s", exc)

    def _get_fixtures(self) -> list[dict[str, Any]]:
        """Load all fixtures (live or cached)."""
        if self._fixtures_cache is not None:
            return self._fixtures_cache

        # Try live FPL API
        try:
            settings = self._state.settings
            fpl_source = FPLApiDataSource(
                base_url=settings.data_sources.fpl_api_base_url,
                events_path=settings.automation.fpl_api_events_path,
                live_event_path_template=settings.automation.fpl_api_live_event_path_template,
                fixtures_path=settings.automation.fpl_api_fixtures_path,
                timeout_seconds=settings.data_sources.request_timeout_seconds,
                max_retries=settings.data_sources.request_max_retries,
            )
            fixtures = fpl_source.get_fixtures(future_only=False)
            if fixtures:
                self._fixtures_cache = fixtures
                return fixtures
        except Exception as exc:
            logger.debug("Live fixture fetch failed, checking local cache: %s", exc)

        # Fallback to local cached fixtures.json
        for path in [
            self._state.settings.paths.raw_data_dir / "fpl_api" / "fixtures.json",
            Path("data/raw/fpl_api/fixtures.json"),
        ]:
            if path.exists():
                try:
                    fixtures = json.loads(path.read_text(encoding="utf-8"))
                    self._fixtures_cache = fixtures
                    return fixtures
                except Exception:
                    pass

        return []

    def predict_next_gameweek(self) -> MatchPredictionResponse:
        """Predict match outcomes for all fixtures in the next Gameweek."""
        season = self._state.season or "2026-27"
        latest_completed_gw = self._state.latest_completed_gameweek

        if latest_completed_gw is None:
            if hasattr(self._state, "engineered_data") and not self._state.engineered_data.empty:
                s_data = (
                    self._state.engineered_data[
                        self._state.engineered_data["season"] == season
                    ]
                    if "season" in self._state.engineered_data.columns
                    else self._state.engineered_data
                )
                latest_completed_gw = find_latest_completed_gameweek(s_data)
            else:
                latest_completed_gw = 1

        predicted_gw = self._state.predicted_gameweek
        if predicted_gw is None:
            max_gw = getattr(self._state.settings.prediction, "max_valid_gameweek", 38)
            predicted_gw = min(int(latest_completed_gw) + 1, max_gw)

        all_fixtures = self._get_fixtures()
        target_fixtures = [
            f
            for f in all_fixtures
            if f.get("event") == predicted_gw
        ]

        if not target_fixtures:
            # Check for unplayed fixtures if event filter returned none
            unplayed = [f for f in all_fixtures if not f.get("finished", False)]
            if unplayed:
                next_ev = unplayed[0].get("event")
                if next_ev is not None:
                    predicted_gw = int(next_ev)
                    target_fixtures = [f for f in all_fixtures if f.get("event") == predicted_gw]

        # Sort fixtures by kickoff time
        target_fixtures.sort(key=lambda f: f.get("kickoff_time") or "")

        match_predictions: list[MatchPrediction] = []

        for f in target_fixtures:
            pred = self._predict_single_fixture(f, predicted_gw)
            match_predictions.append(pred)

        generated_at = self._state.generated_at or datetime.now(timezone.utc).isoformat()

        return MatchPredictionResponse(
            season=season,
            latest_completed_gameweek=latest_completed_gw,
            predicted_gameweek=predicted_gw,
            generated_at=generated_at,
            count=len(match_predictions),
            predictions=match_predictions,
        )

    def _predict_single_fixture(
        self,
        fixture: dict[str, Any],
        gameweek: int,
    ) -> MatchPrediction:
        """Run existing match model inference on a single fixture."""
        home_id = fixture.get("team_h")
        away_id = fixture.get("team_a")
        fixture_id = fixture.get("id") or fixture.get("code") or 0

        home_team = self._team_id_to_name.get(home_id, f"Team {home_id}")
        away_team = self._team_id_to_name.get(away_id, f"Team {away_id}")

        home_badge = self._team_name_to_badge.get(home_team)
        away_badge = self._team_name_to_badge.get(away_team)

        # Retrieve latest team stats from historical data
        home_stats = (
            self._team_stats.loc[home_team]
            if self._team_stats is not None and home_team in self._team_stats.index
            else pd.Series()
        )
        away_stats = (
            self._team_stats.loc[away_team]
            if self._team_stats is not None and away_team in self._team_stats.index
            else pd.Series()
        )

        # Baseline defaults if team stats absent
        default_attack = 1.3
        default_defence = 1.3
        default_form = 1.1

        # 1. Build features for Home Team (is_home = 1)
        row_h = {
            "team_attack_str": home_stats.get("team_attack_str", default_attack),
            "team_defence_str": home_stats.get("team_defence_str", default_defence),
            "opp_attack_str": away_stats.get("team_attack_str", default_attack),
            "opp_defence_str": away_stats.get("team_defence_str", default_defence),
            "team_form_3": home_stats.get("team_form_3", default_form),
            "team_form_5": home_stats.get("team_form_5", default_form),
            "team_form_10": home_stats.get("team_form_10", default_form),
            "opp_form_3": away_stats.get("team_form_3", default_form),
            "opp_form_5": away_stats.get("team_form_5", default_form),
            "opp_form_10": away_stats.get("team_form_10", default_form),
            "is_home": 1,
            "team_is_promoted": home_stats.get("team_is_promoted", 0),
            "opp_is_promoted": away_stats.get("team_is_promoted", 0),
            "team_goals_for_expanding": home_stats.get("team_goals_for_expanding", default_attack),
            "team_goals_against_expanding": home_stats.get("team_goals_against_expanding", default_defence),
            "opp_goals_for_expanding": away_stats.get("team_goals_for_expanding", default_attack),
            "opp_goals_against_expanding": away_stats.get("team_goals_against_expanding", default_defence),
        }

        # 2. Build features for Away Team (is_home = 0)
        row_a = {
            "team_attack_str": away_stats.get("team_attack_str", default_attack),
            "team_defence_str": away_stats.get("team_defence_str", default_defence),
            "opp_attack_str": home_stats.get("team_attack_str", default_attack),
            "opp_defence_str": home_stats.get("team_defence_str", default_defence),
            "team_form_3": away_stats.get("team_form_3", default_form),
            "team_form_5": away_stats.get("team_form_5", default_form),
            "team_form_10": away_stats.get("team_form_10", default_form),
            "opp_form_3": home_stats.get("team_form_3", default_form),
            "opp_form_5": home_stats.get("team_form_5", default_form),
            "opp_form_10": home_stats.get("team_form_10", default_form),
            "is_home": 0,
            "team_is_promoted": away_stats.get("team_is_promoted", 0),
            "opp_is_promoted": home_stats.get("team_is_promoted", 0),
            "team_goals_for_expanding": away_stats.get("team_goals_for_expanding", default_attack),
            "team_goals_against_expanding": away_stats.get("team_goals_against_expanding", default_defence),
            "opp_goals_for_expanding": home_stats.get("team_goals_for_expanding", default_attack),
            "opp_goals_against_expanding": home_stats.get("team_goals_against_expanding", default_defence),
        }

        # Predict expected goals with existing match model
        if self._match_model is not None:
            X_h = pd.DataFrame([row_h])[self._feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            X_a = pd.DataFrame([row_a])[self._feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            pred_home_goals = float(self._match_model.predict(X_h)[0])
            pred_away_goals = float(self._match_model.predict(X_a)[0])
        else:
            # Conservative fallback if model artifact missing
            pred_home_goals = 1.4
            pred_away_goals = 1.1

        pred_home_goals = max(0.1, pred_home_goals)
        pred_away_goals = max(0.1, pred_away_goals)

        # 3. Calculate Poisson probability distribution
        probs = goals_to_probabilities(np.array([pred_home_goals]), np.array([pred_away_goals]))
        hw_prob = float(probs["win_prob"][0])
        d_prob = float(probs["draw_prob"][0])
        aw_prob = float(probs["loss_prob"][0])

        # 4. Joint bivariate Poisson matrix (up to 8 goals)
        joint_matrix = np.zeros((9, 9))
        for h in range(9):
            for a in range(9):
                joint_matrix[h, a] = poisson.pmf(h, pred_home_goals) * poisson.pmf(a, pred_away_goals)
        total_mass = joint_matrix.sum()
        if total_mass > 0:
            joint_matrix /= total_mass

        over_2_5 = float(sum(joint_matrix[h, a] for h in range(9) for a in range(9) if h + a > 2))
        under_2_5 = 1.0 - over_2_5
        btts = float(sum(joint_matrix[h, a] for h in range(1, 9) for a in range(1, 9)))
        home_clean_sheet = float(joint_matrix[:, 0].sum())
        away_clean_sheet = float(joint_matrix[0, :].sum())

        # Most likely scoreline
        best_h, best_a = np.unravel_index(np.argmax(joint_matrix), joint_matrix.shape)
        predicted_scoreline = f"{int(best_h)}-{int(best_a)}"

        # Predicted result
        if hw_prob > max(d_prob, aw_prob):
            predicted_result = "HOME_WIN"
        elif aw_prob > max(d_prob, hw_prob):
            predicted_result = "AWAY_WIN"
        else:
            predicted_result = "DRAW"

        # Confidence
        confidence = float(max(hw_prob, d_prob, aw_prob))
        if confidence >= 0.55:
            confidence_level = "HIGH"
        elif confidence >= 0.42:
            confidence_level = "MODERATE"
        else:
            confidence_level = "LOW"

        # Prediction drivers from real features
        prediction_drivers = {
            "home_attack_strength": round(float(row_h["team_attack_str"]), 2),
            "home_defence_strength": round(float(row_h["team_defence_str"]), 2),
            "away_attack_strength": round(float(row_a["team_attack_str"]), 2),
            "away_defence_strength": round(float(row_a["team_defence_str"]), 2),
            "home_form_index": round(float(row_h["team_form_3"]), 2),
            "away_form_index": round(float(row_a["team_form_3"]), 2),
            "home_advantage_active": True,
        }

        # 5. Connect to Phase 3: Fantasy Impact (top players from existing player predictions)
        top_home_players, top_away_players, captain_pick, best_attacker, best_defender = (
            self._resolve_fantasy_impact(home_team, away_team)
        )

        return MatchPrediction(
            fixture_id=int(fixture_id),
            code=fixture.get("code"),
            gameweek=gameweek,
            kickoff_time=fixture.get("kickoff_time"),
            home_team=home_team,
            away_team=away_team,
            home_team_id=home_id,
            away_team_id=away_id,
            home_team_logo_url=home_badge,
            away_team_logo_url=away_badge,
            home_win_probability=round(hw_prob, 3),
            draw_probability=round(d_prob, 3),
            away_win_probability=round(aw_prob, 3),
            predicted_result=predicted_result,
            predicted_home_goals=round(pred_home_goals, 2),
            predicted_away_goals=round(pred_away_goals, 2),
            predicted_scoreline=predicted_scoreline,
            confidence=round(confidence, 3),
            confidence_level=confidence_level,
            over_2_5_probability=round(over_2_5, 3),
            under_2_5_probability=round(under_2_5, 3),
            btts_probability=round(btts, 3),
            home_clean_sheet_probability=round(home_clean_sheet, 3),
            away_clean_sheet_probability=round(away_clean_sheet, 3),
            prediction_drivers=prediction_drivers,
            top_home_players=top_home_players,
            top_away_players=top_away_players,
            best_captain_candidate=captain_pick,
            best_attacking_option=best_attacker,
            best_defensive_option=best_defender,
        )

    def _resolve_fantasy_impact(
        self,
        home_team: str,
        away_team: str,
    ) -> tuple[
        list[MatchPlayerImpact],
        list[MatchPlayerImpact],
        MatchPlayerImpact | None,
        MatchPlayerImpact | None,
        MatchPlayerImpact | None,
    ]:
        """Query top players from existing Feedback 5 player prediction engine."""
        if not hasattr(self._state, "predictions") or self._state.predictions.empty:
            return [], [], None, None, None

        preds = self._state.predictions

        def _to_impact(p: pd.Series) -> MatchPlayerImpact:
            name = p.get("name") or p.get("web_name") or "Player"
            pos = p.get("position")
            if pos == "GKP":
                pos = "GK"
            val = p.get("value")
            if val is None and "now_cost" in p:
                val = float(p["now_cost"]) / 10.0

            # Safe float conversion
            def _flt(k: str) -> float | None:
                v = p.get(k)
                return float(v) if pd.notna(v) and v is not None else None

            # Expected minutes from prediction signals or historical
            mins = None
            signals = p.get("prediction_signals")
            if isinstance(signals, dict) and "expected_minutes" in signals:
                mins = signals["expected_minutes"].get("minutes")
            if mins is None:
                mins = _flt("minutes_avg_last_5")

            return MatchPlayerImpact(
                element=int(p["element"]) if "element" in p and pd.notna(p["element"]) else None,
                name=str(name),
                position=str(pos) if pos else None,
                team=str(p.get("team") or ""),
                expected_points=_flt("predicted_expected_points") or _flt("predicted_total_points"),
                fpl_rank_score=_flt("predicted_fpl_rank_score"),
                prob_high_score_6=_flt("prob_high_score_6"),
                expected_minutes=float(mins) if mins is not None else None,
                photo_url=p.get("photo_url"),
                value=float(val) if val is not None else None,
            )

        home_players_df = preds[preds["team"] == home_team] if "team" in preds.columns else pd.DataFrame()
        away_players_df = preds[preds["team"] == away_team] if "team" in preds.columns else pd.DataFrame()

        sort_col = (
            "predicted_fpl_rank_score"
            if "predicted_fpl_rank_score" in preds.columns
            else "predicted_expected_points"
            if "predicted_expected_points" in preds.columns
            else "predicted_total_points"
        )

        top_home: list[MatchPlayerImpact] = []
        if not home_players_df.empty and sort_col in home_players_df.columns:
            top_h_df = home_players_df.sort_values(by=sort_col, ascending=False).head(3)
            top_home = [_to_impact(row) for _, row in top_h_df.iterrows()]

        top_away: list[MatchPlayerImpact] = []
        if not away_players_df.empty and sort_col in away_players_df.columns:
            top_a_df = away_players_df.sort_values(by=sort_col, ascending=False).head(3)
            top_away = [_to_impact(row) for _, row in top_a_df.iterrows()]

        # Best captain, attacker, defender across this fixture
        all_fixture_players = pd.concat([home_players_df, away_players_df]) if not home_players_df.empty or not away_players_df.empty else pd.DataFrame()

        captain_pick: MatchPlayerImpact | None = None
        best_attacker: MatchPlayerImpact | None = None
        best_defender: MatchPlayerImpact | None = None

        if not all_fixture_players.empty and sort_col in all_fixture_players.columns:
            sorted_all = all_fixture_players.sort_values(by=sort_col, ascending=False)
            if not sorted_all.empty:
                captain_pick = _to_impact(sorted_all.iloc[0])

            if "position" in sorted_all.columns:
                attackers = sorted_all[sorted_all["position"].isin(["FWD", "MID"])]
                if not attackers.empty:
                    best_attacker = _to_impact(attackers.iloc[0])

                defenders = sorted_all[sorted_all["position"].isin(["DEF", "GKP", "GK"])]
                if not defenders.empty:
                    best_defender = _to_impact(defenders.iloc[0])

        return top_home, top_away, captain_pick, best_attacker, best_defender
