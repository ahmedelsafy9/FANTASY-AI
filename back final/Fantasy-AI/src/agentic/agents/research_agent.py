"""Research / RAG Agent.

Responsible for:
- Retrieving relevant knowledge from the knowledge base
- Returning source context
- Separating retrieved knowledge from live data
- Answering rules-based questions
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.agentic.rag.retriever import KnowledgeRetriever
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class ResearchAgent(BaseAgent):
    """Retrieves and contextualizes knowledge from the FPL knowledge base."""

    def __init__(self, tool_registry, retriever: KnowledgeRetriever) -> None:
        super().__init__(tool_registry)
        self._retriever = retriever

    @property
    def name(self) -> str:
        return "research"

    @property
    def description(self) -> str:
        return (
            "Retrieves relevant FPL knowledge: rules, strategy guides, "
            "chip usage, and general fantasy principles."
        )

    @property
    def tool_names(self) -> list[str]:
        return ["get_current_gameweek"]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "rule", "rules", "how does", "how do",
            "what is", "what are", "explain",
            "scoring", "points", "budget",
            "formation", "auto-sub", "deadline",
            "why", "how", "what", "tell me about",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Retrieve knowledge relevant to the query."""
        tool_calls: list[dict[str, Any]] = []

        # Retrieve from knowledge base
        knowledge = self._retriever.retrieve_as_context(
            query, top_k=4, min_score=0.03,
        )

        analysis: dict[str, Any] = {
            "knowledge": knowledge,
        }

        # Add gameweek context
        gw_result = self._call_tool("get_current_gameweek")
        tool_calls.append({
            "tool": "get_current_gameweek",
            "success": gw_result.success,
        })
        if gw_result.success:
            analysis["gameweek_context"] = gw_result.data

        confidence = 0.7 if knowledge.get("has_knowledge") else 0.3

        return AgentResult(
            agent_name=self.name,
            analysis=analysis,
            tool_calls=tool_calls,
            knowledge_context=knowledge if knowledge.get("has_knowledge") else None,
            confidence=confidence,
            summary="Knowledge retrieval completed.",
        )
