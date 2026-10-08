"""Player Analysis Agent.

Responsible for individual player analysis:
- Form and recent performance
- Minutes and availability
- Statistics and underlying numbers
- Fixture context
- Comparison with alternatives
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class PlayerAnalysisAgent(BaseAgent):
    """Analyzes individual players using stats, form, and availability data."""

    @property
    def name(self) -> str:
        return "player_analysis"

    @property
    def description(self) -> str:
        return (
            "Analyzes individual players: form, minutes, availability, "
            "statistics, fixture context, and comparison with alternatives."
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "search_player_by_name",
            "get_player_info",
            "get_player_availability",
            "get_player_form",
            "get_player_stats",
            "compare_players",
            "get_fixture_info",
        ]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "player", "form", "stats", "minutes", "xg", "xa",
            "how is", "tell me about", "is he", "should i get",
            "compare", "vs", "versus", "or", "better",
            "fit", "injured", "available", "start",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Analyze player(s) mentioned in the query."""
        tool_calls: list[dict[str, Any]] = []
        analysis: dict[str, Any] = {}

        # Extract player names from context if provided
        player_names = (context or {}).get("player_names", [])

        if len(player_names) >= 2:
            # Comparison mode
            result = self._call_tool(
                "compare_players",
                player1_name=player_names[0],
                player2_name=player_names[1],
            )
            tool_calls.append({
                "tool": "compare_players",
                "success": result.success,
            })
            if result.success:
                analysis["comparison"] = result.data
        elif len(player_names) == 1:
            # Single player mode — get comprehensive data
            info_result = self._call_tool(
                "get_player_info",
                player_name=player_names[0],
            )
            tool_calls.append({
                "tool": "get_player_info",
                "success": info_result.success,
            })
            if info_result.success:
                analysis["player_info"] = info_result.data

            form_result = self._call_tool(
                "get_player_form",
                player_name=player_names[0],
            )
            tool_calls.append({
                "tool": "get_player_form",
                "success": form_result.success,
            })
            if form_result.success:
                analysis["form"] = form_result.data

            avail_result = self._call_tool(
                "get_player_availability",
                player_name=player_names[0],
            )
            tool_calls.append({
                "tool": "get_player_availability",
                "success": avail_result.success,
            })
            if avail_result.success:
                analysis["availability"] = avail_result.data
        else:
            # No specific player — try to extract from query text
            info_result = self._call_tool(
                "search_player_by_name",
                query=query,
            )
            tool_calls.append({
                "tool": "search_player_by_name",
                "success": info_result.success,
            })
            if info_result.success and info_result.data:
                analysis["search_results"] = info_result.data

        return AgentResult(
            agent_name=self.name,
            analysis=analysis,
            tool_calls=tool_calls,
            summary="Player analysis completed.",
        )
