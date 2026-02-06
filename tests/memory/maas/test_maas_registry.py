# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for MaaS Agent Registry - ADR-003 Phase 4.2 (Issues #138-143).

TDD RED phase: Write tests first, then implement.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from luminescent_cluster.memory.maas.types import AgentCapability, AgentIdentity, AgentType


class TestAgentRegistrySingleton:
    """Test AgentRegistry singleton pattern."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_get_returns_singleton(self):
        """Verify get() always returns the same instance."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry1 = AgentRegistry.get()
        registry2 = AgentRegistry.get()

        assert registry1 is registry2

    def test_reset_creates_new_instance(self):
        """Verify reset() creates a new singleton."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry1 = AgentRegistry.get()
        AgentRegistry.reset()
        registry2 = AgentRegistry.get()

        assert registry1 is not registry2

    def test_singleton_thread_safety(self):
        """Verify singleton creation is thread-safe."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        instances = []

        def get_instance():
            instances.append(AgentRegistry.get())

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same object
        assert all(inst is instances[0] for inst in instances)


class TestAgentRegistration:
    """Test agent registration functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_register_agent(self):
        """Verify agent can be registered."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        assert agent_id is not None
        assert isinstance(agent_id, str)

    def test_register_agent_with_custom_id(self):
        """Verify agent can be registered with custom ID."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        custom_id = "my-custom-agent-id"

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            agent_id=custom_id,
        )

        assert agent_id == custom_id

    def test_register_agent_with_custom_capabilities(self):
        """Verify agent can be registered with custom capabilities."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CUSTOM_PIPELINE,
            owner_id="user-123",
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.MEMORY_WRITE},
        )

        agent = registry.get_agent(agent_id)
        assert AgentCapability.MEMORY_READ in agent.capabilities
        assert AgentCapability.MEMORY_WRITE in agent.capabilities

    def test_register_agent_uses_default_capabilities(self):
        """Verify default capabilities are used when not specified."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry
        from luminescent_cluster.memory.maas.types import get_default_capabilities

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        agent = registry.get_agent(agent_id)
        expected = get_default_capabilities(AgentType.CLAUDE_CODE)
        assert agent.capabilities == expected

    def test_register_agent_with_metadata(self):
        """Verify agent can be registered with metadata."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
            metadata={"model": "gpt-4", "temperature": 0.7},
        )

        agent = registry.get_agent(agent_id)
        assert agent.metadata["model"] == "gpt-4"
        assert agent.metadata["temperature"] == 0.7

    def test_duplicate_registration_raises(self):
        """Verify duplicate registration raises error."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry, DuplicateAgentError

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            agent_id="duplicate-id",
        )

        with pytest.raises(DuplicateAgentError):
            registry.register_agent(
                agent_type=AgentType.CLAUDE_CODE,
                owner_id="user-123",
                agent_id="duplicate-id",
            )


class TestAgentRetrieval:
    """Test agent retrieval functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_get_agent(self):
        """Verify agent can be retrieved by ID."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        agent = registry.get_agent(agent_id)

        assert agent is not None
        assert agent.id == agent_id
        assert agent.agent_type == AgentType.CLAUDE_CODE
        assert agent.owner_id == "user-123"

    def test_get_nonexistent_agent_returns_none(self):
        """Verify getting nonexistent agent returns None."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        agent = registry.get_agent("nonexistent-id")

        assert agent is None

    def test_get_agents_by_owner(self):
        """Verify agents can be retrieved by owner."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        # Register agents for different owners
        registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
        )
        registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-456",
        )

        agents = registry.get_agents_by_owner("user-123")

        assert len(agents) == 2
        assert all(a.owner_id == "user-123" for a in agents)

    def test_get_active_agents(self):
        """Verify only active agents are returned."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        # Register and deactivate one agent
        agent1_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        agent2_id = registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
        )
        registry.deactivate_agent(agent1_id)

        agents = registry.get_active_agents()

        assert len(agents) == 1
        assert agents[0].id == agent2_id


