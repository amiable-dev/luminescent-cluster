# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS Shared Memory Pools - ADR-003 Phase 4.2 (Issues #144-149).

Shared memory pools for multi-agent collaboration:
- Create and manage named memory pools
- Membership with permission levels (READ, WRITE, ADMIN)
- Share memories across agents within pools
- Pool lifecycle management (active, archived, deleted)

Design follows thread-safe singleton pattern like AgentRegistry.
"""

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Optional

from luminescent_cluster.memory.maas.registry import AgentRegistry
from luminescent_cluster.memory.maas.scope import PermissionModel, SharedScope

# Default limits for DoS prevention
DEFAULT_MAX_POOLS = 10000
DEFAULT_MAX_MEMBERSHIPS_PER_POOL = 1000
DEFAULT_MAX_SHARED_MEMORIES_PER_POOL = 100000


class PoolStatus(str, Enum):
    """Status of a shared memory pool."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class DuplicatePoolError(Exception):
    """Raised when attempting to create a pool with duplicate ID."""

    def __init__(self, pool_id: str):
        self.pool_id = pool_id
        super().__init__(f"Pool with ID '{pool_id}' already exists")


class PoolCapacityError(Exception):
    """Raised when pool capacity is exceeded (DoS prevention)."""

    def __init__(self, resource: str, limit: int):
        self.resource = resource
        self.limit = limit
        super().__init__(f"Pool capacity exceeded: {resource} limit is {limit}")


@dataclass
class PoolMembership:
    """Membership record for an agent in a pool.

    Attributes:
        agent_id: The member agent's ID.
        permission: Permission level (READ, WRITE, ADMIN).
        joined_at: When the agent joined the pool.
    """

    agent_id: str
    permission: PermissionModel
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SharedMemoryRef:
    """Reference to a shared memory in a pool.

    Attributes:
        memory_id: The memory's unique ID.
        shared_by: Agent ID that shared this memory.
        scope: Visibility scope of this share.
        shared_at: When the memory was shared.
    """

    memory_id: str
    shared_by: str
    scope: SharedScope
    shared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SharedMemoryPool:
    """A named pool for sharing memories between agents.

    Attributes:
        id: Unique pool identifier.
        name: Human-readable pool name.
        owner_id: User ID that owns this pool.
        scope: Default visibility scope for the pool.
        status: Pool status (ACTIVE, ARCHIVED).
        created_at: When the pool was created.
        metadata: Arbitrary pool metadata.
    """

    id: str
    name: str
    owner_id: str
    scope: SharedScope
    status: PoolStatus = PoolStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "SharedMemoryPool":
        """Create a defensive copy of this pool.

        Returns a new SharedMemoryPool instance with copied metadata
        to prevent external mutation of internal state.

        Returns:
            A new SharedMemoryPool instance with the same data.
        """
        return SharedMemoryPool(
            id=self.id,
            name=self.name,
            owner_id=self.owner_id,
            scope=self.scope,
            status=self.status,
            created_at=self.created_at,
            metadata=self.metadata.copy(),
        )


