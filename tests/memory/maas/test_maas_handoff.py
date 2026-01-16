# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for MaaS Agent Handoff - ADR-003 Phase 4.2 (Issues #156-161).

TDD RED phase: Write tests first, then implement.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from src.memory.maas.registry import AgentRegistry
from src.memory.maas.types import AgentCapability, AgentType


class TestHandoffContext:
    """Test HandoffContext dataclass."""

    def test_handoff_context_creation(self):
        """Verify HandoffContext can be created."""
        from src.memory.maas.handoff import HandoffContext

        context = HandoffContext(
            task_description="Complete the authentication flow",
            current_state={"step": 2, "total_steps": 5},
            relevant_memories=["mem-1", "mem-2"],
            relevant_files=["auth.py", "config.yaml"],
        )

        assert context.task_description == "Complete the authentication flow"
        assert context.current_state["step"] == 2
        assert "mem-1" in context.relevant_memories
        assert "auth.py" in context.relevant_files

    def test_handoff_context_defaults(self):
        """Verify HandoffContext has sensible defaults."""
        from src.memory.maas.handoff import HandoffContext

        context = HandoffContext(
            task_description="Simple task",
        )

        assert context.current_state == {}
        assert context.relevant_memories == []
        assert context.relevant_files == []

    def test_handoff_context_to_dict(self):
        """Verify HandoffContext serialization."""
        from src.memory.maas.handoff import HandoffContext

        context = HandoffContext(
            task_description="Test task",
            current_state={"key": "value"},
            relevant_memories=["mem-1"],
            relevant_files=["file.py"],
        )

        data = context.to_dict()

        assert data["task_description"] == "Test task"
        assert data["current_state"]["key"] == "value"
        assert "mem-1" in data["relevant_memories"]

    def test_handoff_context_from_dict(self):
        """Verify HandoffContext deserialization."""
        from src.memory.maas.handoff import HandoffContext

        data = {
            "task_description": "Test task",
            "current_state": {"key": "value"},
            "relevant_memories": ["mem-1"],
            "relevant_files": ["file.py"],
        }

        context = HandoffContext.from_dict(data)

        assert context.task_description == "Test task"
        assert context.current_state["key"] == "value"


class TestHandoffStatus:
    """Test HandoffStatus enum."""

    def test_status_values(self):
        """Verify all status values exist."""
        from src.memory.maas.handoff import HandoffStatus

        assert hasattr(HandoffStatus, "PENDING")
        assert hasattr(HandoffStatus, "ACCEPTED")
        assert hasattr(HandoffStatus, "REJECTED")
        assert hasattr(HandoffStatus, "COMPLETED")
        assert hasattr(HandoffStatus, "EXPIRED")


class TestHandoffCreation:
    """Test handoff creation functionality."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

        # Create test agents
        self.agent_registry = AgentRegistry.get()
        self.source_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            capabilities={
                AgentCapability.MEMORY_READ,
                AgentCapability.HANDOFF_INITIATE,
            },
        )
        self.target_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
            capabilities={
                AgentCapability.MEMORY_READ,
                AgentCapability.HANDOFF_RECEIVE,
            },
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

    def test_initiate_handoff(self):
        """Verify handoff can be initiated."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(
            task_description="Complete the task",
        )

        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )

        assert handoff_id is not None
        assert isinstance(handoff_id, str)

    def test_initiate_handoff_requires_capability(self):
        """Verify initiating handoff requires HANDOFF_INITIATE capability."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        # Create agent without HANDOFF_INITIATE
        no_cap_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CUSTOM_PIPELINE,
            owner_id="user-456",
            capabilities={AgentCapability.MEMORY_READ},
        )

        context = HandoffContext(task_description="Test")

        handoff_id = manager.initiate_handoff(
            source_agent_id=no_cap_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )

        assert handoff_id is None

    def test_initiate_handoff_target_requires_receive(self):
        """Verify target must have HANDOFF_RECEIVE capability."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        # Create target without HANDOFF_RECEIVE
        no_receive_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CUSTOM_PIPELINE,
            owner_id="user-456",
            capabilities={AgentCapability.MEMORY_READ},
        )

        context = HandoffContext(task_description="Test")

        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=no_receive_agent_id,
            context=context,
        )

        assert handoff_id is None


class TestHandoffLifecycle:
    """Test handoff lifecycle management."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

        self.agent_registry = AgentRegistry.get()
        self.source_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.HANDOFF_INITIATE},
        )
        self.target_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.HANDOFF_RECEIVE},
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

    def test_accept_handoff(self):
        """Verify handoff can be accepted."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager, HandoffStatus

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )

        result = manager.accept_handoff(handoff_id, self.target_agent_id)

        assert result is True
        handoff = manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.ACCEPTED

    def test_accept_handoff_wrong_agent(self):
        """Verify only target agent can accept."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )

        # Try to accept as source agent (wrong agent)
        result = manager.accept_handoff(handoff_id, self.source_agent_id)

        assert result is False

    def test_reject_handoff(self):
        """Verify handoff can be rejected."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager, HandoffStatus

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )

        result = manager.reject_handoff(handoff_id, self.target_agent_id, reason="Too busy")

        assert result is True
        handoff = manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.REJECTED
        assert handoff.rejection_reason == "Too busy"

    def test_complete_handoff(self):
        """Verify handoff can be completed."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager, HandoffStatus

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )
        manager.accept_handoff(handoff_id, self.target_agent_id)

        result = manager.complete_handoff(
            handoff_id,
            self.target_agent_id,
            result={"status": "success"},
        )

        assert result is True
        handoff = manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.COMPLETED
        assert handoff.result["status"] == "success"

    def test_complete_requires_accepted(self):
        """Verify handoff must be accepted before completion."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
        )

        # Try to complete without accepting
        result = manager.complete_handoff(handoff_id, self.target_agent_id, result={})

        assert result is False


