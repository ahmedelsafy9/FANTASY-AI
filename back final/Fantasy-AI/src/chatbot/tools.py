"""Chatbot tool definitions and executors.

Each tool is a thin wrapper around existing Fantasy AI services and
the ``AppState`` predictions DataFrame.  No new data sources are
introduced — every tool returns data already computed at startup.

Tool functions return plain dicts/lists that are JSON-serialisable.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.api.state import AppState
from src.chatbot.player_resolver import PlayerResolver, _row_to_safe_dict
from src.config.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------
# Key columns to include in player summaries (avoid dumping the
# entire 200+ column DataFrame into the LLM context).
# ---------------------------------------------------------------

_PLAYER_SUMMARY_COLUMNS = [
    "element", "web_name", "name", "first_name", "second_name",
    "team", "position", "value", "now_cost",
    # Predictions
    "predicted_expected_points", "predicted_expected_points_raw",
    "predicted_total_points", "predicted_fpl_rank_score", "score_d",
    "captaincy_score", "predicted_p85_points", "predicted_p90_points",
    "availability_adjustment_factor",
    # Availability
    "availability_status", "injury_flag", "doubt_flag",
    "suspension_flag", "ruled_out_flag", "expected_to_start",
    "availability_expected_minutes", "rotation_risk",
    "team_news", "team_news_flag", "chance_of_playing_next_round",
    # FPL stats
    "selected_by_percent", "ep_next", "fpl_form",
    "fpl_points_per_game", "fpl_total_points_season",
    "fpl_expected_goals", "fpl_expected_assists",
    "fpl_expected_goal_involvements",
    # Engineered features
    "total_points_avg_last_3", "total_points_avg_last_5",
    "minutes_avg_last_3", "minutes_avg_last_5",
    "xG_avg_last_3", "xA_avg_last_3",
    "form_index", "fixture_difficulty",
    # Fixture
    "opponent_team", "is_home", "fixture_source",
    "photo_url", "team_logo_url",
]


def _summarise_player(row: pd.Series) -> dict[str, Any]:
    """Extract key columns from a player row for LLM consumption."""
    d = _row_to_safe_dict(row)
    result = {}
    for col in _PLAYER_SUMMARY_COLUMNS:
        if col in d:
            result[col] = d[col]
    # Always include upcoming fixtures if present
    if "upcoming_fixtures" in d:
        result["upcoming_fixtures"] = d["upcoming_fixtures"]
    return result


def _find_prediction_column(predictions: pd.DataFrame) -> str:
    """Find the primary prediction column in the DataFrame."""
    for col in (
        "score_d", "predicted_fpl_rank_score",
        "predicted_expected_points", "predicted_total_points",
    ):
        if col in predictions.columns:
            return col
    return predictions.columns[0]


class ChatbotTools:
    """Collection of tool executors backed by AppState.

    Each public method corresponds to a tool the LLM can call.
    """

    def __init__(self, app_state: AppState) -> None:
        self._state = app_state
        self._predictions = app_state.predictions
        self._resolver = PlayerResolver(self._predictions)
        self._pred_col = _find_prediction_column(self._predictions)

    # ---------------------------------------------------------------
    # Tool: search_player_by_name
    # ---------------------------------------------------------------

    def search_player_by_name(self, query: str) -> list[dict[str, Any]]:
        """Search for a player by name (supports Arabic, partial, fuzzy).

        Args:
            query: Player name or partial name in any language.

        Returns:
            List of matching player summaries (up to 5).
        """
        matches = self._resolver.resolve(query, max_results=5)
        return matches

    # ---------------------------------------------------------------
    # Tool: get_player_info
    # ---------------------------------------------------------------

    def get_player_info(self, player_name: str) -> dict[str, Any]:
        """Get full information for a player (stats, prediction, availability, fixtures).

        Args:
            player_name: Player name or partial name.

        Returns:
            Player summary dict, or error message.
        """
        matches = self._resolver.resolve(player_name, max_results=1)
        if not matches:
            return {"error": f"No player found matching '{player_name}'."}

        pid = matches[0].get("element")
        if pid is not None:
            row = self._predictions[self._predictions["element"] == pid]
            if not row.empty:
                return _summarise_player(row.iloc[0])
        return matches[0]

    # ---------------------------------------------------------------
    # Tool: get_player_availability
    # ---------------------------------------------------------------

    def get_player_availability(self, player_name: str) -> dict[str, Any]:
        """Get availability and injury information for a player.

        Args:
            player_name: Player name or partial name.

        Returns:
            Availability-focused summary.
        """
        info = self.get_player_info(player_name)
        if "error" in info:
            return info

        avail_keys = [
            "element", "web_name", "team", "position",
            "availability_status", "injury_flag", "doubt_flag",
            "suspension_flag", "ruled_out_flag", "expected_to_start",
            "availability_expected_minutes", "rotation_risk",
            "team_news", "team_news_flag", "chance_of_playing_next_round",
            "chance_of_playing_this_round", "availability_timestamp",
            "predicted_expected_points", "predicted_expected_points_raw",
            "availability_adjustment_factor",
        ]
        return {k: info.get(k) for k in avail_keys if k in info}

    # ---------------------------------------------------------------
    # Tool: get_gameweek_predictions
    # ---------------------------------------------------------------

    def get_gameweek_predictions(
        self, limit: int = 15, position: str | None = None,
    ) -> dict[str, Any]:
        """Get top predicted players for the upcoming gameweek.

        Args:
            limit: Number of players to return (default 15).
            position: Filter by position (GKP/DEF/MID/FWD), or None for all.

        Returns:
            Dict with gameweek info and list of player summaries.
        """
        df = self._predictions.copy()

        # Filter out unavailable/injured players with zero prediction
        df = df[df.get("availability_status", pd.Series(["fit"] * len(df))).isin(
            ["fit", "rotation_risk", "doubtful", "minor_injury"]
        ) | ~df["availability_status"].notna()]

        if position:
            pos = position.upper()
            if "position" in df.columns:
                df = df[df["position"].str.upper() == pos]

        df = df.sort_values(by=self._pred_col, ascending=False)
        top = df.head(min(limit, 50))

        players = [_summarise_player(row) for _, row in top.iterrows()]

        return {
            "predicted_gameweek": self._state.predicted_gameweek,
            "season": self._state.season,
            "scoring_model": self._state.scoring_model,
            "count": len(players),
            "players": players,
        }

    # ---------------------------------------------------------------
    # Tool: compare_players
    # ---------------------------------------------------------------

    def compare_players(
        self, player1_name: str, player2_name: str,
    ) -> dict[str, Any]:
        """Compare two players side-by-side.

        Args:
            player1_name: First player name.
            player2_name: Second player name.

        Returns:
            Side-by-side comparison with both players' data.
        """
        p1 = self.get_player_info(player1_name)
        p2 = self.get_player_info(player2_name)

        if "error" in p1 or "error" in p2:
            return {"player1": p1, "player2": p2}

        return {
            "player1": p1,
            "player2": p2,
            "comparison_note": (
                "Compare predicted_expected_points (availability-adjusted), "
                "availability_status, expected_to_start, fixture_difficulty, "
                "and upcoming_fixtures to make your recommendation."
            ),
        }

    # ---------------------------------------------------------------
    # Tool: get_captain_recommendation
    # ---------------------------------------------------------------

    def get_captain_recommendation(self) -> dict[str, Any]:
        """Get captain pick recommendation based on adjusted predictions.

        Returns:
            Top captain candidates with reasoning factors.
        """
        df = self._predictions.copy()
        if df.empty:
            return {
                "predicted_gameweek": self._state.predicted_gameweek,
                "candidates": [],
                "error": "No prediction data available to recommend captains.",
            }

        # Filter to likely starters with good availability
        fit_mask = (
            df["availability_status"].isin(["fit", "rotation_risk"])
            if "availability_status" in df.columns
            else pd.Series([True] * len(df))
        )

        pool = df[fit_mask]
        if pool.empty:
            pool = df

        sort_col = (
            "captaincy_score"
            if "captaincy_score" in pool.columns and pool["captaincy_score"].notna().any()
            else self._pred_col
        )

        pool_sorted = pool.sort_values(by=sort_col, ascending=False)
        top_5 = pool_sorted.head(5)
        candidates = [_summarise_player(row) for _, row in top_5.iterrows()]

        gw = self._state.predicted_gameweek
        if gw is None and "predicted_for_gw" in df.columns and not df.empty:
            try:
                gw = int(df["predicted_for_gw"].iloc[0])
            except (ValueError, TypeError):
                pass

        return {
            "predicted_gameweek": gw,
            "candidates": candidates,
            "recommendation_note": (
                "The top candidate by adjusted expected points is the safest "
                "captain choice. Consider fixture difficulty and availability. "
                "A doubtful player should NOT be captained even if raw "
                "prediction is high."
            ),
        }

    # ---------------------------------------------------------------
    # Tool: get_current_gameweek
    # ---------------------------------------------------------------

    def get_current_gameweek(self) -> dict[str, Any]:
        """Get current gameweek information.

        Returns:
            Season, completed GW, predicted GW, generation timestamp.
        """
        return {
            "season": self._state.season,
            "latest_completed_gameweek": self._state.latest_completed_gameweek,
            "predicted_gameweek": self._state.predicted_gameweek,
            "generated_at": self._state.generated_at,
            "player_count": len(self._predictions),
            "scoring_model": self._state.scoring_model,
        }

    # ---------------------------------------------------------------
    # Tool: get_team_players
    # ---------------------------------------------------------------

    def get_team_players(self, team_name: str) -> dict[str, Any]:
        """Get all players for a specific team.

        Args:
            team_name: Team name (e.g. "Arsenal", "Liverpool").

        Returns:
            List of players for that team.
        """
        if "team" not in self._predictions.columns:
            return {"error": "Team column not available."}

        # Fuzzy team match
        norm_query = team_name.lower().strip()
        mask = self._predictions["team"].str.lower().str.contains(
            norm_query, na=False
        )
        team_df = self._predictions[mask].sort_values(
            by=self._pred_col, ascending=False
        )

        if team_df.empty:
            return {"error": f"No team found matching '{team_name}'."}

        players = [_summarise_player(row) for _, row in team_df.iterrows()]
        return {
            "team": team_df.iloc[0].get("team", team_name),
            "count": len(players),
            "players": players,
        }

    # ---------------------------------------------------------------
    # Tool: get_fixture_info
    # ---------------------------------------------------------------

    def get_fixture_info(self, team_name: str) -> dict[str, Any]:
        """Get upcoming fixture information for a team.

        Args:
            team_name: Team name.

        Returns:
            Fixture difficulty, opponent, home/away, and upcoming fixtures.
        """
        team_data = self.get_team_players(team_name)
        if "error" in team_data:
            return team_data

        players = team_data.get("players", [])
        if not players:
            return {"error": f"No fixture data for '{team_name}'."}

        sample = players[0]
        return {
            "team": team_data.get("team"),
            "opponent_team": sample.get("opponent_team"),
            "is_home": sample.get("is_home"),
            "fixture_difficulty": sample.get("fixture_difficulty"),
            "fixture_source": sample.get("fixture_source"),
            "upcoming_fixtures": sample.get("upcoming_fixtures", []),
        }

    # ---------------------------------------------------------------
    # Tool: get_top_by_position
    # ---------------------------------------------------------------

    def get_top_by_position(
        self, position: str, limit: int = 10,
    ) -> dict[str, Any]:
        """Get top predicted players for a specific position.

        Args:
            position: One of GKP, DEF, MID, FWD.
            limit: Number of players to return.

        Returns:
            List of top players at that position.
        """
        return self.get_gameweek_predictions(limit=limit, position=position)

    # ---------------------------------------------------------------
    # Tool: get_differential_picks
    # ---------------------------------------------------------------

    def get_differential_picks(self, limit: int = 10) -> dict[str, Any]:
        """Get low-ownership, high-upside differential picks.

        Args:
            limit: Number of differentials to return.

        Returns:
            List of differential players.
        """
        diff_df = self._state.differential_predictions
        if diff_df is not None and not diff_df.empty:
            top = diff_df.head(limit)
            return {
                "count": len(top),
                "players": [_row_to_safe_dict(row) for _, row in top.iterrows()],
            }

        # Fallback: synthesise from main predictions
        df = self._predictions.copy()
        if "selected_by_percent" in df.columns:
            df = df[
                pd.to_numeric(df["selected_by_percent"], errors="coerce") < 10.0
            ]
        df = df.sort_values(by=self._pred_col, ascending=False)
        top = df.head(limit)

        return {
            "count": len(top),
            "source": "synthesised_from_main_predictions",
            "players": [_summarise_player(row) for _, row in top.iterrows()],
        }

    # ---------------------------------------------------------------
    # Tool: get_injured_doubtful_players
    # ---------------------------------------------------------------

    def get_injured_doubtful_players(self) -> dict[str, Any]:
        """Get all players currently injured, doubtful, or suspended.

        Returns:
            List of flagged players with their availability details.
        """
        if "availability_status" not in self._predictions.columns:
            return {"error": "Availability data not available."}

        flagged = self._predictions[
            self._predictions["availability_status"].isin([
                "doubtful", "minor_injury", "major_injury",
                "suspended", "ruled_out", "unavailable",
                "rotation_risk",
            ])
        ].sort_values(by="availability_status")

        avail_cols = [
            "element", "web_name", "team", "position",
            "availability_status", "team_news",
            "chance_of_playing_next_round", "expected_to_start",
            "availability_expected_minutes",
            "predicted_expected_points", "predicted_expected_points_raw",
        ]
        available_cols = [c for c in avail_cols if c in flagged.columns]

        players = []
        for _, row in flagged.iterrows():
            players.append({c: _row_to_safe_dict(row).get(c) for c in available_cols})

        return {
            "count": len(players),
            "players": players,
        }


# ---------------------------------------------------------------
# Tool schema definitions (for LLM function calling)
# ---------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_player_by_name",
        "description": "Search for a player by name. Supports English, Arabic, partial names, and nicknames. Use this first when you need to find a player.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Player name or partial name in any language (e.g. 'Palmer', 'صلاح', 'Mo Salah')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_player_info",
        "description": "Get full information for a player including stats, prediction, availability, and fixtures. Use this to answer questions about a specific player.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name or partial name",
                },
            },
            "required": ["player_name"],
        },
    },
    {
        "name": "get_player_availability",
        "description": "Get injury/availability/team news information for a player. Use this when asked about a player's fitness or availability.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name or partial name",
                },
            },
            "required": ["player_name"],
        },
    },
    {
        "name": "get_gameweek_predictions",
        "description": "Get top predicted players for the upcoming gameweek, optionally filtered by position.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (default 15)",
                },
                "position": {
                    "type": "string",
                    "description": "Filter by position: GKP, DEF, MID, or FWD. Leave empty for all positions.",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                },
            },
        },
    },
    {
        "name": "compare_players",
        "description": "Compare two players side-by-side with their stats, predictions, availability, and fixtures.",
        "parameters": {
            "type": "object",
            "properties": {
                "player1_name": {
                    "type": "string",
                    "description": "First player name",
                },
                "player2_name": {
                    "type": "string",
                    "description": "Second player name",
                },
            },
            "required": ["player1_name", "player2_name"],
        },
    },
    {
        "name": "get_captain_recommendation",
        "description": "Get captain pick recommendations for the upcoming gameweek based on availability-adjusted predictions.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_current_gameweek",
        "description": "Get current gameweek information including season, completed GW, and prediction status.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_team_players",
        "description": "Get all players for a specific Premier League team with their predictions.",
        "parameters": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Team name (e.g. 'Arsenal', 'Liverpool', 'Man City')",
                },
            },
            "required": ["team_name"],
        },
    },
    {
        "name": "get_fixture_info",
        "description": "Get upcoming fixture information for a team including difficulty, opponent, and home/away status.",
        "parameters": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Team name",
                },
            },
            "required": ["team_name"],
        },
    },
    {
        "name": "get_top_by_position",
        "description": "Get the top predicted players at a specific position (GKP, DEF, MID, FWD).",
        "parameters": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "description": "Position: GKP, DEF, MID, or FWD",
                    "enum": ["GKP", "DEF", "MID", "FWD"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (default 10)",
                },
            },
            "required": ["position"],
        },
    },
    {
        "name": "get_differential_picks",
        "description": "Get low-ownership, high-upside differential player picks.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of differentials to return (default 10)",
                },
            },
        },
    },
    {
        "name": "get_injured_doubtful_players",
        "description": "Get all players currently injured, doubtful, suspended, or flagged with availability concerns.",
        "parameters": {"type": "object", "properties": {}},
    },
    # ---------------------------------------------------------------
    # New agentic tools (added by agentic system upgrade)
    # ---------------------------------------------------------------
    {
        "name": "get_player_form",
        "description": "Get a player's recent form including average points, minutes, xG, and xA over the last 3 and 5 gameweeks.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name or partial name",
                },
            },
            "required": ["player_name"],
        },
    },
    {
        "name": "get_player_stats",
        "description": "Get detailed statistics for a player including xG, xA, BPS, ICT index, and season totals.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name or partial name",
                },
            },
            "required": ["player_name"],
        },
    },
    {
        "name": "analyze_transfer",
        "description": "Analyze a potential transfer comparing the player being sold with the player being bought. Returns side-by-side data on predictions, form, availability, fixtures, and value.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_out": {
                    "type": "string",
                    "description": "Name of the player being sold/transferred out",
                },
                "player_in": {
                    "type": "string",
                    "description": "Name of the player being bought/transferred in",
                },
            },
            "required": ["player_out", "player_in"],
        },
    },
    {
        "name": "analyze_squad",
        "description": "Analyze a squad of player names to identify strengths, weaknesses, availability risks, and transfer priorities. Pass player names as a comma-separated string.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_names": {
                    "type": "string",
                    "description": "Comma-separated list of player names in the squad (e.g. 'Salah, Palmer, Saka, Haaland')",
                },
            },
            "required": ["player_names"],
        },
    },
]

