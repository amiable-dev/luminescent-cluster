# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for MaaS Shared Memory Pools - ADR-003 Phase 4.2 (Issues #144-149).

TDD RED phase: Write tests first, then implement.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from src.memory.maas.registry import AgentRegistry
from src.memory.maas.scope import PermissionModel, SharedScope
from src.memory.maas.types import AgentCapability, AgentIdentity, AgentType


class TestSharedMemoryPoolCreation:
    """Test pool creation functionality."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_create_pool(self):
        """Verify pool can be created."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        assert pool_id is not None
        assert isinstance(pool_id, str)

    def test_create_pool_with_custom_id(self):
        """Verify pool can be created with custom ID."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
            pool_id="custom-pool-id",
        )

        assert pool_id == "custom-pool-id"

    def test_create_pool_with_metadata(self):
        """Verify pool can be created with metadata."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
            metadata={"project_id": "proj-456"},
        )

        pool = registry.get_pool(pool_id)
        assert pool.metadata["project_id"] == "proj-456"

    def test_duplicate_pool_raises(self):
        """Verify duplicate pool creation raises error."""
        from src.memory.maas.pool import DuplicatePoolError, PoolRegistry

        registry = PoolRegistry.get()

        registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
            pool_id="duplicate-id",
        )

        with pytest.raises(DuplicatePoolError):
            registry.create_pool(
                name="another-pool",
                owner_id="user-123",
                scope=SharedScope.PROJECT,
                pool_id="duplicate-id",
            )


class TestPoolMembership:
    """Test pool membership management."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

        # Create a test agent
        self.agent_registry = AgentRegistry.get()
        self.agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_join_pool(self):
        """Verify agent can join a pool."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        result = registry.join_pool(pool_id, self.agent_id, PermissionModel.READ)

        assert result is True

    def test_join_pool_as_owner_gets_admin(self):
        """Verify pool owner automatically has ADMIN permission."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",  # Same as agent owner
            scope=SharedScope.PROJECT,
        )

        # Owner should be able to join with any permission
        # but internally gets ADMIN
        result = registry.join_pool(pool_id, self.agent_id, PermissionModel.READ)
        assert result is True

        # Check they have ADMIN permission
        assert registry.get_member_permission(pool_id, self.agent_id) == PermissionModel.ADMIN

    def test_join_nonexistent_pool(self):
        """Verify joining nonexistent pool returns False."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()
        result = registry.join_pool("nonexistent-pool", self.agent_id, PermissionModel.READ)

        assert result is False

    def test_join_pool_nonexistent_agent(self):
        """Verify joining pool with nonexistent agent returns False."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        # Try to join with a non-existent agent ID
        result = registry.join_pool(pool_id, "fake-agent-id", PermissionModel.READ)

        assert result is False

    def test_leave_pool(self):
        """Verify agent can leave a pool."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-456",  # Different owner
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.READ)

        result = registry.leave_pool(pool_id, self.agent_id)

        assert result is True

    def test_leave_pool_not_member(self):
        """Verify leaving pool when not a member returns False."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        result = registry.leave_pool(pool_id, "not-a-member")

        assert result is False

    def test_get_pool_members(self):
        """Verify pool members can be retrieved."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-456",
            scope=SharedScope.PROJECT,
        )

        # Create another agent and join
        agent2_id = self.agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-456",
        )

        registry.join_pool(pool_id, self.agent_id, PermissionModel.READ)
        registry.join_pool(pool_id, agent2_id, PermissionModel.WRITE)

        members = registry.get_pool_members(pool_id)

        assert len(members) == 2
        assert any(m["agent_id"] == self.agent_id for m in members)
        assert any(m["agent_id"] == agent2_id for m in members)

    def test_get_agent_pools(self):
        """Verify agent's pools can be retrieved."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool1_id = registry.create_pool(
            name="pool-1",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )
        pool2_id = registry.create_pool(
            name="pool-2",
            owner_id="user-123",
            scope=SharedScope.TEAM,
        )

        registry.join_pool(pool1_id, self.agent_id, PermissionModel.READ)
        registry.join_pool(pool2_id, self.agent_id, PermissionModel.WRITE)

        pools = registry.get_agent_pools(self.agent_id)

        assert len(pools) == 2


class TestPoolAccess:
    """Test pool access control."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

        self.agent_registry = AgentRegistry.get()
        self.agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_check_access_read(self):
        """Verify read access checking."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-456",
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.READ)

        assert registry.check_access(pool_id, self.agent_id, PermissionModel.READ) is True
        assert registry.check_access(pool_id, self.agent_id, PermissionModel.WRITE) is False

    def test_check_access_write_includes_read(self):
        """Verify write permission includes read."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-456",
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.WRITE)

        assert registry.check_access(pool_id, self.agent_id, PermissionModel.READ) is True
        assert registry.check_access(pool_id, self.agent_id, PermissionModel.WRITE) is True
        assert registry.check_access(pool_id, self.agent_id, PermissionModel.ADMIN) is False

    def test_check_access_admin_includes_all(self):
        """Verify admin permission includes all."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",  # Same owner as agent
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.ADMIN)

        assert registry.check_access(pool_id, self.agent_id, PermissionModel.READ) is True
        assert registry.check_access(pool_id, self.agent_id, PermissionModel.WRITE) is True
        assert registry.check_access(pool_id, self.agent_id, PermissionModel.ADMIN) is True

    def test_check_access_non_member(self):
        """Verify non-members have no access."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        assert registry.check_access(pool_id, "not-a-member", PermissionModel.READ) is False


