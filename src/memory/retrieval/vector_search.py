# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Dense vector semantic search for Two-Stage Retrieval Architecture.

Implements embedding-based semantic search using sentence-transformers
as part of ADR-003 Phase 3 Stage 1 candidate generation.

Vector search complements BM25 by handling:
- Semantic similarity (synonyms, paraphrases)
- Conceptual matching beyond exact keywords
- Natural language queries

Model: all-MiniLM-L6-v2 (384-dim, fast, good quality)

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from src.memory.schemas import Memory

logger = logging.getLogger(__name__)


class EmbeddingModel(Protocol):
    """Protocol for embedding models."""

    def encode(
        self,
        sentences: list[str] | str,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> NDArray[np.float32]: ...


@dataclass
class VectorIndex:
    """Vector index for a collection of documents.

    Stores embeddings and document IDs for efficient similarity search.

    Attributes:
        doc_ids: List of document IDs.
        embeddings: Normalized embedding matrix (num_docs x embedding_dim).
    """

    doc_ids: list[str] = field(default_factory=list)
    embeddings: Optional[NDArray[np.float32]] = None


class VectorSearch:
    """Dense vector semantic search for memory retrieval.

    Provides embedding-based semantic search using sentence-transformers.
    Maintains per-user indexes for multi-tenant support.

    Example:
        >>> search = VectorSearch()
        >>> search.index_memories("user-1", memories)
        >>> results = search.search("user-1", "database configuration", top_k=10)
        >>> for memory_id, score in results:
        ...     print(f"{memory_id}: {score:.4f}")

    Attributes:
        model_name: Name of the sentence-transformers model.
        embedding_dim: Dimension of embeddings.
    """

    # Default model - fast and good quality
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    DEFAULT_EMBEDDING_DIM = 384

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        lazy_load: bool = True,
    ):
        """Initialize vector search.

        Args:
            model_name: Sentence-transformers model name.
            embedding_dim: Expected embedding dimension.
            lazy_load: If True, load model on first use.
        """
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self._model: Optional[EmbeddingModel] = None
        self._indexes: dict[str, VectorIndex] = {}
        self._memory_contents: dict[str, dict[str, Memory]] = {}
        self._lazy_load = lazy_load

        if not lazy_load:
            self._load_model()

    def _load_model(self) -> EmbeddingModel:
        """Load the sentence-transformers model.

        Returns:
            Loaded embedding model.
        """
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = cast(EmbeddingModel, SentenceTransformer(self.model_name))
            logger.info("Embedding model loaded successfully")
            return self._model
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for VectorSearch. "
                "Install with: pip install sentence-transformers"
            ) from e

    @property
    def model(self) -> EmbeddingModel:
        """Get the embedding model, loading if necessary."""
        if self._model is None:
            return self._load_model()
        return self._model

    def embed(
        self,
        text: str | list[str],
        normalize: bool = True,
    ) -> NDArray[np.float32]:
        """Generate embeddings for text.

        Args:
            text: Single text or list of texts to embed.
            normalize: Whether to L2-normalize embeddings.

        Returns:
            Embedding array of shape (n, embedding_dim).
        """
        if isinstance(text, str):
            texts = [text]
        else:
            texts = text

        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=normalize,
        )

        return embeddings

    def embed_single(self, text: str, normalize: bool = True) -> NDArray[np.float32]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.
            normalize: Whether to L2-normalize.

        Returns:
            1D embedding array of shape (embedding_dim,).
        """
        embedding = self.embed(text, normalize=normalize)
        return embedding[0] if embedding.ndim == 2 else embedding

    def index_memories(
        self,
        user_id: str,
        memories: list[Memory],
        memory_ids: Optional[list[str]] = None,
        batch_size: int = 32,
    ) -> None:
        """Build vector index for a user's memories.

        Args:
            user_id: User ID to index for.
            memories: List of memories to index.
            memory_ids: Optional list of memory IDs.
            batch_size: Batch size for embedding generation.
        """
        if not memories:
            self._indexes[user_id] = VectorIndex()
            self._memory_contents[user_id] = {}
            return

        index = VectorIndex()
        self._memory_contents[user_id] = {}

        # Collect texts and IDs
        texts: list[str] = []
        for i, memory in enumerate(memories):
            if memory_ids:
                mem_id = memory_ids[i]
            else:
                mem_id = memory.metadata.get("memory_id", f"mem-{i}")

            index.doc_ids.append(mem_id)
            texts.append(memory.content)
            self._memory_contents[user_id][mem_id] = memory

        # Generate embeddings in batches
        embeddings = self.embed(texts, normalize=True)
        index.embeddings = embeddings

        self._indexes[user_id] = index

    def add_memory(
        self,
        user_id: str,
        memory: Memory,
        memory_id: str,
    ) -> None:
        """Add a single memory to the index.

        Args:
            user_id: User ID.
            memory: Memory to add.
            memory_id: ID for the memory.
        """
        # Create index if it doesn't exist
        if user_id not in self._indexes:
            self._indexes[user_id] = VectorIndex()
            self._memory_contents[user_id] = {}

        index = self._indexes[user_id]

        # Generate embedding
        embedding = self.embed_single(memory.content, normalize=True)

        # Add to index
        index.doc_ids.append(memory_id)

        if index.embeddings is None:
            index.embeddings = embedding.reshape(1, -1)
        else:
            index.embeddings = np.vstack([index.embeddings, embedding])

        # Store memory
        self._memory_contents[user_id][memory_id] = memory

    def remove_memory(self, user_id: str, memory_id: str) -> bool:
        """Remove a memory from the index.

        Args:
            user_id: User ID.
            memory_id: ID of memory to remove.

        Returns:
            True if memory was removed, False if not found.
        """
        if user_id not in self._indexes:
            return False

        index = self._indexes[user_id]

        try:
            doc_idx = index.doc_ids.index(memory_id)
        except ValueError:
            return False

        # Remove from doc_ids
        index.doc_ids.pop(doc_idx)

        # Remove from embeddings
        if index.embeddings is not None and len(index.doc_ids) > 0:
            index.embeddings = np.delete(index.embeddings, doc_idx, axis=0)
        else:
            index.embeddings = None

        # Remove from memory store
        self._memory_contents[user_id].pop(memory_id, None)

        return True

    def _cosine_similarity(
        self,
        query_embedding: NDArray[np.float32],
        doc_embeddings: NDArray[np.float32],
    ) -> NDArray[np.float32]:
        """Calculate cosine similarity between query and documents.

        Args:
            query_embedding: Query embedding (1D or 2D).
            doc_embeddings: Document embeddings (2D).

        Returns:
            Similarity scores array.
        """
        # Ensure query is 1D
        if query_embedding.ndim == 2:
            query_embedding = query_embedding[0]

        # For normalized vectors, cosine similarity is just dot product
        similarities = np.dot(doc_embeddings, query_embedding)

        return similarities

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 50,
    ) -> list[tuple[str, float]]:
        """Search for memories using semantic similarity.

        Args:
            user_id: User ID to search for.
            query: Search query.
            top_k: Maximum number of results to return.

        Returns:
            List of (memory_id, similarity_score) tuples sorted by score descending.
        """
        if user_id not in self._indexes:
            return []

        index = self._indexes[user_id]

        if index.embeddings is None or len(index.doc_ids) == 0:
            return []

        # Generate query embedding
        query_embedding = self.embed_single(query, normalize=True)

        # Calculate similarities
        similarities = self._cosine_similarity(query_embedding, index.embeddings)

        # Get top-k indices
        if len(similarities) <= top_k:
            top_indices = np.argsort(similarities)[::-1]
        else:
            top_indices = np.argpartition(similarities, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        # Build results
        results: list[tuple[str, float]] = []
        for idx in top_indices:
            results.append((index.doc_ids[idx], float(similarities[idx])))

        return results

    def search_with_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 50,
    ) -> list[tuple[Memory, float]]:
        """Search and return Memory objects with scores.

        Args:
            user_id: User ID to search for.
            query: Search query.
            top_k: Maximum number of results to return.

        Returns:
            List of (Memory, score) tuples sorted by score descending.
        """
        results = self.search(user_id, query, top_k)
        memories = self._memory_contents.get(user_id, {})

        return [
            (memories[mem_id], score)
            for mem_id, score in results
            if mem_id in memories
        ]

    def search_by_embedding(
        self,
        user_id: str,
        query_embedding: NDArray[np.float32],
        top_k: int = 50,
    ) -> list[tuple[str, float]]:
        """Search using a pre-computed embedding.

        Args:
            user_id: User ID to search for.
            query_embedding: Pre-computed query embedding.
            top_k: Maximum number of results to return.

        Returns:
            List of (memory_id, similarity_score) tuples.
        """
        if user_id not in self._indexes:
            return []

        index = self._indexes[user_id]

        if index.embeddings is None or len(index.doc_ids) == 0:
            return []

        # Calculate similarities
        similarities = self._cosine_similarity(query_embedding, index.embeddings)

        # Get top-k indices
        if len(similarities) <= top_k:
            top_indices = np.argsort(similarities)[::-1]
        else:
            top_indices = np.argpartition(similarities, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        # Build results
        results: list[tuple[str, float]] = []
        for idx in top_indices:
            results.append((index.doc_ids[idx], float(similarities[idx])))

        return results

    def get_memory(self, user_id: str, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID.

        Args:
            user_id: User ID.
            memory_id: Memory ID.

        Returns:
            Memory if found, None otherwise.
        """
        return self._memory_contents.get(user_id, {}).get(memory_id)

    def get_embedding(
        self, user_id: str, memory_id: str
    ) -> Optional[NDArray[np.float32]]:
        """Get the embedding for a memory.

        Args:
            user_id: User ID.
            memory_id: Memory ID.

        Returns:
            Embedding array if found, None otherwise.
        """
        if user_id not in self._indexes:
            return None

        index = self._indexes[user_id]

        try:
            doc_idx = index.doc_ids.index(memory_id)
        except ValueError:
            return None

        if index.embeddings is None:
            return None

        return index.embeddings[doc_idx]

    def has_index(self, user_id: str) -> bool:
        """Check if an index exists for a user.

        Args:
            user_id: User ID to check.

        Returns:
            True if index exists.
        """
        return user_id in self._indexes

    def clear_index(self, user_id: str) -> None:
        """Clear the index for a user.

        Args:
            user_id: User ID to clear.
        """
        self._indexes.pop(user_id, None)
        self._memory_contents.pop(user_id, None)

    def index_stats(self, user_id: str) -> dict[str, float | int]:
        """Get statistics about the index.

        Args:
            user_id: User ID.

        Returns:
            Dictionary with index statistics.
        """
        if user_id not in self._indexes:
            return {
                "total_docs": 0,
                "embedding_dim": self.embedding_dim,
                "model_loaded": self._model is not None,
            }

        index = self._indexes[user_id]
        return {
            "total_docs": len(index.doc_ids),
            "embedding_dim": (
                index.embeddings.shape[1] if index.embeddings is not None else 0
            ),
            "model_loaded": self._model is not None,
        }

    def similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Cosine similarity score between 0 and 1.
        """
        embeddings = self.embed([text1, text2], normalize=True)
        return float(np.dot(embeddings[0], embeddings[1]))
