"""Fixture / Transfer Agent.

Responsible for:
- Upcoming fixtures and fixture difficulty
- Transfer opportunities
- Short-term vs medium-term value analysis
- Player-in/player-out transfer evaluation
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class FixtureTransferAgent(BaseAgent):
    """Analyzes fixtures and evaluates transfer opportunities."""

    @property
    def name(self) -> str:
        return "fixture_transfer"

    @property
    def description(self) -> str:
        return (
            "Analyzes upcoming fixtures, fixture difficulty, transfer "
            "opportunities, and short-term vs medium-term value."
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "get_fixture_info",
            "get_team_players",
            "analyze_transfer",
            "get_player_info",
            "compare_players",
            "get_gameweek_predictions",
            "get_top_by_position",
            "get_current_gameweek",
        ]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "fixture", "fixtures", "transfer", "sell", "buy",
            "replace", "swap", "replacement", "alternative",
            "schedule", "difficulty", "fdr",
            "next week", "upcoming", "gameweek",
            "hit", "-4", "worth",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Analyze fixtures or transfer opportunities."""
        tool_calls: list[dict[str, Any]] = []
        analysis: dict[str, Any] = {}
        lower = query.lower()
        ctx = context or {}

        # Transfer analysis
        player_names = ctx.get("player_names", [])
        if len(player_names) >= 2 and any(
            kw in lower for kw in ("transfer", "replace", "swap", "sell", "buy")
        ):
            result = self._call_tool(
                "analyze_transfer",
                player_out=player_names[0],
                player_in=player_names[1],
            )
            tool_calls.append({
                "tool": "analyze_transfer",
                "success": result.success,
            })
            if result.success:
                analysis["transfer_analysis"] = result.data

        # Fixture lookup for team
        team_name = ctx.get("team_name")
        if team_name:
            result = self._call_tool(
                "get_fixture_info",
                team_name=team_name,
            )
            tool_calls.append({
                "tool": "get_fixture_info",
                "success": result.success,
            })
            if result.success:
                analysis["fixture_info"] = result.data

        # Find best players by position for replacement
        position = ctx.get("position")
        if position and any(
            kw in lower for kw in ("replacement", "alternative", "best", "top")
        ):
            result = self._call_tool(
                "get_top_by_position",
                position=position,
                limit=5,
            )
            tool_calls.append({
                "tool": "get_top_by_position",
                "success": result.success,
            })
            if result.success:
                analysis["position_alternatives"] = result.data

        # General transfer suggestions
        if not analysis and any(
            kw in lower for kw in ("transfer", "option", "suggest", "recommend")
        ):
            for pos in ["MID", "FWD", "DEF"]:
                result = self._call_tool(
                    "get_top_by_position",
                    position=pos,
                    limit=3,
                )
                tool_calls.append({
                    "tool": "get_top_by_position",
                    "success": result.success,
                })
                if result.success:
                    analysis[f"top_{pos.lower()}"] = result.data

        # Gameweek context
        gw_result = self._call_tool("get_current_gameweek")
        tool_calls.append({
            "tool": "get_current_gameweek",
            "success": gw_result.success,
        })
        if gw_result.success:
            analysis["gameweek_info"] = gw_result.data

        return AgentResult(
            agent_name=self.name,
            analysis=analysis,
            tool_calls=tool_calls,
            summary="Fixture/transfer analysis completed.",
        )
