# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""BM25 sparse keyword search for Two-Stage Retrieval Architecture.

Implements BM25 (Best Matching 25) ranking function for keyword-based
retrieval as part of ADR-003 Phase 3 Stage 1 candidate generation.

BM25 complements vector search by handling:
- Exact term matches
- Rare/unique keywords
- Technical terminology

Formula: BM25(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))

ADR Reference: ADR-003 Memory Architecture, Phase 3 (Two-Stage Retrieval)
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from luminescent_cluster.memory.schemas import Memory


@dataclass
class BM25Index:
    """BM25 index for a collection of documents.

    Stores term frequencies, document frequencies, and document lengths
    needed for efficient BM25 scoring.

    Attributes:
        doc_ids: List of document IDs in index order.
        doc_lengths: Document length for each document.
        doc_term_freqs: Term frequencies for each document.
        doc_freq: Number of documents containing each term.
        total_docs: Total number of documents.
        avg_doc_length: Average document length.
    """

    doc_ids: list[str] = field(default_factory=list)
    doc_lengths: list[int] = field(default_factory=list)
    doc_term_freqs: list[dict[str, int]] = field(default_factory=list)
    doc_freq: dict[str, int] = field(default_factory=dict)
    total_docs: int = 0
    avg_doc_length: float = 0.0


