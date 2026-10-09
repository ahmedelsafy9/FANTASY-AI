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

from src.agentic.agents.base import AgentResult, BaseAgent, Finding
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
        findings: list[Finding] = []
        sources: list[str] = ["Squad Optimization Engine"]
        lower = query.lower()

        # Captain-specific request
        if any(kw in lower for kw in ("captain", "captaincy", "armband", "who to c")):
            result = self._call_tool("get_captain_recommendation")
            tool_calls.append({
                "tool": "get_captain_recommendation",
                "success": result.success,
            })
            if result.success and isinstance(result.data, dict):
                analysis["captain_recommendation"] = result.data
                sources.append("Captaincy Model")
                top_c = result.data.get("top_captain", {})
                findings.append(Finding(
                    factor="strategy",
                    player=top_c.get("name") or top_c.get("web_name"),
                    assessment="favorable",
                    evidence=top_c,
                    summary=f"Top captain pick: {top_c.get('name')} ({top_c.get('predicted_points')} pts).",
                ))

        # Squad analysis if squad names or player list provided
        squad_names = (context or {}).get("squad_names") or (context or {}).get("player_names")
        if squad_names and (isinstance(squad_names, list) and len(squad_names) >= 2 or isinstance(squad_names, str)):
            result = self._call_tool(
                "analyze_squad",
                player_names=squad_names,
            )
            tool_calls.append({
                "tool": "analyze_squad",
                "success": result.success,
            })
            if result.success and isinstance(result.data, dict):
                analysis["squad_analysis"] = result.data
                weakest = result.data.get("weakest_players", [])
                for w in weakest:
                    findings.append(Finding(
                        factor="risk",
                        player=w.get("name"),
                        assessment="warning",
                        evidence=w,
                        summary=f"Low predicted points: {w.get('name')} ({w.get('predicted_points')} pts)",
                    ))
                for inj in result.data.get("injury_risks", []):
                    findings.append(Finding(
                        factor="availability",
                        player=inj.get("name"),
                        assessment="unfavorable",
                        evidence=inj,
                        summary=f"Injury risk: {inj.get('name')} ({inj.get('status')})",
                    ))

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
            if result.success and isinstance(result.data, dict):
                analysis["captain_recommendation"] = result.data
                top_c = result.data.get("top_captain", {})
                findings.append(Finding(
                    factor="strategy",
                    player=top_c.get("name"),
                    assessment="favorable",
                    evidence=top_c,
                    summary=f"Top armband pick: {top_c.get('name')}.",
                ))

        return AgentResult(
            agent_name=self.name,
            status="success",
            findings=findings,
            analysis=analysis,
            tool_calls=tool_calls,
            confidence=None,
            sources=sources,
            summary="Squad analysis completed.",
        )
