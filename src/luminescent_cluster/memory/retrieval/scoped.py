# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Scope-aware memory retrieval.

Implements hierarchical retrieval: user > project > global.

Related GitHub Issues:
- #99: Scope-Aware Retrieval

ADR Reference: ADR-003 Memory Architecture, Phase 1c (Retrieval & Ranking)
"""

from enum import IntEnum
from typing import Any, List, Optional

from luminescent_cluster.memory.retrieval.ranker import MemoryRanker
from luminescent_cluster.memory.schemas import Memory


class MemoryScope(IntEnum):
    """Memory scope hierarchy.

    Lower values have higher priority in the hierarchy.
    user > project > global
    """

    USER = 1
    PROJECT = 2
    GLOBAL = 3


class ScopedRetriever:
    """Scope-aware memory retriever.

    Retrieves memories respecting the scope hierarchy:
    1. User scope - personal preferences and facts
    2. Project scope - project-specific information
    3. Global scope - organization-wide knowledge

    Can cascade up the hierarchy if not enough results found.

    Attributes:
        provider: The memory provider for storage access.
        ranker: Memory ranker for scoring results.

    Example:
        >>> retriever = ScopedRetriever(provider)
        >>> results = await retriever.retrieve(
        ...     query="database",
        ...     user_id="user-1",
        ...     scope="project",
        ...     project_id="proj-1",
        ... )
    """

    def __init__(
        self,
        provider: Any,
        ranker: Optional[MemoryRanker] = None,
    ):
        """Initialize the scoped retriever.

        Args:
            provider: Memory provider implementation.
            ranker: Optional custom ranker (creates default if not provided).
        """
        self.provider = provider
        self.ranker = ranker or MemoryRanker()

    async def retrieve(
        self,
        query: str,
        user_id: str,
        scope: str = "user",
        project_id: Optional[str] = None,
        cascade: bool = False,
        limit: int = 5,
    ) -> List[Memory]:
        """Retrieve memories respecting scope hierarchy.

        Args:
            query: Search query.
            user_id: User ID for retrieval.
            scope: Starting scope ("user", "project", "global").
            project_id: Project ID for project-scoped retrieval.
            cascade: If True, cascade up hierarchy if results insufficient.
            limit: Maximum number of results.

        Returns:
            List of Memory objects matching the query and scope.
        """
        results: List[Memory] = []
        scopes_to_search = self._get_scopes_to_search(scope, cascade)

        for search_scope in scopes_to_search:
            scope_results = await self._retrieve_for_scope(
                query=query,
                user_id=user_id,
                scope=search_scope,
                project_id=project_id,
                limit=limit - len(results),
            )
            results.extend(scope_results)

            if len(results) >= limit:
                break

        # Rank and limit results
        if results:
            ranked = self.ranker.rank(query, results, limit=limit)
            return [memory for memory, _ in ranked]

        return results

    def _get_scopes_to_search(self, scope: str, cascade: bool) -> List[str]:
        """Get list of scopes to search based on starting scope and cascade.

        Args:
            scope: Starting scope.
            cascade: Whether to cascade up hierarchy.

        Returns:
            List of scope strings to search in order.
        """
        scope_order = ["user", "project", "global"]

        try:
            start_idx = scope_order.index(scope.lower())
        except ValueError:
            start_idx = 0

        if cascade:
            return scope_order[start_idx:]
        else:
            return [scope_order[start_idx]]

    async def _retrieve_for_scope(
        self,
        query: str,
        user_id: str,
        scope: str,
        project_id: Optional[str],
        limit: int,
    ) -> List[Memory]:
        """Retrieve memories for a specific scope.

        Args:
            query: Search query.
            user_id: User ID.
            scope: Scope to search.
            project_id: Project ID for project scope.
            limit: Maximum results.

        Returns:
            List of memories matching scope and query.
        """
        # Build filters for scope
        filters = self._build_scope_filters(scope, project_id)

        # Get all memories for user first
        all_memories = await self.provider.retrieve(query, user_id, limit=limit * 2)

        # Filter by scope
        scope_memories = []
        for memory in all_memories:
            if self._matches_scope(memory, scope, project_id):
                scope_memories.append(memory)

        return scope_memories[:limit]

    def _build_scope_filters(
        self, scope: str, project_id: Optional[str]
    ) -> dict[str, Any]:
        """Build filter dictionary for a scope.

        Args:
            scope: Scope to filter by.
            project_id: Project ID for project scope.

        Returns:
            Filter dictionary.
        """
        filters: dict[str, Any] = {}

        if scope == "project" and project_id:
            filters["project_id"] = project_id

        return filters

    def _matches_scope(
        self,
        memory: Memory,
        scope: str,
        project_id: Optional[str],
    ) -> bool:
        """Check if a memory matches the specified scope.

        Args:
            memory: Memory to check.
            scope: Required scope.
            project_id: Project ID for project scope.

        Returns:
            True if memory matches scope.
        """
        memory_scope = memory.metadata.get("scope", "user")

        if scope == "user":
            return memory_scope == "user" or memory_scope is None

        if scope == "project":
            if memory_scope != "project":
                return False
            if project_id:
                return memory.metadata.get("project_id") == project_id
            return True

        if scope == "global":
            return memory_scope == "global"

        return True

    async def retrieve_all_scopes(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        limit_per_scope: int = 3,
    ) -> dict[str, List[Memory]]:
        """Retrieve memories from all scopes separately.

        Args:
            query: Search query.
            user_id: User ID.
            project_id: Optional project ID.
            limit_per_scope: Max results per scope.

        Returns:
            Dictionary mapping scope names to memory lists.
        """
        results = {}

        for scope in ["user", "project", "global"]:
            scope_results = await self._retrieve_for_scope(
                query=query,
                user_id=user_id,
                scope=scope,
                project_id=project_id,
                limit=limit_per_scope,
            )
            results[scope] = scope_results

        return results
