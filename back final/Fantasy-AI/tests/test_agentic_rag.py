"""Tests for the RAG pipeline.

Covers:
- Knowledge document chunking
- Vector store indexing and search
- Retriever query classification
- Retriever context formatting
- Source attribution
"""

from __future__ import annotations

import pytest

from src.agentic.rag.knowledge_base import (
    KnowledgeChunk,
    KnowledgeDocument,
    chunk_document,
    get_all_chunks,
    KNOWLEDGE_DOCUMENTS,
)
from src.agentic.rag.vector_store import RetrievalResult, VectorStore
from src.agentic.rag.retriever import KnowledgeRetriever, _classify_query_category


# ---------------------------------------------------------------
# Knowledge Base Tests
# ---------------------------------------------------------------


class TestKnowledgeBase:
    """Tests for document creation and chunking."""

    def test_document_has_deterministic_id(self):
        doc = KnowledgeDocument(
            title="Test", content="Hello world", category="test",
        )
        assert doc.doc_id
        # Same inputs → same ID
        doc2 = KnowledgeDocument(
            title="Test", content="Different content", category="test",
        )
        assert doc.doc_id == doc2.doc_id

    def test_chunk_document(self):
        doc = KnowledgeDocument(
            title="Test",
            content="First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
            category="test",
        )
        chunks = chunk_document(doc, chunk_size=30, overlap=0)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk, KnowledgeChunk)
            assert chunk.doc_id == doc.doc_id
            assert chunk.category == "test"

    def test_chunk_preserves_content(self):
        content = "Alpha\n\nBravo\n\nCharlie\n\nDelta"
        doc = KnowledgeDocument(
            title="T", content=content, category="test",
        )
        chunks = chunk_document(doc, chunk_size=10000)
        # With a huge chunk size, everything should be in one chunk
        assert len(chunks) == 1
        assert "Alpha" in chunks[0].text
        assert "Delta" in chunks[0].text

    def test_empty_document_returns_no_chunks(self):
        doc = KnowledgeDocument(
            title="Empty", content="   ", category="test",
        )
        assert chunk_document(doc) == []

    def test_builtin_documents_exist(self):
        assert len(KNOWLEDGE_DOCUMENTS) >= 6

    def test_get_all_chunks(self):
        chunks = get_all_chunks()
        assert len(chunks) > 0
        categories = {c.category for c in chunks}
        assert "rules" in categories
        assert "strategy" in categories


# ---------------------------------------------------------------
# Vector Store Tests
# ---------------------------------------------------------------


class TestVectorStore:
    """Tests for TF-IDF vector store."""

    def setup_method(self):
        self.store = VectorStore()
        self.store.index()

    def test_store_is_indexed(self):
        assert self.store.is_indexed is True
        assert self.store.chunk_count > 0

    def test_search_returns_results(self):
        results = self.store.search("captain pick who to captain")
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_search_scores_sorted_descending(self):
        results = self.store.search("transfer strategy")
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_search_respects_top_k(self):
        results = self.store.search("FPL rules", top_k=2)
        assert len(results) <= 2

    def test_search_respects_min_score(self):
        results = self.store.search(
            "xyznonexistent1234567890", min_score=0.5,
        )
        assert len(results) == 0

    def test_search_with_category_filter(self):
        results = self.store.search(
            "scoring system", category_filter="rules",
        )
        for r in results:
            assert r.category == "rules"

    def test_empty_query(self):
        assert self.store.search("") == []

    def test_result_has_metadata(self):
        results = self.store.search("wildcard chip")
        if results:
            r = results[0]
            assert r.title
            assert r.category
            assert r.source
            assert r.score > 0


# ---------------------------------------------------------------
# Retriever Tests
# ---------------------------------------------------------------


class TestRetriever:
    """Tests for the high-level knowledge retriever."""

    def setup_method(self):
        self.retriever = KnowledgeRetriever()
        self.retriever.initialize()

    def test_retriever_is_ready(self):
        assert self.retriever.is_ready is True

    def test_retrieve_returns_results(self):
        results = self.retriever.retrieve("When should I use my wildcard?")
        assert len(results) > 0

    def test_retrieve_as_context(self):
        ctx = self.retriever.retrieve_as_context(
            "How many points for a goal?"
        )
        assert "has_knowledge" in ctx
        if ctx["has_knowledge"]:
            assert len(ctx["chunks"]) > 0
            assert len(ctx["sources"]) > 0
            assert "note" in ctx

    def test_retrieve_no_match(self):
        ctx = self.retriever.retrieve_as_context(
            "xyznonexistent1234567890",
            min_score=0.9,
        )
        assert ctx["has_knowledge"] is False


class TestQueryClassification:
    """Tests for query category classification."""

    def test_rules_classification(self):
        assert _classify_query_category("How does the scoring system work?") == "rules"

    def test_strategy_classification(self):
        assert _classify_query_category("What's the best approach to plan my transfers?") == "strategy"

    def test_chips_classification(self):
        assert _classify_query_category("When should I use my wildcard?") == "chips"

    def test_captaincy_classification(self):
        assert _classify_query_category("Who should I captain this week?") == "captaincy"

    def test_transfer_classification(self):
        assert _classify_query_category("Should I sell and buy a replacement?") == "transfers"

    def test_no_match(self):
        result = _classify_query_category("hello world xyz")
        assert result is None
