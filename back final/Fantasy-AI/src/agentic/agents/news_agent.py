"""News / Availability Agent.

Responsible for:
- Injuries and suspensions
- Availability and team news
- Rotation concerns
- Doubtful players
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent, Finding
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class NewsAvailabilityAgent(BaseAgent):
    """Reports on injuries, suspensions, availability, and team news."""

    @property
    def name(self) -> str:
        return "news_availability"

    @property
    def description(self) -> str:
        return (
            "Reports on injuries, suspensions, availability, rotation "
            "concerns, and relevant team news."
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "get_injured_doubtful_players",
            "get_player_availability",
            "get_player_info",
            "search_player_by_name",
            "get_team_players",
        ]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "injur", "injury", "injured", "doubt", "doubtful",
            "suspend", "suspension", "banned", "red card",
            "available", "availability", "fit", "fitness",
            "news", "team news", "press conference",
            "ruled out", "out", "miss",
            "rotation", "benched", "dropped", "rested",
            # Arabic
            "مصاب", "إصاب", "غياب", "شكوك", "موقوف",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Gather availability and injury information efficiently."""
        tool_calls: list[dict[str, Any]] = []
        analysis: dict[str, Any] = {}
        findings: list[Finding] = []
        sources: list[str] = ["FPL Availability API"]
        ctx = context or {}

        # Specific player availability
        player_names = ctx.get("player_names", [])
        if player_names:
            for pname in player_names[:3]:
                result = self._call_tool(
                    "get_player_availability",
                    player_name=pname,
                )
                tool_calls.append({
                    "tool": "get_player_availability",
                    "success": result.success,
                })
                if result.success and isinstance(result.data, dict):
                    analysis.setdefault("player_availability", []).append(result.data)
                    chance = result.data.get("chance_of_playing_next_round", 100)
                    status_desc = result.data.get("news") or "Fit and available"
                    assessment = "favorable" if chance == 100 else ("doubtful" if chance and chance >= 50 else "unfavorable")
                    findings.append(Finding(
                        factor="availability",
                        player=result.data.get("name") or pname,
                        assessment=assessment,
                        evidence={"chance_of_playing": chance, "news": status_desc},
                        summary=f"Playing chance: {chance}%. Status: {status_desc}",
                    ))
        else:
            # General injury report only when no specific player is requested
            result = self._call_tool("get_injured_doubtful_players")
            tool_calls.append({
                "tool": "get_injured_doubtful_players",
                "success": result.success,
            })
            if result.success and isinstance(result.data, list):
                analysis["injury_report"] = result.data
                findings.append(Finding(
                    factor="availability",
                    player=None,
                    assessment="neutral",
                    evidence={"flagged_count": len(result.data)},
                    summary=f"{len(result.data)} players currently flagged across the Premier League.",
                ))

        # Team-specific news
        team_name = ctx.get("team_name")
        if team_name:
            result = self._call_tool(
                "get_team_players",
                team_name=team_name,
            )
            tool_calls.append({
                "tool": "get_team_players",
                "success": result.success,
            })
            if result.success and isinstance(result.data, dict):
                team_data = result.data
                players = team_data.get("players", [])
                flagged = [
                    p for p in players
                    if p.get("availability_status") not in ("fit", None)
                ]
                analysis["team_availability"] = {
                    "team": team_name,
                    "flagged_players": flagged,
                }

        summary_msg = f"Checked availability for {len(player_names)} player(s)." if player_names else "General injury report compiled."

        return AgentResult(
            agent_name=self.name,
            status="success",
            findings=findings,
            analysis=analysis,
            tool_calls=tool_calls,
            confidence=None,
            sources=sources,
            summary=summary_msg,
        )