class TestHandoffQueries:
    """Test handoff query functionality."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

        self.agent_registry = AgentRegistry.get()
        self.agent1_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            capabilities={
                AgentCapability.MEMORY_READ,
                AgentCapability.HANDOFF_INITIATE,
                AgentCapability.HANDOFF_RECEIVE,
            },
        )
        self.agent2_id = self.agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
            capabilities={
                AgentCapability.MEMORY_READ,
                AgentCapability.HANDOFF_INITIATE,
                AgentCapability.HANDOFF_RECEIVE,
            },
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

    def test_get_pending_handoffs(self):
        """Verify pending handoffs can be retrieved."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        manager.initiate_handoff(
            source_agent_id=self.agent1_id,
            target_agent_id=self.agent2_id,
            context=context,
        )
        manager.initiate_handoff(
            source_agent_id=self.agent1_id,
            target_agent_id=self.agent2_id,
            context=context,
        )

        pending = manager.get_pending_handoffs(self.agent2_id)

        assert len(pending) == 2

    def test_get_handoffs_by_agent(self):
        """Verify handoffs can be retrieved by agent."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        manager.initiate_handoff(
            source_agent_id=self.agent1_id,
            target_agent_id=self.agent2_id,
            context=context,
        )

        # Get handoffs where agent1 is source
        handoffs = manager.get_handoffs_by_agent(self.agent1_id, as_source=True)
        assert len(handoffs) == 1

        # Get handoffs where agent1 is target (none)
        handoffs = manager.get_handoffs_by_agent(self.agent1_id, as_source=False)
        assert len(handoffs) == 0

    def test_get_handoff(self):
        """Verify handoff can be retrieved by ID."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.agent1_id,
            target_agent_id=self.agent2_id,
            context=context,
        )

        handoff = manager.get_handoff(handoff_id)

        assert handoff is not None
        assert handoff.id == handoff_id
        assert handoff.source_agent_id == self.agent1_id
        assert handoff.target_agent_id == self.agent2_id

    def test_get_nonexistent_handoff(self):
        """Verify getting nonexistent handoff returns None."""
        from src.memory.maas.handoff import HandoffManager

        manager = HandoffManager.get()
        handoff = manager.get_handoff("nonexistent-id")

        assert handoff is None


class TestHandoffExpiration:
    """Test handoff expiration functionality."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

        self.agent_registry = AgentRegistry.get()
        self.source_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.HANDOFF_INITIATE},
        )
        self.target_agent_id = self.agent_registry.register_agent(
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-123",
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.HANDOFF_RECEIVE},
        )

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

    def test_handoff_with_ttl(self):
        """Verify handoff can have TTL."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
            ttl_seconds=3600,  # 1 hour
        )

        handoff = manager.get_handoff(handoff_id)
        assert handoff.expires_at is not None

    def test_expire_old_handoffs(self):
        """Verify expired handoffs are marked as expired."""
        from src.memory.maas.handoff import (
            HandoffContext,
            HandoffManager,
            HandoffStatus,
        )

        manager = HandoffManager.get()

        context = HandoffContext(task_description="Test")
        handoff_id = manager.initiate_handoff(
            source_agent_id=self.source_agent_id,
            target_agent_id=self.target_agent_id,
            context=context,
            ttl_seconds=0,  # Expire immediately
        )

        # Run expiration check
        time.sleep(0.01)  # Small delay to ensure expiration
        expired_count = manager.expire_old_handoffs()

        handoff = manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.EXPIRED
        assert expired_count >= 1


class TestHandoffThreadSafety:
    """Test thread safety of handoff operations."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        HandoffManager.reset()

    def test_concurrent_handoff_operations(self):
        """Verify concurrent handoff operations are thread-safe."""
        from src.memory.maas.handoff import HandoffContext, HandoffManager

        agent_registry = AgentRegistry.get()
        handoff_manager = HandoffManager.get()

        errors = []
        handoff_ids = []
        lock = threading.Lock()

        def create_and_process_handoff(i):
            try:
                # Create unique agents for each thread
                source_id = agent_registry.register_agent(
                    agent_type=AgentType.CLAUDE_CODE,
                    owner_id=f"user-{i}",
                    capabilities={AgentCapability.HANDOFF_INITIATE, AgentCapability.MEMORY_READ},
                )
                target_id = agent_registry.register_agent(
                    agent_type=AgentType.GPT_AGENT,
                    owner_id=f"user-{i}",
                    capabilities={AgentCapability.HANDOFF_RECEIVE, AgentCapability.MEMORY_READ},
                )

                context = HandoffContext(task_description=f"Task {i}")
                handoff_id = handoff_manager.initiate_handoff(
                    source_agent_id=source_id,
                    target_agent_id=target_id,
                    context=context,
                )

                if handoff_id:
                    handoff_manager.accept_handoff(handoff_id, target_id)
                    handoff_manager.complete_handoff(handoff_id, target_id, result={})
                    with lock:
                        handoff_ids.append(handoff_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(create_and_process_handoff, range(50)))

        assert len(errors) == 0
        assert len(handoff_ids) == 50
