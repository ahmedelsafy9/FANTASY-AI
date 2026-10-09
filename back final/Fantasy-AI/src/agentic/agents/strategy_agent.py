"""Strategy Agent.

Responsible for:
- Transfer strategy (when to hold, sell, buy)
- Captaincy strategy
- Chip timing (wildcard, free hit, bench boost, triple captain)
- Risk/reward evaluation
- Short-term vs long-term decisions
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent, Finding
from src.agentic.rag.retriever import KnowledgeRetriever
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class StrategyAgent(BaseAgent):
    """Provides strategic FPL advice grounded in knowledge and data."""

    def __init__(self, tool_registry, retriever: KnowledgeRetriever) -> None:
        super().__init__(tool_registry)
        self._retriever = retriever

    @property
    def name(self) -> str:
        return "strategy"

    @property
    def description(self) -> str:
        return (
            "Provides strategic FPL advice: transfers, captaincy, chips, "
            "risk/reward, and short-term vs long-term decisions."
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "get_captain_recommendation",
            "get_gameweek_predictions",
            "get_differential_picks",
            "get_current_gameweek",
            "analyze_squad",
        ]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "strategy", "should i", "worth", "advice",
            "wildcard", "free hit", "bench boost", "triple captain",
            "chip", "wc", "bb", "tc", "fh",
            "plan", "long term", "short term",
            "differential", "template", "risk",
            "hold", "keep", "sell", "when to",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Provide strategic advice combining knowledge and live data."""
        tool_calls: list[dict[str, Any]] = []
        analysis: dict[str, Any] = {}
        findings: list[Finding] = []
        sources: list[str] = ["FPL Strategic Context"]
        lower = query.lower()

        # Retrieve relevant strategy knowledge ONLY when query asks for strategy theory, rules, or chips
        knowledge = None
        needs_rag = any(kw in lower for kw in (
            "wildcard", "free hit", "bench boost", "triple captain", "chip", "wc", "bb", "tc", "fh",
            "rule", "strategy", "long term", "approach", "how to", "-4", "hit",
        ))
        if needs_rag:
            knowledge = self._retriever.retrieve_as_context(query, top_k=3)
            if knowledge.get("has_knowledge"):
                analysis["strategy_knowledge"] = knowledge
                sources.append("FPL Strategy Knowledge Base")
                findings.append(Finding(
                    factor="strategy",
                    player=None,
                    assessment="neutral",
                    evidence={"chunks_retrieved": len(knowledge.get("chunks", []))},
                    summary="Retrieved curated guidelines on chip timing and transfer tactics.",
                ))

        # Chip-related questions
        if any(kw in lower for kw in (
            "wildcard", "free hit", "bench boost", "triple captain",
            "chip", "wc", "bb", "tc", "fh",
        )):
            gw_result = self._call_tool("get_current_gameweek")
            tool_calls.append({
                "tool": "get_current_gameweek",
                "success": gw_result.success,
            })
            if gw_result.success:
                analysis["gameweek_context"] = gw_result.data
                sources.append("Live Gameweek Schedule")

        # Differential strategy
        if any(kw in lower for kw in ("differential", "low ownership", "punt")):
            result = self._call_tool(
                "get_differential_picks",
                limit=5,
            )
            tool_calls.append({
                "tool": "get_differential_picks",
                "success": result.success,
            })
            if result.success and isinstance(result.data, list):
                analysis["differential_picks"] = result.data
                sources.append("Differential Projections Engine")
                for d in result.data[:3]:
                    findings.append(Finding(
                        factor="strategy",
                        player=d.get("name"),
                        assessment="favorable",
                        evidence=d,
                        summary=f"Differential pick: {d.get('name')} (Ownership: {d.get('ownership', d.get('selected_by_percent', '<10%'))})",
                    ))

        # Captain strategy
        if any(kw in lower for kw in ("captain", "captaincy", "armband")):
            result = self._call_tool("get_captain_recommendation")
            tool_calls.append({
                "tool": "get_captain_recommendation",
                "success": result.success,
            })
            if result.success and isinstance(result.data, dict):
                analysis["captain_recommendation"] = result.data
                sources.append("Captaincy Optimization Model")

        # General predictions for context
        if not analysis.get("captain_recommendation") and not analysis.get("differential_picks") and not needs_rag:
            result = self._call_tool(
                "get_gameweek_predictions",
                limit=10,
            )
            tool_calls.append({
                "tool": "get_gameweek_predictions",
                "success": result.success,
            })
            if result.success:
                analysis["predictions_context"] = result.data

        return AgentResult(
            agent_name=self.name,
            status="success",
            findings=findings,
            analysis=analysis,
            tool_calls=tool_calls,
            knowledge_context=knowledge if (knowledge and knowledge.get("has_knowledge")) else None,
            confidence=None,
            sources=sources,
            summary="Strategic evaluation completed.",
        )