class TestAgentDeactivation:
    """Test agent deactivation functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_deactivate_agent(self):
        """Verify agent can be deactivated."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        result = registry.deactivate_agent(agent_id)

        assert result is True

    def test_deactivate_nonexistent_agent(self):
        """Verify deactivating nonexistent agent returns False."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        result = registry.deactivate_agent("nonexistent-id")

        assert result is False

    def test_deactivated_agent_not_in_active(self):
        """Verify deactivated agent is excluded from active agents."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        registry.deactivate_agent(agent_id)

        active = registry.get_active_agents()
        assert not any(a.id == agent_id for a in active)

    def test_is_agent_active(self):
        """Verify is_agent_active returns correct status."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        assert registry.is_agent_active(agent_id) is True

        registry.deactivate_agent(agent_id)

        assert registry.is_agent_active(agent_id) is False


class TestSessionManagement:
    """Test session management functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_start_session(self):
        """Verify session can be started for an agent."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        session_id = registry.start_session(agent_id)

        assert session_id is not None
        assert isinstance(session_id, str)

    def test_start_session_updates_agent(self):
        """Verify starting session updates agent's session_id."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        session_id = registry.start_session(agent_id)
        agent = registry.get_agent(agent_id)

        assert agent.session_id == session_id

    def test_start_session_nonexistent_agent(self):
        """Verify starting session for nonexistent agent returns None."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        session_id = registry.start_session("nonexistent-id")

        assert session_id is None

    def test_end_session(self):
        """Verify session can be ended."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        registry.start_session(agent_id)
        result = registry.end_session(agent_id)

        assert result is True

    def test_end_session_clears_session_id(self):
        """Verify ending session clears agent's session_id."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        registry.start_session(agent_id)
        registry.end_session(agent_id)

        agent = registry.get_agent(agent_id)
        assert agent.session_id is None

    def test_get_session(self):
        """Verify session info can be retrieved."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        session_id = registry.start_session(agent_id)

        session = registry.get_session(session_id)

        assert session is not None
        assert session["session_id"] == session_id
        assert session["agent_id"] == agent_id

    def test_get_nonexistent_session(self):
        """Verify getting nonexistent session returns None."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        session = registry.get_session("nonexistent-session")

        assert session is None


class TestRegistryMetrics:
    """Test registry metrics and statistics."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_get_stats(self):
        """Verify registry stats are returned correctly."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        # Register some agents
        agent1_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )
        registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-456",
        )
        registry.deactivate_agent(agent1_id)

        stats = registry.get_stats()

        assert stats["total_agents"] == 2
        assert stats["active_agents"] == 1
        assert stats["agents_by_type"][AgentType.CLAUDE_CODE] == 1
        assert stats["agents_by_type"][AgentType.GPT_AGENT] == 1

    def test_agent_count(self):
        """Verify agent count is accurate."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()

        assert registry.agent_count() == 0

        registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        assert registry.agent_count() == 1


class TestThreadSafety:
    """Test thread safety of registry operations."""

    def setup_method(self):
        """Reset registry before each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def teardown_method(self):
        """Reset registry after each test."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()

    def test_concurrent_registration(self):
        """Verify concurrent registration is thread-safe."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        registered_ids = []
        lock = threading.Lock()

        def register_agent(i):
            agent_id = registry.register_agent(
                agent_type=AgentType.CLAUDE_CODE,
                owner_id=f"user-{i}",
            )
            with lock:
                registered_ids.append(agent_id)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(register_agent, range(100)))

        # All 100 agents should be registered
        assert len(registered_ids) == 100
        assert len(set(registered_ids)) == 100  # All IDs unique

    def test_concurrent_read_write(self):
        """Verify concurrent reads and writes are thread-safe."""
        from luminescent_cluster.memory.maas.registry import AgentRegistry

        registry = AgentRegistry.get()
        errors = []

        # Pre-register some agents
        agent_ids = [
            registry.register_agent(
                agent_type=AgentType.CLAUDE_CODE,
                owner_id=f"user-{i}",
            )
            for i in range(10)
        ]

        def reader():
            try:
                for _ in range(50):
                    for agent_id in agent_ids:
                        registry.get_agent(agent_id)
                    registry.get_active_agents()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    agent_id = registry.register_agent(
                        agent_type=AgentType.GPT_AGENT,
                        owner_id=f"writer-{i}",
                    )
                    registry.start_session(agent_id)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader) for _ in range(3)
        ] + [
            threading.Thread(target=writer) for _ in range(2)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
