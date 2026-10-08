"""Lightweight vector store using TF-IDF + cosine similarity.

Uses scikit-learn (already in requirements) instead of heavy external
vector databases.  This is sufficient for the curated knowledge base
(~30 chunks) and avoids adding new dependencies.

The store supports:
- Indexing knowledge chunks
- Cosine-similarity search
- Source metadata preservation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.agentic.rag.knowledge_base import KnowledgeChunk, get_all_chunks
from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieval result with score and metadata.

    Attributes:
        text: The retrieved chunk text.
        score: Cosine similarity score (0–1).
        title: Title of the source document.
        category: Category of the source document.
        source: Source identifier for citation.
        chunk_index: Position within the source document.
        doc_id: Parent document ID.
    """

    text: str
    score: float
    title: str
    category: str
    source: str
    chunk_index: int = 0
    doc_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-safe dict."""
        return {
            "text": self.text,
            "score": round(self.score, 4),
            "title": self.title,
            "category": self.category,
            "source": self.source,
        }


class VectorStore:
    """TF-IDF based vector store for knowledge retrieval.

    Indexes :class:`KnowledgeChunk` objects and supports cosine-similarity
    search.  Built on scikit-learn's :class:`TfidfVectorizer`.
    """

    def __init__(self) -> None:
        self._chunks: list[KnowledgeChunk] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix: np.ndarray | None = None
        self._is_indexed = False

    def index(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        """Index knowledge chunks for retrieval.

        Args:
            chunks: Chunks to index.  If ``None``, uses the built-in
                knowledge base.
        """
        if chunks is None:
            chunks = get_all_chunks()

        if not chunks:
            logger.warning("No chunks to index.")
            return

        self._chunks = chunks
        texts = [chunk.text for chunk in chunks]

        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._matrix = self._vectorizer.fit_transform(texts).toarray()
        self._is_indexed = True

        logger.info(
            "Vector store indexed %d chunks (vocab size: %d)",
            len(chunks),
            len(self._vectorizer.vocabulary_),
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.05,
        category_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """Search the vector store for relevant chunks.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.
            min_score: Minimum cosine similarity threshold.
            category_filter: Optional category to filter by.

        Returns:
            List of :class:`RetrievalResult`, sorted by descending score.
        """
        if not self._is_indexed or self._vectorizer is None or self._matrix is None:
            logger.warning("Vector store not indexed. Call index() first.")
            return []

        if not query or not query.strip():
            return []

        # Vectorize the query
        query_vec = self._vectorizer.transform([query]).toarray()

        # Compute similarities
        similarities = cosine_similarity(query_vec, self._matrix)[0]

        # Rank and filter
        indices = np.argsort(similarities)[::-1]
        results: list[RetrievalResult] = []

        for idx in indices:
            if len(results) >= top_k:
                break

            score = float(similarities[idx])
            if score < min_score:
                break

            chunk = self._chunks[idx]

            if category_filter and chunk.category != category_filter:
                continue

            results.append(
                RetrievalResult(
                    text=chunk.text,
                    score=score,
                    title=chunk.title,
                    category=chunk.category,
                    source=chunk.source,
                    chunk_index=chunk.chunk_index,
                    doc_id=chunk.doc_id,
                )
            )

        logger.debug(
            "Vector search for '%s': %d results (top score: %.3f)",
            query[:50],
            len(results),
            results[0].score if results else 0.0,
        )

        return results

    @property
    def is_indexed(self) -> bool:
        """Whether the store has been indexed."""
        return self._is_indexed

    @property
    def chunk_count(self) -> int:
        """Number of indexed chunks."""
        return len(self._chunks)
