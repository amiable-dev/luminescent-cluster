# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for MaaS core types - ADR-003 Phase 4.2 (Issues #132-137).

TDD RED phase: Write tests first, then implement.
"""

import uuid
from datetime import datetime, timezone

import pytest


class TestAgentType:
    """Test AgentType enum."""

    def test_agent_types_exist(self):
        """Verify all required agent types are defined."""
        from luminescent_cluster.memory.maas.types import AgentType

        assert hasattr(AgentType, "CLAUDE_CODE")
        assert hasattr(AgentType, "GPT_AGENT")
        assert hasattr(AgentType, "CUSTOM_PIPELINE")
        assert hasattr(AgentType, "HUMAN")

    def test_agent_type_values(self):
        """Verify agent type string values."""
        from luminescent_cluster.memory.maas.types import AgentType

        assert AgentType.CLAUDE_CODE.value == "claude_code"
        assert AgentType.GPT_AGENT.value == "gpt_agent"
        assert AgentType.CUSTOM_PIPELINE.value == "custom_pipeline"
        assert AgentType.HUMAN.value == "human"

    def test_agent_type_is_str_enum(self):
        """Verify AgentType is string-compatible."""
        from luminescent_cluster.memory.maas.types import AgentType

        # Should be usable as a string
        assert str(AgentType.CLAUDE_CODE) == "claude_code"


class TestAgentCapability:
    """Test AgentCapability enum."""

    def test_memory_capabilities_exist(self):
        """Verify memory-related capabilities."""
        from luminescent_cluster.memory.maas.types import AgentCapability

        assert hasattr(AgentCapability, "MEMORY_READ")
        assert hasattr(AgentCapability, "MEMORY_WRITE")
        assert hasattr(AgentCapability, "MEMORY_DELETE")

    def test_kb_capabilities_exist(self):
        """Verify knowledge base capabilities."""
        from luminescent_cluster.memory.maas.types import AgentCapability

        assert hasattr(AgentCapability, "KB_SEARCH")
        assert hasattr(AgentCapability, "DECISION_READ")
        assert hasattr(AgentCapability, "INCIDENT_READ")

    def test_handoff_capabilities_exist(self):
        """Verify handoff-related capabilities."""
        from luminescent_cluster.memory.maas.types import AgentCapability

        assert hasattr(AgentCapability, "HANDOFF_INITIATE")
        assert hasattr(AgentCapability, "HANDOFF_RECEIVE")

    def test_capability_values(self):
        """Verify capability string values."""
        from luminescent_cluster.memory.maas.types import AgentCapability

        assert AgentCapability.MEMORY_READ.value == "memory_read"
        assert AgentCapability.MEMORY_WRITE.value == "memory_write"
        assert AgentCapability.KB_SEARCH.value == "kb_search"


class TestSharedScope:
    """Test SharedScope enum for visibility levels."""

    def test_scope_hierarchy_exists(self):
        """Verify all scope levels are defined."""
        from luminescent_cluster.memory.maas.scope import SharedScope

        assert hasattr(SharedScope, "AGENT_PRIVATE")
        assert hasattr(SharedScope, "USER")
        assert hasattr(SharedScope, "PROJECT")
        assert hasattr(SharedScope, "TEAM")
        assert hasattr(SharedScope, "GLOBAL")

    def test_scope_values(self):
        """Verify scope string values."""
        from luminescent_cluster.memory.maas.scope import SharedScope

        assert SharedScope.AGENT_PRIVATE.value == "agent_private"
        assert SharedScope.USER.value == "user"
        assert SharedScope.PROJECT.value == "project"
        assert SharedScope.TEAM.value == "team"
        assert SharedScope.GLOBAL.value == "global"

    def test_scope_ordering(self):
        """Verify scope hierarchy ordering."""
        from luminescent_cluster.memory.maas.scope import SharedScope

        # Ordering: AGENT_PRIVATE < USER < PROJECT < TEAM < GLOBAL
        assert SharedScope.AGENT_PRIVATE.level < SharedScope.USER.level
        assert SharedScope.USER.level < SharedScope.PROJECT.level
        assert SharedScope.PROJECT.level < SharedScope.TEAM.level
        assert SharedScope.TEAM.level < SharedScope.GLOBAL.level

    def test_scope_comparison(self):
        """Verify scopes can be compared."""
        from luminescent_cluster.memory.maas.scope import SharedScope

        assert SharedScope.USER.can_access(SharedScope.USER)
        assert SharedScope.PROJECT.can_access(SharedScope.USER)
        assert not SharedScope.USER.can_access(SharedScope.PROJECT)


class TestAgentIdentity:
    """Test AgentIdentity dataclass."""

    def test_agent_identity_creation(self):
        """Verify AgentIdentity can be created with required fields."""
        from luminescent_cluster.memory.maas.types import AgentCapability, AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-001",
            agent_type=AgentType.CLAUDE_CODE,
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.KB_SEARCH},
            owner_id="user-123",
        )

        assert identity.id == "agent-001"
        assert identity.agent_type == AgentType.CLAUDE_CODE
        assert AgentCapability.MEMORY_READ in identity.capabilities
        assert identity.owner_id == "user-123"

    def test_agent_identity_defaults(self):
        """Verify AgentIdentity defaults are set correctly."""
        from luminescent_cluster.memory.maas.types import AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-002",
            agent_type=AgentType.GPT_AGENT,
            owner_id="user-456",
        )

        assert identity.capabilities == set()
        assert identity.metadata == {}
        assert identity.session_id is None
        assert isinstance(identity.created_at, datetime)

    def test_agent_identity_with_metadata(self):
        """Verify AgentIdentity can store arbitrary metadata."""
        from luminescent_cluster.memory.maas.types import AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-003",
            agent_type=AgentType.CUSTOM_PIPELINE,
            owner_id="user-789",
            metadata={"model": "gpt-4", "temperature": 0.7},
        )

        assert identity.metadata["model"] == "gpt-4"
        assert identity.metadata["temperature"] == 0.7

    def test_agent_identity_with_session(self):
        """Verify AgentIdentity can track session."""
        from luminescent_cluster.memory.maas.types import AgentIdentity, AgentType

        session_id = str(uuid.uuid4())
        identity = AgentIdentity(
            id="agent-004",
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
            session_id=session_id,
        )

        assert identity.session_id == session_id

    def test_agent_identity_has_capability(self):
        """Verify capability checking method."""
        from luminescent_cluster.memory.maas.types import AgentCapability, AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-005",
            agent_type=AgentType.CLAUDE_CODE,
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.MEMORY_WRITE},
            owner_id="user-123",
        )

        assert identity.has_capability(AgentCapability.MEMORY_READ)
        assert identity.has_capability(AgentCapability.MEMORY_WRITE)
        assert not identity.has_capability(AgentCapability.KB_SEARCH)

    def test_agent_identity_to_dict(self):
        """Verify serialization to dict."""
        from luminescent_cluster.memory.maas.types import AgentCapability, AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-006",
            agent_type=AgentType.CLAUDE_CODE,
            capabilities={AgentCapability.MEMORY_READ},
            owner_id="user-123",
        )

        data = identity.to_dict()

        assert data["id"] == "agent-006"
        assert data["agent_type"] == "claude_code"
        assert "memory_read" in data["capabilities"]
        assert data["owner_id"] == "user-123"

    def test_agent_identity_from_dict(self):
        """Verify deserialization from dict."""
        from luminescent_cluster.memory.maas.types import AgentCapability, AgentIdentity, AgentType

        data = {
            "id": "agent-007",
            "agent_type": "claude_code",
            "capabilities": ["memory_read", "kb_search"],
            "owner_id": "user-123",
            "metadata": {"key": "value"},
            "session_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        identity = AgentIdentity.from_dict(data)

        assert identity.id == "agent-007"
        assert identity.agent_type == AgentType.CLAUDE_CODE
        assert AgentCapability.MEMORY_READ in identity.capabilities
        assert identity.metadata["key"] == "value"


class TestDefaultCapabilities:
    """Test default capability assignments by agent type."""

    def test_claude_code_defaults(self):
        """Verify Claude Code agents get appropriate defaults."""
        from luminescent_cluster.memory.maas.types import (
            AgentCapability,
            AgentType,
            get_default_capabilities,
        )

        caps = get_default_capabilities(AgentType.CLAUDE_CODE)

        assert AgentCapability.MEMORY_READ in caps
        assert AgentCapability.MEMORY_WRITE in caps
        assert AgentCapability.KB_SEARCH in caps
        assert AgentCapability.HANDOFF_INITIATE in caps
        assert AgentCapability.HANDOFF_RECEIVE in caps

    def test_gpt_agent_defaults(self):
        """Verify GPT agents get appropriate defaults."""
        from luminescent_cluster.memory.maas.types import (
            AgentCapability,
            AgentType,
            get_default_capabilities,
        )

        caps = get_default_capabilities(AgentType.GPT_AGENT)

        assert AgentCapability.MEMORY_READ in caps
        assert AgentCapability.MEMORY_WRITE in caps
        assert AgentCapability.KB_SEARCH in caps
        assert AgentCapability.HANDOFF_INITIATE in caps
        assert AgentCapability.HANDOFF_RECEIVE in caps

    def test_custom_pipeline_defaults(self):
        """Verify custom pipelines get restricted defaults."""
        from luminescent_cluster.memory.maas.types import (
            AgentCapability,
            AgentType,
            get_default_capabilities,
        )

        caps = get_default_capabilities(AgentType.CUSTOM_PIPELINE)

        assert AgentCapability.MEMORY_READ in caps
        assert AgentCapability.KB_SEARCH in caps
        # Should not have write or handoff by default
        assert AgentCapability.MEMORY_WRITE not in caps
        assert AgentCapability.HANDOFF_INITIATE not in caps

    def test_human_defaults(self):
        """Verify human agents get full capabilities."""
        from luminescent_cluster.memory.maas.types import (
            AgentCapability,
            AgentType,
            get_default_capabilities,
        )

        caps = get_default_capabilities(AgentType.HUMAN)

        # Humans should have all capabilities
        assert AgentCapability.MEMORY_READ in caps
        assert AgentCapability.MEMORY_WRITE in caps
        assert AgentCapability.MEMORY_DELETE in caps
        assert AgentCapability.KB_SEARCH in caps


class TestPermissionScope:
    """Test permission scopes for pool access control."""

    def test_permission_model_exists(self):
        """Verify PermissionModel enum exists."""
        from luminescent_cluster.memory.maas.scope import PermissionModel

        assert hasattr(PermissionModel, "READ")
        assert hasattr(PermissionModel, "WRITE")
        assert hasattr(PermissionModel, "ADMIN")

    def test_permission_hierarchy(self):
        """Verify permission hierarchy."""
        from luminescent_cluster.memory.maas.scope import PermissionModel

        # ADMIN includes WRITE includes READ
        assert PermissionModel.ADMIN.includes(PermissionModel.WRITE)
        assert PermissionModel.ADMIN.includes(PermissionModel.READ)
        assert PermissionModel.WRITE.includes(PermissionModel.READ)
        assert not PermissionModel.READ.includes(PermissionModel.WRITE)


class TestAgentScope:
    """Test AgentScope combining identity with visibility."""

    def test_agent_scope_creation(self):
        """Verify AgentScope can be created."""
        from luminescent_cluster.memory.maas.scope import AgentScope, SharedScope
        from luminescent_cluster.memory.maas.types import AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-001",
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        scope = AgentScope(
            agent=identity,
            visibility=SharedScope.PROJECT,
            project_id="proj-456",
        )

        assert scope.agent == identity
        assert scope.visibility == SharedScope.PROJECT
        assert scope.project_id == "proj-456"

    def test_agent_scope_can_read_from(self):
        """Verify scope-based read access checking."""
        from luminescent_cluster.memory.maas.scope import AgentScope, SharedScope
        from luminescent_cluster.memory.maas.types import AgentCapability, AgentIdentity, AgentType

        reader = AgentIdentity(
            id="reader-001",
            agent_type=AgentType.CLAUDE_CODE,
            capabilities={AgentCapability.MEMORY_READ},
            owner_id="user-123",
        )

        reader_scope = AgentScope(
            agent=reader,
            visibility=SharedScope.PROJECT,
            project_id="proj-456",
        )

        # Can read user-scoped data
        assert reader_scope.can_read_from(SharedScope.USER)
        # Can read project-scoped data in same project
        assert reader_scope.can_read_from(SharedScope.PROJECT)
        # Cannot read team-scoped data (higher visibility)
        assert not reader_scope.can_read_from(SharedScope.TEAM)

    def test_agent_scope_to_dict(self):
        """Verify AgentScope serialization."""
        from luminescent_cluster.memory.maas.scope import AgentScope, SharedScope
        from luminescent_cluster.memory.maas.types import AgentIdentity, AgentType

        identity = AgentIdentity(
            id="agent-001",
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

        scope = AgentScope(
            agent=identity,
            visibility=SharedScope.USER,
        )

        data = scope.to_dict()

        assert "agent" in data
        assert data["visibility"] == "user"
