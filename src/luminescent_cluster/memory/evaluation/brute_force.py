# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Brute-force exact search for HNSW recall measurement.

Provides ground truth for Recall@k measurement by computing exact
cosine similarity against all documents in the corpus.

IMPORTANT: This module is designed for offline evaluation, not real-time
queries. The search operations are CPU-intensive and will block the
asyncio event loop. For async contexts, use the async wrapper methods
or run searches in a thread pool executor.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)

Research Reference:
- "HNSW at Scale: Why Your RAG System Gets Worse as the Vector Database Grows"
"""

import asyncio
import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np


class EmbeddingModel(Protocol):
    """Protocol for embedding models."""

    def encode(self, texts: list[str] | str) -> np.ndarray:
        """Encode text(s) to embedding vector(s)."""
        ...


@dataclass
class Document:
    """A document in the corpus for recall measurement.

    Attributes:
        id: Unique identifier for the document.
        content: Text content to be embedded.
        metadata: Optional metadata for filtering.
    """

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BruteForceResult:
    """Result from brute-force exact search.

    Attributes:
        document_id: ID of the matched document.
        content: Content of the matched document.
        score: Cosine similarity score (0.0 to 1.0).
    """

    document_id: str
    content: str
    score: float


class BruteForceSearcher:
    """Compute exact cosine similarity for HNSW recall ground truth.

    This class pre-computes embeddings for all documents in a corpus
    and performs exact nearest neighbor search using brute-force
    cosine similarity computation.

    Note: This class limits corpus size to prevent out-of-memory conditions.
    For larger corpora, use sampling or a dedicated evaluation service.

    Example:
        >>> from sentence_transformers import SentenceTransformer
        >>> model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        >>> searcher = BruteForceSearcher(model)
        >>> docs = [Document(id="1", content="Hello world")]
        >>> searcher.index_corpus(docs)
        >>> results = searcher.search("Hello", k=1)
        >>> print(results[0].document_id)
        "1"
    """

    # Maximum corpus size to prevent OOM (50K docs ~= 300MB for 384-dim embeddings)
    MAX_CORPUS_SIZE = 50_000

    def __init__(self, embedding_model: EmbeddingModel):
        """Initialize the brute-force searcher.

        Args:
            embedding_model: Model implementing encode() method.
                            Must return normalized embeddings for cosine similarity.
        """
        self._model = embedding_model
        self._documents: list[Document] = []
        self._embeddings: np.ndarray | None = None
        self._id_to_index: dict[str, int] = {}

    @property
    def corpus_size(self) -> int:
        """Return the number of documents in the corpus."""
        return len(self._documents)

    @property
    def is_indexed(self) -> bool:
        """Return True if a corpus has been indexed."""
        return self._embeddings is not None and len(self._documents) > 0

    def index_corpus(self, documents: list[Document]) -> None:
        """Pre-compute embeddings for all documents.

        Args:
            documents: List of documents to index.

        Raises:
            ValueError: If documents list is empty or exceeds MAX_CORPUS_SIZE.
        """
        if not documents:
            raise ValueError("Cannot index empty document list")

        if len(documents) > self.MAX_CORPUS_SIZE:
            raise ValueError(
                f"Corpus size {len(documents)} exceeds maximum allowed "
                f"({self.MAX_CORPUS_SIZE}). Use sampling or a dedicated "
                "evaluation service for larger corpora."
            )

        self._documents = documents
        self._id_to_index = {doc.id: i for i, doc in enumerate(documents)}

        # Extract content and compute embeddings in batch
        contents = [doc.content for doc in documents]
        embeddings = self._model.encode(contents)

        # Ensure 2D array (batch encoding may return 2D directly)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        # Avoid division by zero for zero vectors
        norms = np.where(norms == 0, 1, norms)
        self._embeddings = embeddings / norms

    def search(self, query: str, k: int = 10) -> list[BruteForceResult]:
        """Return top-k documents by exact cosine similarity.

        Args:
            query: Query text to search for.
            k: Number of results to return.

        Returns:
            List of BruteForceResult sorted by descending similarity.

        Raises:
            RuntimeError: If index_corpus has not been called.
            ValueError: If k is less than 1.
        """
        if not self.is_indexed:
            raise RuntimeError("Corpus not indexed. Call index_corpus() first.")
        if k < 1:
            raise ValueError("k must be at least 1")

        # Compute query embedding
        query_embedding = self._model.encode([query])
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        # Normalize query
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm

        # Compute cosine similarities (dot product of normalized vectors)
        similarities = np.dot(self._embeddings, query_embedding.T).flatten()

        # Get top-k indices
        k = min(k, len(self._documents))
        top_indices = np.argsort(similarities)[::-1][:k]

        # Build results
        results = []
        for idx in top_indices:
            doc = self._documents[idx]
            results.append(
                BruteForceResult(
                    document_id=doc.id,
                    content=doc.content,
                    score=float(similarities[idx]),
                )
            )

        return results

    def search_with_filter(
        self,
        query: str,
        k: int,
        filter_fn: Callable[[Document], bool],
    ) -> list[BruteForceResult]:
        """Filtered exact search for tenant/tag testing.

        This method computes cosine similarity only for documents
        that pass the filter function, simulating filtered HNSW search.

        Args:
            query: Query text to search for.
            k: Number of results to return.
            filter_fn: Function that returns True for documents to include.

        Returns:
            List of BruteForceResult sorted by descending similarity.

        Raises:
            RuntimeError: If index_corpus has not been called.
            ValueError: If k is less than 1.
        """
        if not self.is_indexed:
            raise RuntimeError("Corpus not indexed. Call index_corpus() first.")
        if k < 1:
            raise ValueError("k must be at least 1")

        # Compute query embedding
        query_embedding = self._model.encode([query])
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        # Normalize query
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm

        # Filter documents and compute similarities only for matching docs
        filtered_results = []
        for i, doc in enumerate(self._documents):
            if filter_fn(doc):
                similarity = float(
                    np.dot(self._embeddings[i], query_embedding.T).flatten()[0]
                )
                filtered_results.append(
                    BruteForceResult(
                        document_id=doc.id,
                        content=doc.content,
                        score=similarity,
                    )
                )

        # Sort by score descending and return top-k
        filtered_results.sort(key=lambda r: r.score, reverse=True)
        return filtered_results[:k]

    def get_document_ids(self) -> list[str]:
        """Return all document IDs in the corpus."""
        return [doc.id for doc in self._documents]

    # ─────────────────────────────────────────────────────────────────────────
    # Async Wrappers - Use these in asyncio contexts to avoid blocking
    # ─────────────────────────────────────────────────────────────────────────

    async def search_async(
        self,
        query: str,
        k: int = 10,
        executor: concurrent.futures.ThreadPoolExecutor | None = None,
    ) -> list[BruteForceResult]:
        """Async wrapper for search() that runs in a thread pool.

        Use this method in asyncio contexts to avoid blocking the event loop.

        Args:
            query: Query text to search for.
            k: Number of results to return.
            executor: Optional thread pool executor. If None, uses default.

        Returns:
            List of BruteForceResult sorted by descending similarity.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, self.search, query, k)

    async def search_with_filter_async(
        self,
        query: str,
        k: int,
        filter_fn: Callable[[Document], bool],
        executor: concurrent.futures.ThreadPoolExecutor | None = None,
    ) -> list[BruteForceResult]:
        """Async wrapper for search_with_filter() that runs in a thread pool.

        Use this method in asyncio contexts to avoid blocking the event loop.

        Args:
            query: Query text to search for.
            k: Number of results to return.
            filter_fn: Function that returns True for documents to include.
            executor: Optional thread pool executor. If None, uses default.

        Returns:
            List of BruteForceResult sorted by descending similarity.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            executor,
            self.search_with_filter,
            query,
            k,
            filter_fn,
        )
