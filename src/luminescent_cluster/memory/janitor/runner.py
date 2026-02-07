# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Janitor runner for orchestrating cleanup tasks.

Coordinates deduplication, contradiction handling, and expiration cleanup.

Related GitHub Issues:
- #102: Janitor Process Framework

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

import time
from typing import Any, Dict, Optional

from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler
from luminescent_cluster.memory.janitor.deduplication import Deduplicator
from luminescent_cluster.memory.janitor.expiration import ExpirationCleaner


class JanitorRunner:
    """Orchestrates all janitor cleanup tasks.

    Runs deduplication, contradiction handling, and expiration
    cleanup in sequence, collecting statistics from each.

    Attributes:
        provider: Memory provider for storage access.
        deduplicator: Deduplication task handler.
        contradiction_handler: Contradiction resolution handler.
        expiration_cleaner: Expiration cleanup handler.

    Example:
        >>> runner = JanitorRunner(provider)
        >>> result = await runner.run_all(user_id="user-1")
        >>> print(f"Removed {result['total_removed']} memories")
    """

    def __init__(
        self,
        provider: Any,
        deduplicator: Optional[Deduplicator] = None,
        contradiction_handler: Optional[ContradictionHandler] = None,
        expiration_cleaner: Optional[ExpirationCleaner] = None,
    ):
        """Initialize the janitor runner.

        Args:
            provider: Memory provider.
            deduplicator: Custom deduplicator (creates default if not provided).
            contradiction_handler: Custom handler (creates default if not provided).
            expiration_cleaner: Custom cleaner (creates default if not provided).
        """
        self.provider = provider
        self.deduplicator = deduplicator or Deduplicator()
        self.contradiction_handler = contradiction_handler or ContradictionHandler()
        self.expiration_cleaner = expiration_cleaner or ExpirationCleaner()

    async def run_deduplication(self, user_id: str) -> Dict[str, Any]:
        """Run deduplication task.

        Args:
            user_id: User ID to process.

        Returns:
            Deduplication statistics.
        """
        return await self.deduplicator.run(self.provider, user_id)

    async def run_contradiction_resolution(self, user_id: str) -> Dict[str, Any]:
        """Run contradiction resolution task.

        Args:
            user_id: User ID to process.

        Returns:
            Contradiction resolution statistics.
        """
        return await self.contradiction_handler.run(self.provider, user_id)

    async def run_expiration_cleanup(self, user_id: str) -> Dict[str, Any]:
        """Run expiration cleanup task.

        Args:
            user_id: User ID to process.

        Returns:
            Expiration cleanup statistics.
        """
        return await self.expiration_cleaner.run(self.provider, user_id)

    async def run_all(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Run all cleanup tasks.

        Args:
            user_id: User ID to process. If None, processes all users.

        Returns:
            Combined statistics from all tasks.
        """
        start_time = time.perf_counter()

        # Default user_id if not provided
        if user_id is None:
            user_id = "default"

        # Run all tasks in sequence
        dedup_result = await self.run_deduplication(user_id)
        contradiction_result = await self.run_contradiction_resolution(user_id)
        expiration_result = await self.run_expiration_cleanup(user_id)

        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        # Combine results
        total_processed = (
            dedup_result.get("processed", 0)
            + contradiction_result.get("processed", 0)
            + expiration_result.get("processed", 0)
        )

        total_removed = (
            dedup_result.get("removed", 0)
            + contradiction_result.get("resolved", 0)
            + expiration_result.get("removed", 0)
        )

        return {
            "deduplication": dedup_result,
            "contradiction": contradiction_result,
            "expiration": expiration_result,
            "total_processed": total_processed,
            "total_removed": total_removed,
            "duration_ms": duration_ms,
        }