class TestPoolLifecycle:
    """Test pool lifecycle management."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_archive_pool(self):
        """Verify pool can be archived."""
        from src.memory.maas.pool import PoolRegistry, PoolStatus

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        result = registry.archive_pool(pool_id)

        assert result is True
        pool = registry.get_pool(pool_id)
        assert pool.status == PoolStatus.ARCHIVED

    def test_archived_pool_not_in_active(self):
        """Verify archived pool is excluded from active pools."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )
        registry.archive_pool(pool_id)

        active = registry.get_active_pools()
        assert not any(p.id == pool_id for p in active)

    def test_delete_pool(self):
        """Verify pool can be deleted."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        result = registry.delete_pool(pool_id)

        assert result is True
        assert registry.get_pool(pool_id) is None


class TestPoolMemorySharing:
    """Test memory sharing within pools."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

        self.agent_registry = AgentRegistry.get()
        self.agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.MEMORY_WRITE},
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_share_memory_to_pool(self):
        """Verify memory can be shared to a pool."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.WRITE)

        memory_id = "mem-123"
        result = registry.share_memory(
            pool_id=pool_id,
            memory_id=memory_id,
            agent_id=self.agent_id,
            scope=SharedScope.PROJECT,
        )

        assert result is True

    def test_share_memory_requires_write_permission(self):
        """Verify sharing memory requires write permission."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-456",
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.READ)

        result = registry.share_memory(
            pool_id=pool_id,
            memory_id="mem-123",
            agent_id=self.agent_id,
            scope=SharedScope.PROJECT,
        )

        assert result is False

    def test_get_shared_memories(self):
        """Verify shared memories can be retrieved."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.WRITE)

        registry.share_memory(pool_id, "mem-1", self.agent_id, SharedScope.PROJECT)
        registry.share_memory(pool_id, "mem-2", self.agent_id, SharedScope.PROJECT)

        memories = registry.get_shared_memories(pool_id)

        assert len(memories) == 2
        assert "mem-1" in [m["memory_id"] for m in memories]
        assert "mem-2" in [m["memory_id"] for m in memories]

    def test_query_pool_memories(self):
        """Verify pool memories can be queried by scope."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()

        pool_id = registry.create_pool(
            name="test-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )
        registry.join_pool(pool_id, self.agent_id, PermissionModel.WRITE)

        registry.share_memory(pool_id, "mem-1", self.agent_id, SharedScope.USER)
        registry.share_memory(pool_id, "mem-2", self.agent_id, SharedScope.PROJECT)

        # Query with USER scope should only get USER-scoped memories
        reader_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
        )
        registry.join_pool(pool_id, reader_agent_id, PermissionModel.READ)

        memories = registry.query_shared(
            pool_id=pool_id,
            agent_id=reader_agent_id,
            max_scope=SharedScope.USER,
        )

        assert len(memories) == 1
        assert memories[0]["memory_id"] == "mem-1"


class TestPoolThreadSafety:
    """Test thread safety of pool operations."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()

    def test_concurrent_pool_creation(self):
        """Verify concurrent pool creation is thread-safe."""
        from src.memory.maas.pool import PoolRegistry

        registry = PoolRegistry.get()
        created_ids = []
        lock = threading.Lock()

        def create_pool(i):
            pool_id = registry.create_pool(
                name=f"pool-{i}",
                owner_id=f"user-{i}",
                scope=SharedScope.PROJECT,
            )
            with lock:
                created_ids.append(pool_id)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(create_pool, range(50)))

        assert len(created_ids) == 50
        assert len(set(created_ids)) == 50  # All IDs unique

    def test_concurrent_membership(self):
        """Verify concurrent membership operations are thread-safe."""
        from src.memory.maas.pool import PoolRegistry

        agent_registry = AgentRegistry.get()
        pool_registry = PoolRegistry.get()

        pool_id = pool_registry.create_pool(
            name="concurrent-pool",
            owner_id="user-123",
            scope=SharedScope.PROJECT,
        )

        errors = []

        def join_and_leave(i):
            try:
                agent_id = agent_registry.register_agent(
                    agent_type=AgentType.CLAUDE_CODE,
                    owner_id=f"user-{i}",
                )
                pool_registry.join_pool(pool_id, agent_id, PermissionModel.READ)
                pool_registry.leave_pool(pool_id, agent_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(join_and_leave, range(100)))

        assert len(errors) == 0
