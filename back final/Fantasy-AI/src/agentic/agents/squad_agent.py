"""Squad Analysis Agent.

Responsible for squad-level analysis:
- Analyzing the user's current squad
- Identifying weaknesses
- Detecting rotation risks
- Identifying transfer priorities
- Evaluating captaincy options
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class SquadAnalysisAgent(BaseAgent):
    """Analyzes squad composition, weaknesses, and opportunities."""

    @property
    def name(self) -> str:
        return "squad_analysis"

    @property
    def description(self) -> str:
        return (
            "Analyzes the user's squad: weaknesses, rotation risks, "
            "transfer priorities, bench strength, and captaincy options."
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "analyze_squad",
            "get_captain_recommendation",
            "get_player_info",
            "get_player_availability",
            "get_gameweek_predictions",
            "get_injured_doubtful_players",
        ]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "squad", "my team", "my squad", "analyze my",
            "weakness", "weak", "bench", "rotation",
            "priority", "priorities", "who to sell",
            "captain", "captaincy", "armband", "who to c",
            "strongest", "best xi", "starting",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Analyze squad or provide captain recommendation."""
        tool_calls: list[dict[str, Any]] = []
        analysis: dict[str, Any] = {}
        lower = query.lower()

        # Captain-specific request
        if any(kw in lower for kw in ("captain", "captaincy", "armband", "who to c")):
            result = self._call_tool("get_captain_recommendation")
            tool_calls.append({
                "tool": "get_captain_recommendation",
                "success": result.success,
            })
            if result.success:
                analysis["captain_recommendation"] = result.data

        # Squad analysis if squad names provided
        squad_names = (context or {}).get("squad_names")
        if squad_names:
            result = self._call_tool(
                "analyze_squad",
                player_names=squad_names,
            )
            tool_calls.append({
                "tool": "analyze_squad",
                "success": result.success,
            })
            if result.success:
                analysis["squad_analysis"] = result.data

        # Injury check
        if any(kw in lower for kw in ("rotation", "injury", "risk", "weak")):
            result = self._call_tool("get_injured_doubtful_players")
            tool_calls.append({
                "tool": "get_injured_doubtful_players",
                "success": result.success,
            })
            if result.success:
                analysis["injury_report"] = result.data

        # If no specific analysis triggered, provide general recommendations
        if not analysis:
            result = self._call_tool("get_captain_recommendation")
            tool_calls.append({
                "tool": "get_captain_recommendation",
                "success": result.success,
            })
            if result.success:
                analysis["captain_recommendation"] = result.data

            pred_result = self._call_tool(
                "get_gameweek_predictions",
                limit=10,
            )
            tool_calls.append({
                "tool": "get_gameweek_predictions",
                "success": pred_result.success,
            })
            if pred_result.success:
                analysis["top_predictions"] = pred_result.data

        return AgentResult(
            agent_name=self.name,
            analysis=analysis,
            tool_calls=tool_calls,
            summary="Squad analysis completed.",
        )
