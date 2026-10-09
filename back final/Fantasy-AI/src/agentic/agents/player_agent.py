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

from src.agentic.agents.base import AgentResult, BaseAgent, Finding
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
        findings: list[Finding] = []
        sources: list[str] = ["FPL Player Database", "Model Projections"]

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
            if result.success and isinstance(result.data, dict):
                analysis["comparison"] = result.data
                p1 = result.data.get("player1", {})
                p2 = result.data.get("player2", {})
                p1_pts = p1.get("predicted_points", 0)
                p2_pts = p2.get("predicted_points", 0)
                findings.append(Finding(
                    factor="predictions",
                    player=p1.get("name") or player_names[0],
                    assessment="favorable" if p1_pts >= p2_pts else "lower",
                    evidence={"predicted_points": p1_pts},
                    summary=f"Projected at {p1_pts} pts.",
                ))
                findings.append(Finding(
                    factor="predictions",
                    player=p2.get("name") or player_names[1],
                    assessment="favorable" if p2_pts >= p1_pts else "lower",
                    evidence={"predicted_points": p2_pts},
                    summary=f"Projected at {p2_pts} pts.",
                ))
        elif len(player_names) == 1:
            pname = player_names[0]
            info_result = self._call_tool("get_player_info", player_name=pname)
            tool_calls.append({"tool": "get_player_info", "success": info_result.success})
            if info_result.success and isinstance(info_result.data, dict):
                analysis["player_info"] = info_result.data
                pts = info_result.data.get("predicted_points", 0)
                findings.append(Finding(
                    factor="predictions",
                    player=pname,
                    assessment="favorable" if pts >= 6.0 else "neutral",
                    evidence={"predicted_points": pts, "cost": info_result.data.get("cost")},
                    summary=f"Expected points: {pts} pts (Price: £{info_result.data.get('cost')}m).",
                ))

            form_result = self._call_tool("get_player_form", player_name=pname)
            tool_calls.append({"tool": "get_player_form", "success": form_result.success})
            if form_result.success and isinstance(form_result.data, dict):
                analysis["form"] = form_result.data
                f_score = form_result.data.get("fpl_form", "N/A")
                findings.append(Finding(
                    factor="form",
                    player=pname,
                    assessment="favorable",
                    evidence={"form": f_score},
                    summary=f"Current form metric: {f_score}.",
                ))

            avail_result = self._call_tool("get_player_availability", player_name=pname)
            tool_calls.append({"tool": "get_player_availability", "success": avail_result.success})
            if avail_result.success and isinstance(avail_result.data, dict):
                analysis["availability"] = avail_result.data
        else:
            info_result = self._call_tool("search_player_by_name", query=query)
            tool_calls.append({"tool": "search_player_by_name", "success": info_result.success})
            if info_result.success and info_result.data:
                analysis["search_results"] = info_result.data

        summary_text = f"Analyzed {len(player_names)} player(s)." if player_names else "Search completed."

        return AgentResult(
            agent_name=self.name,
            status="success",
            findings=findings,
            analysis=analysis,
            tool_calls=tool_calls,
            confidence=None,
            sources=sources,
            summary=summary_text,
        )