class PoolRegistry:
    """Singleton registry for shared memory pools.

    The PoolRegistry manages all shared memory pools, their memberships,
    and shared memory references.

    Thread-safe: All operations use RLock for synchronization.

    Usage (creating pools):
        registry = PoolRegistry.get()
        pool_id = registry.create_pool(
            name="project-memories",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

    Usage (joining pools):
        registry = PoolRegistry.get()
        registry.join_pool(pool_id, agent_id, PermissionModel.READ)
    """

    # Singleton management
    _instance: ClassVar[Optional["PoolRegistry"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _audit_logger: ClassVar[Optional[Any]] = None  # MaaSAuditLogger

    def __init__(
        self,
        max_pools: int = DEFAULT_MAX_POOLS,
        max_memberships_per_pool: int = DEFAULT_MAX_MEMBERSHIPS_PER_POOL,
        max_shared_memories_per_pool: int = DEFAULT_MAX_SHARED_MEMORIES_PER_POOL,
    ):
        """Initialize the registry (internal use only).

        Args:
            max_pools: Maximum number of pools (DoS prevention).
            max_memberships_per_pool: Maximum members per pool.
            max_shared_memories_per_pool: Maximum shared memories per pool.
        """
        self._pools: dict[str, SharedMemoryPool] = {}
        self._memberships: dict[str, dict[str, PoolMembership]] = defaultdict(
            dict
        )  # pool_id -> agent_id -> membership
        self._agent_pools: dict[str, set[str]] = defaultdict(set)  # agent_id -> set of pool_ids
        self._shared_memories: dict[str, list[SharedMemoryRef]] = defaultdict(
            list
        )  # pool_id -> list of refs
        self._rlock = threading.RLock()
        self._max_pools = max_pools
        self._max_memberships_per_pool = max_memberships_per_pool
        self._max_shared_memories_per_pool = max_shared_memories_per_pool

    @classmethod
    def get(cls) -> "PoolRegistry":
        """Get the singleton PoolRegistry instance.

        Thread-safe: Uses double-checked locking pattern.

        Returns:
            The singleton PoolRegistry instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing only)."""
        with cls._lock:
            cls._instance = None
            cls._audit_logger = None

    @classmethod
    def set_audit_logger(cls, logger: Any) -> None:
        """Set the audit logger for the registry.

        Args:
            logger: MaaSAuditLogger instance.
        """
        cls._audit_logger = logger

    def _log_event(
        self,
        event_type: str,
        agent_id: str,
        action: str,
        outcome: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an event if audit logger is configured.

        Thread-safe: Captures logger reference to prevent TOCTOU race.
        """
        # Capture reference to prevent race condition (TOCTOU)
        logger = self._audit_logger
        if logger is not None:
            logger.log_agent_operation(
                event_type=event_type,
                agent_id=agent_id,
                action=action,
                outcome=outcome,
                details=details,
            )

    def create_pool(
        self,
        name: str,
        owner_id: str,
        scope: SharedScope,
        pool_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a new shared memory pool.

        Args:
            name: Human-readable pool name.
            owner_id: User ID that owns this pool.
            scope: Default visibility scope.
            pool_id: Optional custom pool ID.
            metadata: Optional pool metadata.

        Returns:
            The pool ID.

        Raises:
            DuplicatePoolError: If pool_id already exists.
            PoolCapacityError: If max_pools limit is reached.
        """
        with self._rlock:
            # Check capacity limit (DoS prevention)
            if len(self._pools) >= self._max_pools:
                self._log_event(
                    event_type="POOL_OPERATION",
                    agent_id=owner_id,
                    action="create_pool",
                    outcome="denied",
                    details={"reason": "capacity_exceeded", "limit": self._max_pools},
                )
                raise PoolCapacityError("pools", self._max_pools)

            if pool_id is None:
                pool_id = f"pool-{uuid.uuid4().hex}"

            if pool_id in self._pools:
                raise DuplicatePoolError(pool_id)

            # Copy metadata to prevent external mutation
            pool = SharedMemoryPool(
                id=pool_id,
                name=name,
                owner_id=owner_id,
                scope=scope,
                metadata=(metadata or {}).copy(),  # Defensive copy of input
            )

            self._pools[pool_id] = pool

            # Log success
            self._log_event(
                event_type="POOL_OPERATION",
                agent_id=owner_id,
                action="create_pool",
                outcome="success",
                details={"pool_id": pool_id, "name": name},
            )

            return pool_id

    def get_pool(self, pool_id: str) -> Optional[SharedMemoryPool]:
        """Get a pool by ID.

        Returns a defensive copy to prevent external mutation of internal state.

        Args:
            pool_id: The pool ID to look up.

        Returns:
            Defensive copy of SharedMemoryPool if found, None otherwise.
        """
        with self._rlock:
            pool = self._pools.get(pool_id)
            if pool is None:
                return None
            return pool.copy()

    def get_active_pools(self) -> list[SharedMemoryPool]:
        """Get all active pools.

        Returns defensive copies to prevent external mutation of internal state.

        Returns:
            List of active SharedMemoryPool copies.
        """
        with self._rlock:
            return [p.copy() for p in self._pools.values() if p.status == PoolStatus.ACTIVE]

    def join_pool(
        self,
        pool_id: str,
        agent_id: str,
        permission: PermissionModel,
    ) -> bool:
        """Add an agent to a pool.

        Args:
            pool_id: The pool to join.
            agent_id: The agent joining.
            permission: Requested permission level.

        Returns:
            True if joined successfully, False if pool/agent not found.

        Note:
            If the agent's owner matches the pool owner, they get ADMIN.

        Raises:
            PoolCapacityError: If membership limit is reached.
        """
        with self._rlock:
            pool = self._pools.get(pool_id)
            if pool is None:
                self._log_event(
                    event_type="POOL_OPERATION",
                    agent_id=agent_id,
                    action="join_pool",
                    outcome="failed",
                    details={"pool_id": pool_id, "reason": "pool_not_found"},
                )
                return False

            # Verify agent exists in registry (integrity check)
            agent_registry = AgentRegistry.get()
            agent = agent_registry.get_agent(agent_id)
            if agent is None:
                self._log_event(
                    event_type="POOL_OPERATION",
                    agent_id=agent_id,
                    action="join_pool",
                    outcome="failed",
                    details={"pool_id": pool_id, "reason": "agent_not_found"},
                )
                return False

            # Check membership capacity (DoS prevention) - only for new members
            if agent_id not in self._memberships.get(pool_id, {}):
                current_count = len(self._memberships.get(pool_id, {}))
                if current_count >= self._max_memberships_per_pool:
                    self._log_event(
                        event_type="POOL_OPERATION",
                        agent_id=agent_id,
                        action="join_pool",
                        outcome="denied",
                        details={
                            "pool_id": pool_id,
                            "reason": "membership_limit_exceeded",
                            "limit": self._max_memberships_per_pool,
                        },
                    )
                    raise PoolCapacityError("memberships_per_pool", self._max_memberships_per_pool)

            # Check if agent's owner matches pool owner -> grant ADMIN
            if agent.owner_id == pool.owner_id:
                permission = PermissionModel.ADMIN

            membership = PoolMembership(
                agent_id=agent_id,
                permission=permission,
            )

            self._memberships[pool_id][agent_id] = membership
            self._agent_pools[agent_id].add(pool_id)

            # Log success
            self._log_event(
                event_type="POOL_OPERATION",
                agent_id=agent_id,
                action="join_pool",
                outcome="success",
                details={"pool_id": pool_id, "permission": str(permission)},
            )

            return True

    def leave_pool(self, pool_id: str, agent_id: str) -> bool:
        """Remove an agent from a pool.

        Args:
            pool_id: The pool to leave.
            agent_id: The agent leaving.

        Returns:
            True if left successfully, False if not a member.
        """
        with self._rlock:
            if pool_id not in self._memberships:
                return False

            if agent_id not in self._memberships[pool_id]:
                return False

            del self._memberships[pool_id][agent_id]
            self._agent_pools[agent_id].discard(pool_id)

            return True

    def get_pool_members(self, pool_id: str) -> list[dict[str, Any]]:
        """Get all members of a pool.

        Args:
            pool_id: The pool to query.

        Returns:
            List of member dicts with agent_id and permission.
        """
        with self._rlock:
            members = self._memberships.get(pool_id, {})
            return [
                {
                    "agent_id": m.agent_id,
                    "permission": str(m.permission),
                    "joined_at": m.joined_at.isoformat(),
                }
                for m in members.values()
            ]

    def get_agent_pools(self, agent_id: str) -> list[SharedMemoryPool]:
        """Get all pools an agent is a member of.

        Returns defensive copies to prevent external mutation of internal state.

        Args:
            agent_id: The agent to query.

        Returns:
            List of SharedMemoryPool copies.
        """
        with self._rlock:
            pool_ids = self._agent_pools.get(agent_id, set())
            return [self._pools[pid].copy() for pid in pool_ids if pid in self._pools]

    def get_member_permission(
        self,
        pool_id: str,
        agent_id: str,
    ) -> Optional[PermissionModel]:
        """Get an agent's permission level in a pool.

        Args:
            pool_id: The pool to check.
            agent_id: The agent to check.

        Returns:
            PermissionModel if member, None otherwise.
        """
        with self._rlock:
            membership = self._memberships.get(pool_id, {}).get(agent_id)
            if membership:
                return membership.permission
            return None

    def check_access(
        self,
        pool_id: str,
        agent_id: str,
        required: PermissionModel,
    ) -> bool:
        """Check if an agent has required permission level.

        Args:
            pool_id: The pool to check.
            agent_id: The agent to check.
            required: Required permission level.

        Returns:
            True if agent has required permission, False otherwise.
        """
        with self._rlock:
            actual = self.get_member_permission(pool_id, agent_id)
            if actual is None:
                return False
            return actual.includes(required)

    def archive_pool(self, pool_id: str) -> bool:
        """Archive a pool.

        Args:
            pool_id: The pool to archive.

        Returns:
            True if archived, False if not found.
        """
        with self._rlock:
            pool = self._pools.get(pool_id)
            if pool is None:
                return False

            pool.status = PoolStatus.ARCHIVED
            return True

    def delete_pool(self, pool_id: str) -> bool:
        """Delete a pool permanently.

        Args:
            pool_id: The pool to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._rlock:
            if pool_id not in self._pools:
                return False

            # Remove pool
            del self._pools[pool_id]

            # Clean up memberships
            if pool_id in self._memberships:
                for agent_id in self._memberships[pool_id]:
                    self._agent_pools[agent_id].discard(pool_id)
                del self._memberships[pool_id]

            # Clean up shared memories
            if pool_id in self._shared_memories:
                del self._shared_memories[pool_id]

            return True

    def share_memory(
        self,
        pool_id: str,
        memory_id: str,
        agent_id: str,
        scope: SharedScope,
    ) -> bool:
        """Share a memory to a pool.

        Args:
            pool_id: The pool to share to.
            memory_id: The memory to share.
            agent_id: The agent sharing the memory.
            scope: Visibility scope for this share.

        Returns:
            True if shared, False if no write permission or capacity exceeded.

        Raises:
            PoolCapacityError: If shared memory limit is reached.
        """
        with self._rlock:
            # Check write permission
            if not self.check_access(pool_id, agent_id, PermissionModel.WRITE):
                self._log_event(
                    event_type="PERMISSION_DENIED",
                    agent_id=agent_id,
                    action="share_memory",
                    outcome="denied",
                    details={
                        "pool_id": pool_id,
                        "memory_id": memory_id,
                        "reason": "insufficient_permission",
                    },
                )
                return False

            # Check shared memory capacity (DoS prevention)
            current_count = len(self._shared_memories.get(pool_id, []))
            if current_count >= self._max_shared_memories_per_pool:
                self._log_event(
                    event_type="POOL_OPERATION",
                    agent_id=agent_id,
                    action="share_memory",
                    outcome="denied",
                    details={
                        "pool_id": pool_id,
                        "reason": "shared_memory_limit_exceeded",
                        "limit": self._max_shared_memories_per_pool,
                    },
                )
                raise PoolCapacityError(
                    "shared_memories_per_pool", self._max_shared_memories_per_pool
                )

            ref = SharedMemoryRef(
                memory_id=memory_id,
                shared_by=agent_id,
                scope=scope,
            )

            self._shared_memories[pool_id].append(ref)

            # Log success
            self._log_event(
                event_type="POOL_OPERATION",
                agent_id=agent_id,
                action="share_memory",
                outcome="success",
                details={"pool_id": pool_id, "memory_id": memory_id},
            )

            return True

    def get_shared_memories(self, pool_id: str) -> list[dict[str, Any]]:
        """Get all shared memories in a pool.

        Args:
            pool_id: The pool to query.

        Returns:
            List of shared memory references.
        """
        with self._rlock:
            refs = self._shared_memories.get(pool_id, [])
            return [
                {
                    "memory_id": r.memory_id,
                    "shared_by": r.shared_by,
                    "scope": str(r.scope),
                    "shared_at": r.shared_at.isoformat(),
                }
                for r in refs
            ]

    def query_shared(
        self,
        pool_id: str,
        agent_id: str,
        max_scope: SharedScope,
    ) -> list[dict[str, Any]]:
        """Query shared memories filtered by scope.

        Args:
            pool_id: The pool to query.
            agent_id: The agent querying.
            max_scope: Maximum scope the agent can access.

        Returns:
            List of accessible shared memory references.
        """
        with self._rlock:
            # Check read permission
            if not self.check_access(pool_id, agent_id, PermissionModel.READ):
                self._log_event(
                    event_type="PERMISSION_DENIED",
                    agent_id=agent_id,
                    action="query_shared",
                    outcome="denied",
                    details={"pool_id": pool_id, "reason": "insufficient_permission"},
                )
                return []

            refs = self._shared_memories.get(pool_id, [])
            results = [
                {
                    "memory_id": r.memory_id,
                    "shared_by": r.shared_by,
                    "scope": str(r.scope),
                    "shared_at": r.shared_at.isoformat(),
                }
                for r in refs
                if max_scope.can_access(r.scope)
            ]

            # Log cross-agent reads
            for result in results:
                if result["shared_by"] != agent_id:
                    self._log_event(
                        event_type="CROSS_AGENT_READ",
                        agent_id=agent_id,
                        action="query_shared",
                        outcome="success",
                        details={
                            "pool_id": pool_id,
                            "memory_id": result["memory_id"],
                            "shared_by": result["shared_by"],
                        },
                    )

            return results
