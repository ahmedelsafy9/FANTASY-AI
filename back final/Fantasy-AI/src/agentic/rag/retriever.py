"""RAG retriever: high-level interface for knowledge retrieval.

Combines the vector store with query classification to retrieve
relevant strategy/rules knowledge.  Always returns source metadata
so the agent can distinguish retrieved knowledge from live data.
"""

from __future__ import annotations

import re
from typing import Any

from src.agentic.rag.vector_store import RetrievalResult, VectorStore
from src.config.logging_config import get_logger

logger = get_logger(__name__)


# Category hints: keywords that suggest which knowledge category
# is most relevant for a query.
_CATEGORY_HINTS: dict[str, list[str]] = {
    "chips": [
        "wildcard", "free hit", "bench boost", "triple captain",
        "chip", "when to use", "wc", "bb", "tc", "fh",
    ],
    "captaincy": [
        "captain", "captaincy", "armband", "who to captain",
        "vc", "vice captain",
    ],
    "rules": [
        "rule", "scoring", "points", "budget", "squad size",
        "formation", "auto-sub", "substitut", "deadline",
        "yellow card", "red card", "clean sheet", "bonus",
        "how many", "allowed", "limit", "maximum",
    ],
    "transfers": [
        "transfer", "sell", "buy", "replace", "swap",
        "hit", "-4", "kneejerk", "hold", "keep",
        "free transfer", "ft",
    ],
    "differentials": [
        "differential", "low ownership", "punt", "risk",
        "underowned", "under-owned",
    ],
    "strategy": [
        "strategy", "should i", "advice", "recommend",
        "plan", "approach", "best way", "optimal",
        "fixture swing", "template", "enabler",
        "points per million", "value", "premium",
        "bench", "set and forget",
    ],
}


def _classify_query_category(query: str) -> str | None:
    """Classify a query into a knowledge category.

    Args:
        query: The user's query text.

    Returns:
        Category string, or ``None`` if no strong match.
    """
    lower = query.lower()

    best_category = None
    best_count = 0

    for category, keywords in _CATEGORY_HINTS.items():
        count = sum(1 for kw in keywords if kw in lower)
        if count > best_count:
            best_count = count
            best_category = category

    return best_category if best_count >= 1 else None


class KnowledgeRetriever:
    """High-level retriever combining vector search with query classification.

    Usage::

        retriever = KnowledgeRetriever()
        retriever.initialize()

        results = retriever.retrieve("Should I wildcard?")
        for r in results:
            print(r.title, r.score)
    """

    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self._store = vector_store or VectorStore()
        self._initialized = False

    def initialize(self) -> None:
        """Index the knowledge base.  Safe to call multiple times."""
        if not self._initialized:
            self._store.index()
            self._initialized = True
            logger.info(
                "KnowledgeRetriever initialized with %d chunks.",
                self._store.chunk_count,
            )

    @property
    def is_ready(self) -> bool:
        """Whether the retriever has been initialized."""
        return self._initialized

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.05,
    ) -> list[RetrievalResult]:
        """Retrieve relevant knowledge for a query.

        The retriever first classifies the query to determine if a
        category filter should be applied, then performs vector search.

        Args:
            query: The user's question or topic.
            top_k: Maximum results to return.
            min_score: Minimum similarity threshold.

        Returns:
            List of :class:`RetrievalResult` with source metadata.
        """
        if not self._initialized:
            self.initialize()

        # Try category-filtered search first
        category = _classify_query_category(query)
        results: list[RetrievalResult] = []

        if category:
            # Map hint categories to document categories
            doc_category = {
                "rules": "rules",
                "strategy": "strategy",
                "chips": "strategy",
                "captaincy": "strategy",
                "transfers": "strategy",
                "differentials": "strategy",
            }.get(category, None)

            if doc_category:
                results = self._store.search(
                    query,
                    top_k=top_k,
                    min_score=min_score,
                    category_filter=doc_category,
                )

        # Fall back to unfiltered search if category search found nothing
        if not results:
            results = self._store.search(
                query,
                top_k=top_k,
                min_score=min_score,
            )

        logger.info(
            "Retrieved %d knowledge chunks for query='%s' (category=%s)",
            len(results),
            query[:60],
            category,
        )

        return results

    def retrieve_as_context(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.05,
    ) -> dict[str, Any]:
        """Retrieve knowledge and format as context for the agent.

        Returns a structured dict that the agent can inject into
        its reasoning, with clear source attribution.

        Args:
            query: The user's question.
            top_k: Maximum chunks.
            min_score: Minimum similarity.

        Returns:
            Dict with ``has_knowledge``, ``chunks``, and ``sources``.
        """
        results = self.retrieve(query, top_k=top_k, min_score=min_score)

        if not results:
            return {
                "has_knowledge": False,
                "chunks": [],
                "sources": [],
                "note": "No relevant knowledge found in the knowledge base.",
            }

        chunks = []
        sources = set()
        for r in results:
            chunks.append({
                "text": r.text,
                "title": r.title,
                "category": r.category,
                "relevance_score": round(r.score, 3),
            })
            sources.add(f"{r.title} ({r.category})")

        return {
            "has_knowledge": True,
            "chunks": chunks,
            "sources": sorted(sources),
            "note": (
                "This knowledge is from the Fantasy AI knowledge base "
                "(static FPL rules and strategy). It does NOT contain "
                "current player data — use tools for live information."
            ),
        }