class BM25Search:
    """BM25 sparse keyword search for memory retrieval.

    Provides efficient keyword-based search using the BM25 ranking
    algorithm. Maintains per-user indexes for multi-tenant support.

    Example:
        >>> search = BM25Search()
        >>> search.index_memories("user-1", memories)
        >>> results = search.search("user-1", "database config", top_k=10)
        >>> for memory_id, score in results:
        ...     print(f"{memory_id}: {score:.4f}")

    Attributes:
        k1: Term frequency saturation parameter (default 1.5).
        b: Document length normalization parameter (default 0.75).
    """

    # Default BM25 parameters (tuned for short documents)
    DEFAULT_K1 = 1.5
    DEFAULT_B = 0.75

    # Tokenization pattern
    TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)

    # Stop words to exclude from indexing
    STOP_WORDS = frozenset(
        {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "or",
            "that",
            "the",
            "to",
            "was",
            "were",
            "will",
            "with",
        }
    )

    def __init__(
        self,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
        min_term_length: int = 2,
    ):
        """Initialize BM25 search.

        Args:
            k1: Term frequency saturation parameter.
                Higher values increase TF impact.
            b: Document length normalization (0-1).
                0 = no normalization, 1 = full normalization.
            min_term_length: Minimum term length to index.
        """
        self.k1 = k1
        self.b = b
        self.min_term_length = min_term_length
        self._indexes: dict[str, BM25Index] = {}
        self._memory_contents: dict[str, dict[str, Memory]] = {}

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase terms.

        Args:
            text: Text to tokenize.

        Returns:
            List of lowercase tokens.
        """
        tokens = self.TOKEN_PATTERN.findall(text.lower())
        return [t for t in tokens if len(t) >= self.min_term_length and t not in self.STOP_WORDS]

    def index_memories(
        self,
        user_id: str,
        memories: list[Memory],
        memory_ids: Optional[list[str]] = None,
    ) -> None:
        """Build BM25 index for a user's memories.

        Args:
            user_id: User ID to index for.
            memories: List of memories to index.
            memory_ids: Optional list of memory IDs. If not provided,
                       uses metadata["memory_id"] or generates from index.
        """
        index = BM25Index()
        self._memory_contents[user_id] = {}

        for i, memory in enumerate(memories):
            # Determine memory ID
            if memory_ids:
                mem_id = memory_ids[i]
            else:
                mem_id = memory.metadata.get("memory_id", f"mem-{i}")

            # Tokenize content
            tokens = self.tokenize(memory.content)

            # Store document info
            index.doc_ids.append(mem_id)
            index.doc_lengths.append(len(tokens))

            # Calculate term frequencies for this document
            term_freqs = Counter(tokens)
            index.doc_term_freqs.append(dict(term_freqs))

            # Update document frequencies
            for term in set(tokens):
                index.doc_freq[term] = index.doc_freq.get(term, 0) + 1

            # Store memory for later retrieval
            self._memory_contents[user_id][mem_id] = memory

        # Calculate statistics
        index.total_docs = len(memories)
        if index.total_docs > 0:
            index.avg_doc_length = sum(index.doc_lengths) / index.total_docs

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
            self._indexes[user_id] = BM25Index()
            self._memory_contents[user_id] = {}

        index = self._indexes[user_id]

        # Tokenize content
        tokens = self.tokenize(memory.content)

        # Store document info
        index.doc_ids.append(memory_id)
        index.doc_lengths.append(len(tokens))

        # Calculate term frequencies
        term_freqs = Counter(tokens)
        index.doc_term_freqs.append(dict(term_freqs))

        # Update document frequencies
        for term in set(tokens):
            index.doc_freq[term] = index.doc_freq.get(term, 0) + 1

        # Store memory
        self._memory_contents[user_id][memory_id] = memory

        # Update statistics
        index.total_docs += 1
        total_length = sum(index.doc_lengths)
        index.avg_doc_length = total_length / index.total_docs

    def remove_memory(self, user_id: str, memory_id: str) -> bool:
        """Remove a memory from the index.

        Note: This is O(n) - for frequent removals, consider periodic reindexing.

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

        # Get term frequencies for this document
        term_freqs = index.doc_term_freqs[doc_idx]

        # Update document frequencies
        for term in term_freqs:
            if term in index.doc_freq:
                index.doc_freq[term] -= 1
                if index.doc_freq[term] <= 0:
                    del index.doc_freq[term]

        # Remove document
        index.doc_ids.pop(doc_idx)
        index.doc_lengths.pop(doc_idx)
        index.doc_term_freqs.pop(doc_idx)

        # Remove from memory store
        self._memory_contents[user_id].pop(memory_id, None)

        # Update statistics
        index.total_docs -= 1
        if index.total_docs > 0:
            index.avg_doc_length = sum(index.doc_lengths) / index.total_docs
        else:
            index.avg_doc_length = 0.0

        return True

    def _calculate_idf(self, term: str, index: BM25Index) -> float:
        """Calculate Inverse Document Frequency for a term.

        Uses the standard BM25 IDF formula:
        IDF = log((N - n + 0.5) / (n + 0.5) + 1)

        Args:
            term: Term to calculate IDF for.
            index: BM25 index.

        Returns:
            IDF score for the term.
        """
        n = index.doc_freq.get(term, 0)
        N = index.total_docs

        if N == 0:
            return 0.0

        # Standard BM25 IDF formula with +1 to avoid negative values
        idf = math.log((N - n + 0.5) / (n + 0.5) + 1)
        return idf

    def _score_document(
        self,
        query_terms: list[str],
        doc_idx: int,
        index: BM25Index,
    ) -> float:
        """Calculate BM25 score for a single document.

        Args:
            query_terms: Tokenized query terms.
            doc_idx: Index of document in the index.
            index: BM25 index.

        Returns:
            BM25 score for the document.
        """
        score = 0.0
        doc_len = index.doc_lengths[doc_idx]
        doc_term_freqs = index.doc_term_freqs[doc_idx]
        avgdl = index.avg_doc_length

        for term in query_terms:
            if term not in doc_term_freqs:
                continue

            tf = doc_term_freqs[term]
            idf = self._calculate_idf(term, index)

            # BM25 term score
            # (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avgdl))
            numerator = tf * (self.k1 + 1)
            if avgdl > 0:
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
            else:
                denominator = tf + self.k1

            if denominator > 0:
                score += idf * (numerator / denominator)

        return score

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 50,
    ) -> list[tuple[str, float]]:
        """Search for memories using BM25 ranking.

        Args:
            user_id: User ID to search for.
            query: Search query.
            top_k: Maximum number of results to return.

        Returns:
            List of (memory_id, score) tuples sorted by score descending.
        """
        if user_id not in self._indexes:
            return []

        index = self._indexes[user_id]

        if index.total_docs == 0:
            return []

        # Tokenize query
        query_terms = self.tokenize(query)

        if not query_terms:
            return []

        # Score all documents
        scores: list[tuple[str, float]] = []

        for doc_idx in range(index.total_docs):
            score = self._score_document(query_terms, doc_idx, index)
            if score > 0:
                scores.append((index.doc_ids[doc_idx], score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

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

        return [(memories[mem_id], score) for mem_id, score in results if mem_id in memories]

    def get_memory(self, user_id: str, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID.

        Args:
            user_id: User ID.
            memory_id: Memory ID.

        Returns:
            Memory if found, None otherwise.
        """
        return self._memory_contents.get(user_id, {}).get(memory_id)

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
                "avg_doc_length": 0.0,
                "vocabulary_size": 0,
            }

        index = self._indexes[user_id]
        return {
            "total_docs": index.total_docs,
            "avg_doc_length": index.avg_doc_length,
            "vocabulary_size": len(index.doc_freq),
        }
