"""Concrete tool definitions wrapping existing Fantasy AI services.

Every tool here is a thin adapter around functionality that already
exists in :class:`~src.chatbot.tools.ChatbotTools` or other services.
No new data sources are introduced — tools return data already computed
at startup or available via the existing FPL data layer.

New tools that extend beyond the original 12:
- ``analyze_squad`` — squad-level analysis
- ``analyze_transfer`` — player-in/player-out transfer evaluation
- ``get_player_form`` — recent form metrics
- ``get_player_stats`` — detailed statistical profile
- ``search_players`` — multi-criteria player search
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.agentic.tools.base import BaseTool, ToolParameter
from src.agentic.tools.registry import ToolRegistry
from src.api.state import AppState
from src.chatbot.tools import ChatbotTools, _summarise_player, _find_prediction_column
from src.chatbot.player_resolver import _row_to_safe_dict
from src.config.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------
# Existing tool wrappers (wrapping ChatbotTools)
# ---------------------------------------------------------------


class SearchPlayerTool(BaseTool):
    """Search for a player by name (supports fuzzy, Arabic, partial)."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "search_player_by_name"

    @property
    def description(self) -> str:
        return (
            "Search for a player by name. Supports English, Arabic, partial "
            "names, and nicknames. Use this first when you need to find a player."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Player name or partial name in any language",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.search_player_by_name(kwargs["query"])


class GetPlayerInfoTool(BaseTool):
    """Get full information for a player."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_player_info"

    @property
    def description(self) -> str:
        return (
            "Get full information for a player including stats, prediction, "
            "availability, and fixtures. Use this to answer questions about "
            "a specific player."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player_name",
                type="string",
                description="Player name or partial name",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_player_info(kwargs["player_name"])


class GetPlayerAvailabilityTool(BaseTool):
    """Get availability and injury information for a player."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_player_availability"

    @property
    def description(self) -> str:
        return (
            "Get injury/availability/team news information for a player. "
            "Use this when asked about a player's fitness or availability."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player_name",
                type="string",
                description="Player name or partial name",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_player_availability(kwargs["player_name"])


class GetGameweekPredictionsTool(BaseTool):
    """Get top predicted players for the upcoming gameweek."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_gameweek_predictions"

    @property
    def description(self) -> str:
        return (
            "Get top predicted players for the upcoming gameweek, "
            "optionally filtered by position."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="limit",
                type="integer",
                description="Number of players to return (default 15)",
                required=False,
                default=15,
            ),
            ToolParameter(
                name="position",
                type="string",
                description="Filter by position: GKP, DEF, MID, or FWD",
                required=False,
                enum=["GKP", "DEF", "MID", "FWD"],
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_gameweek_predictions(
            limit=kwargs.get("limit", 15),
            position=kwargs.get("position"),
        )


class ComparePlayersTool(BaseTool):
    """Compare two players side-by-side."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "compare_players"

    @property
    def description(self) -> str:
        return (
            "Compare two players side-by-side with their stats, predictions, "
            "availability, and fixtures."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player1_name",
                type="string",
                description="First player name",
            ),
            ToolParameter(
                name="player2_name",
                type="string",
                description="Second player name",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.compare_players(
            kwargs["player1_name"],
            kwargs["player2_name"],
        )


class GetCaptainRecommendationTool(BaseTool):
    """Get captain pick recommendations."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_captain_recommendation"

    @property
    def description(self) -> str:
        return (
            "Get captain pick recommendations for the upcoming gameweek "
            "based on availability-adjusted predictions."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_captain_recommendation()


class GetCurrentGameweekTool(BaseTool):
    """Get current gameweek information."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_current_gameweek"

    @property
    def description(self) -> str:
        return (
            "Get current gameweek information including season, completed "
            "GW, and prediction status."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_current_gameweek()


class GetTeamPlayersTool(BaseTool):
    """Get all players for a specific team."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_team_players"

    @property
    def description(self) -> str:
        return (
            "Get all players for a specific Premier League team with "
            "their predictions."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="team_name",
                type="string",
                description="Team name (e.g. 'Arsenal', 'Liverpool')",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_team_players(kwargs["team_name"])


class GetFixtureInfoTool(BaseTool):
    """Get upcoming fixture information for a team."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_fixture_info"

    @property
    def description(self) -> str:
        return (
            "Get upcoming fixture information for a team including "
            "difficulty, opponent, and home/away status."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="team_name",
                type="string",
                description="Team name",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_fixture_info(kwargs["team_name"])


class GetTopByPositionTool(BaseTool):
    """Get top predicted players at a specific position."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_top_by_position"

    @property
    def description(self) -> str:
        return "Get the top predicted players at a specific position."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="position",
                type="string",
                description="Position: GKP, DEF, MID, or FWD",
                enum=["GKP", "DEF", "MID", "FWD"],
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Number of players to return (default 10)",
                required=False,
                default=10,
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_top_by_position(
            kwargs["position"],
            kwargs.get("limit", 10),
        )


class GetDifferentialPicksTool(BaseTool):
    """Get low-ownership, high-upside differential picks."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_differential_picks"

    @property
    def description(self) -> str:
        return "Get low-ownership, high-upside differential player picks."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="limit",
                type="integer",
                description="Number of differentials to return (default 10)",
                required=False,
                default=10,
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_differential_picks(
            kwargs.get("limit", 10)
        )


class GetInjuredDoubtfulTool(BaseTool):
    """Get all currently injured, doubtful, or suspended players."""

    def __init__(self, chatbot_tools: ChatbotTools) -> None:
        self._tools = chatbot_tools

    @property
    def name(self) -> str:
        return "get_injured_doubtful_players"

    @property
    def description(self) -> str:
        return (
            "Get all players currently injured, doubtful, suspended, "
            "or flagged with availability concerns."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    def _execute(self, **kwargs: Any) -> Any:
        return self._tools.get_injured_doubtful_players()


# ---------------------------------------------------------------
# NEW tools extending beyond the original 12
# ---------------------------------------------------------------


class GetPlayerFormTool(BaseTool):
    """Get a player's recent form metrics."""

    def __init__(self, app_state: AppState) -> None:
        self._predictions = app_state.predictions
        self._pred_col = _find_prediction_column(self._predictions)

    @property
    def name(self) -> str:
        return "get_player_form"

    @property
    def description(self) -> str:
        return (
            "Get a player's recent form including average points, minutes, "
            "xG, and xA over the last 3 and 5 gameweeks."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player_name",
                type="string",
                description="Player name or partial name",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        from src.chatbot.player_resolver import PlayerResolver

        resolver = PlayerResolver(self._predictions)
        matches = resolver.resolve(kwargs["player_name"], max_results=1)
        if not matches:
            return {"error": f"No player found matching '{kwargs['player_name']}'."}

        p = matches[0]
        form_keys = [
            "element", "web_name", "team", "position",
            "total_points_avg_last_3", "total_points_avg_last_5",
            "minutes_avg_last_3", "minutes_avg_last_5",
            "xG_avg_last_3", "xA_avg_last_3",
            "form_index", "fpl_form", "fpl_points_per_game",
            "fpl_total_points_season",
            self._pred_col,
        ]
        return {k: p.get(k) for k in form_keys if k in p}


class GetPlayerStatsTool(BaseTool):
    """Get detailed statistical profile for a player."""

    def __init__(self, app_state: AppState) -> None:
        self._predictions = app_state.predictions

    @property
    def name(self) -> str:
        return "get_player_stats"

    @property
    def description(self) -> str:
        return (
            "Get detailed statistics for a player including xG, xA, BPS, "
            "ICT index, and season totals."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player_name",
                type="string",
                description="Player name or partial name",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        from src.chatbot.player_resolver import PlayerResolver

        resolver = PlayerResolver(self._predictions)
        matches = resolver.resolve(kwargs["player_name"], max_results=1)
        if not matches:
            return {"error": f"No player found matching '{kwargs['player_name']}'."}

        p = matches[0]
        stat_keys = [
            "element", "web_name", "team", "position", "value", "now_cost",
            "fpl_total_points_season", "fpl_form", "fpl_points_per_game",
            "fpl_expected_goals", "fpl_expected_assists",
            "fpl_expected_goal_involvements",
            "selected_by_percent", "ep_next",
            "xG_avg_last_3", "xA_avg_last_3",
            "total_points_avg_last_3", "total_points_avg_last_5",
            "minutes_avg_last_3", "minutes_avg_last_5",
            "form_index", "fixture_difficulty",
            "predicted_expected_points", "predicted_total_points",
            "captaincy_score", "predicted_p85_points", "predicted_p90_points",
        ]
        return {k: p.get(k) for k in stat_keys if k in p}


class AnalyzeTransferTool(BaseTool):
    """Analyze a potential transfer (player out → player in)."""

    def __init__(self, chatbot_tools: ChatbotTools, app_state: AppState) -> None:
        self._tools = chatbot_tools
        self._state = app_state

    @property
    def name(self) -> str:
        return "analyze_transfer"

    @property
    def description(self) -> str:
        return (
            "Analyze a potential transfer comparing the player being sold "
            "with the player being bought. Returns side-by-side data on "
            "predictions, form, availability, fixtures, and value."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player_out",
                type="string",
                description="Name of the player being sold/transferred out",
            ),
            ToolParameter(
                name="player_in",
                type="string",
                description="Name of the player being bought/transferred in",
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        out_info = self._tools.get_player_info(kwargs["player_out"])
        in_info = self._tools.get_player_info(kwargs["player_in"])

        if "error" in out_info:
            return {"error": f"Could not find player_out: {out_info['error']}"}
        if "error" in in_info:
            return {"error": f"Could not find player_in: {in_info['error']}"}

        # Compute value differential
        out_pts = float(
            out_info.get("predicted_expected_points")
            or out_info.get("score_d")
            or 0.0
        )
        in_pts = float(
            in_info.get("predicted_expected_points")
            or in_info.get("score_d")
            or 0.0
        )
        pts_gain = in_pts - out_pts

        out_price = float(out_info.get("value") or 0.0)
        in_price = float(in_info.get("value") or 0.0)
        price_diff = in_price - out_price

        return {
            "player_out": out_info,
            "player_in": in_info,
            "points_gain": round(pts_gain, 2),
            "price_difference": round(price_diff, 1),
            "recommendation_factors": {
                "points_improvement": pts_gain > 0.5,
                "affordable": price_diff <= 0,
                "player_in_available": in_info.get("availability_status") in (
                    "fit", "rotation_risk"
                ),
                "player_out_declining": out_pts < in_pts,
            },
        }


class AnalyzeSquadTool(BaseTool):
    """Analyze a squad for weaknesses and opportunities."""

    def __init__(self, app_state: AppState) -> None:
        self._state = app_state
        self._predictions = app_state.predictions
        self._pred_col = _find_prediction_column(self._predictions)

    @property
    def name(self) -> str:
        return "analyze_squad"

    @property
    def description(self) -> str:
        return (
            "Analyze a squad of player names to identify strengths, "
            "weaknesses, availability risks, and transfer priorities. "
            "Pass player names as a comma-separated string."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="player_names",
                type="string",
                description=(
                    "Comma-separated list of player names in the squad "
                    "(e.g. 'Salah, Palmer, Saka, Haaland')"
                ),
            ),
        ]

    def _execute(self, **kwargs: Any) -> Any:
        from src.chatbot.player_resolver import PlayerResolver

        resolver = PlayerResolver(self._predictions)
        p_names = kwargs.get("player_names", "")
        if isinstance(p_names, list):
            raw_names = [str(n).strip() for n in p_names if str(n).strip()]
        else:
            raw_names = [n.strip() for n in str(p_names).split(",") if n.strip()]

        squad_players = []
        not_found = []

        for name in raw_names:
            matches = resolver.resolve(name, max_results=1)
            if matches:
                squad_players.append(matches[0])
            else:
                not_found.append(name)

        if not squad_players:
            return {"error": "No players found from the provided names."}

        # Categorize by position
        by_position: dict[str, list[dict]] = {}
        for p in squad_players:
            pos = p.get("position", "Unknown")
            by_position.setdefault(pos, []).append(p)

        # Find risks
        injury_risks = [
            p for p in squad_players
            if p.get("availability_status") not in ("fit", None)
        ]

        rotation_risks = [
            p for p in squad_players
            if p.get("availability_status") == "rotation_risk"
            or p.get("rotation_risk", 0) > 0.3
        ]

        # Find weakest players
        weakest = sorted(
            squad_players,
            key=lambda p: float(p.get("predicted_expected_points") or p.get("score_d") or 0),
        )[:3]

        # Total predicted points
        total_pts = sum(
            float(p.get("predicted_expected_points") or p.get("score_d") or 0)
            for p in squad_players
        )

        return {
            "squad_size": len(squad_players),
            "not_found": not_found,
            "total_predicted_points": round(total_pts, 1),
            "position_breakdown": {
                pos: len(players)
                for pos, players in by_position.items()
            },
            "injury_risks": [
                {
                    "name": p.get("web_name"),
                    "team": p.get("team"),
                    "status": p.get("availability_status"),
                    "news": p.get("team_news"),
                }
                for p in injury_risks
            ],
            "rotation_risks": [
                {
                    "name": p.get("web_name"),
                    "team": p.get("team"),
                }
                for p in rotation_risks
            ],
            "weakest_players": [
                {
                    "name": p.get("web_name"),
                    "team": p.get("team"),
                    "position": p.get("position"),
                    "predicted_points": float(
                        p.get("predicted_expected_points") or p.get("score_d") or 0
                    ),
                }
                for p in weakest
            ],
            "transfer_priority_note": (
                "Players with availability risks or low predicted points "
                "should be considered for transfer first."
            ),
        }


# ---------------------------------------------------------------
# Registry builder
# ---------------------------------------------------------------


def build_tool_registry(app_state: AppState) -> ToolRegistry:
    """Build and populate a :class:`ToolRegistry` with all available tools.

    Wraps existing :class:`ChatbotTools` and adds new agentic tools.

    Args:
        app_state: The application state loaded at startup.

    Returns:
        A fully populated :class:`ToolRegistry`.
    """
    chatbot_tools = ChatbotTools(app_state)
    registry = ToolRegistry()

    # Original 12 tools (wrapping existing ChatbotTools)
    registry.register(SearchPlayerTool(chatbot_tools))
    registry.register(GetPlayerInfoTool(chatbot_tools))
    registry.register(GetPlayerAvailabilityTool(chatbot_tools))
    registry.register(GetGameweekPredictionsTool(chatbot_tools))
    registry.register(ComparePlayersTool(chatbot_tools))
    registry.register(GetCaptainRecommendationTool(chatbot_tools))
    registry.register(GetCurrentGameweekTool(chatbot_tools))
    registry.register(GetTeamPlayersTool(chatbot_tools))
    registry.register(GetFixtureInfoTool(chatbot_tools))
    registry.register(GetTopByPositionTool(chatbot_tools))
    registry.register(GetDifferentialPicksTool(chatbot_tools))
    registry.register(GetInjuredDoubtfulTool(chatbot_tools))

    # New agentic tools
    registry.register(GetPlayerFormTool(app_state))
    registry.register(GetPlayerStatsTool(app_state))
    registry.register(AnalyzeTransferTool(chatbot_tools, app_state))
    registry.register(AnalyzeSquadTool(app_state))

    logger.info(
        "Tool registry built: %d tools registered.", registry.count
    )

    return registry
