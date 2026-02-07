# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Expiration-based memory cleanup.

Removes memories that have passed their expiration date.

Related GitHub Issues:
- #105: Expiration Cleanup

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

from datetime import datetime, timezone
from typing import Any, Dict

from luminescent_cluster.memory.schemas import Memory


class ExpirationCleaner:
    """Cleans up expired memories.

    Removes memories where expires_at is in the past.
    Memories without expiration are never removed by this process.

    Example:
        >>> cleaner = ExpirationCleaner()
        >>> result = await cleaner.run(provider, "user-1")
        >>> print(f"Removed {result['removed']} expired memories")
    """

    def is_expired(self, memory: Memory) -> bool:
        """Check if a memory is expired.

        Args:
            memory: Memory to check.

        Returns:
            True if memory is expired.
        """
        if memory.expires_at is None:
            return False

        now = datetime.now(timezone.utc)

        # Ensure timezone aware comparison
        expires_at = memory.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return expires_at < now

    async def run(self, provider: Any, user_id: str) -> Dict[str, Any]:
        """Run expiration cleanup on all memories for a user.

        Args:
            provider: Memory provider.
            user_id: User ID to process.

        Returns:
            Statistics about the cleanup run.
        """
        # Get all memories for user
        all_memories = await provider.search(user_id, filters={}, limit=10000)
        processed = len(all_memories)
        removed = 0

        # Find and remove expired memories
        for memory in all_memories:
            if self.is_expired(memory):
                if hasattr(memory, "id") and memory.id:
                    try:
                        await provider.delete(memory.id)
                        removed += 1
                    except Exception:
                        pass

        return {
            "processed": processed,
            "removed": removed,
        }
