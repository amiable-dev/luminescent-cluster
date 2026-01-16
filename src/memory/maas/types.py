# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS Core Types - ADR-003 Phase 4.2 (Issues #132-137).

Defines the fundamental types for multi-agent collaboration:
- AgentType: Enum of supported agent types
- AgentCapability: Enum of agent permissions/capabilities
- AgentIdentity: Dataclass for agent identity with capabilities
- get_default_capabilities: Default capability sets by agent type
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AgentType(str, Enum):
    """Types of agents that can participate in MaaS.

    Agent types determine default capabilities and trust levels:
    - CLAUDE_CODE: Anthropic's Claude Code agent (high trust)
    - GPT_AGENT: OpenAI GPT-based agents (high trust)
    - CUSTOM_PIPELINE: User-defined automation pipelines (limited trust)
    - HUMAN: Human operators (full trust, audit required)
    """

    CLAUDE_CODE = "claude_code"
    GPT_AGENT = "gpt_agent"
    CUSTOM_PIPELINE = "custom_pipeline"
    HUMAN = "human"

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value


class AgentCapability(str, Enum):
    """Capabilities that can be granted to agents.

    Capability hierarchy:
    - Memory operations: MEMORY_READ, MEMORY_WRITE, MEMORY_DELETE
    - Knowledge base: KB_SEARCH, DECISION_READ, INCIDENT_READ
    - Handoff: HANDOFF_INITIATE, HANDOFF_RECEIVE

    Security model: Capabilities are granted per-agent and checked
    at runtime for every operation.
    """

    # Memory operations
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MEMORY_DELETE = "memory_delete"

    # Knowledge base operations
    KB_SEARCH = "kb_search"
    DECISION_READ = "decision_read"
    INCIDENT_READ = "incident_read"

    # Handoff operations
    HANDOFF_INITIATE = "handoff_initiate"
    HANDOFF_RECEIVE = "handoff_receive"

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value


# Default capabilities by agent type
_DEFAULT_CAPABILITIES: dict[AgentType, set[AgentCapability]] = {
    AgentType.CLAUDE_CODE: {
        AgentCapability.MEMORY_READ,
        AgentCapability.MEMORY_WRITE,
        AgentCapability.KB_SEARCH,
        AgentCapability.DECISION_READ,
        AgentCapability.INCIDENT_READ,
        AgentCapability.HANDOFF_INITIATE,
        AgentCapability.HANDOFF_RECEIVE,
    },
    AgentType.GPT_AGENT: {
        AgentCapability.MEMORY_READ,
        AgentCapability.MEMORY_WRITE,
        AgentCapability.KB_SEARCH,
        AgentCapability.DECISION_READ,
        AgentCapability.INCIDENT_READ,
        AgentCapability.HANDOFF_INITIATE,
        AgentCapability.HANDOFF_RECEIVE,
    },
    AgentType.CUSTOM_PIPELINE: {
        AgentCapability.MEMORY_READ,
        AgentCapability.KB_SEARCH,
        AgentCapability.DECISION_READ,
        AgentCapability.INCIDENT_READ,
    },
    AgentType.HUMAN: {
        AgentCapability.MEMORY_READ,
        AgentCapability.MEMORY_WRITE,
        AgentCapability.MEMORY_DELETE,
        AgentCapability.KB_SEARCH,
        AgentCapability.DECISION_READ,
        AgentCapability.INCIDENT_READ,
        AgentCapability.HANDOFF_INITIATE,
        AgentCapability.HANDOFF_RECEIVE,
    },
}


def get_default_capabilities(agent_type: AgentType) -> set[AgentCapability]:
    """Get default capabilities for an agent type.

    Args:
        agent_type: The type of agent.

    Returns:
        Set of default capabilities for the agent type.

    Example:
        >>> caps = get_default_capabilities(AgentType.CLAUDE_CODE)
        >>> AgentCapability.MEMORY_READ in caps
        True
    """
    return _DEFAULT_CAPABILITIES.get(agent_type, set()).copy()


@dataclass
class AgentIdentity:
    """Identity of an agent participating in MaaS.

    AgentIdentity uniquely identifies an agent and tracks its capabilities,
    session, and metadata. It serves as the principal for access control
    decisions.

    Attributes:
        id: Unique identifier for this agent instance.
        agent_type: Type of agent (determines default trust level).
        capabilities: Set of granted capabilities.
        owner_id: User ID that owns/controls this agent.
        metadata: Arbitrary metadata (model info, config, etc.).
        session_id: Current session ID if active.
        created_at: When this identity was created.

    Example:
        >>> identity = AgentIdentity(
        ...     id="agent-001",
        ...     agent_type=AgentType.CLAUDE_CODE,
        ...     capabilities={AgentCapability.MEMORY_READ},
        ...     owner_id="user-123",
        ... )
        >>> identity.has_capability(AgentCapability.MEMORY_READ)
        True
    """

    id: str
    agent_type: AgentType
    owner_id: str
    capabilities: set[AgentCapability] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if this agent has a specific capability.

        Args:
            capability: The capability to check for.

        Returns:
            True if the agent has the capability.
        """
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage/transmission.

        Returns:
            Dictionary representation of the identity.
        """
        return {
            "id": self.id,
            "agent_type": str(self.agent_type),
            "capabilities": [str(c) for c in self.capabilities],
            "owner_id": self.owner_id,
            "metadata": self.metadata,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentIdentity":
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation of the identity.

        Returns:
            AgentIdentity instance.
        """
        # Parse agent type
        agent_type = AgentType(data["agent_type"])

        # Parse capabilities
        capabilities = {AgentCapability(c) for c in data.get("capabilities", [])}

        # Parse created_at
        created_at_str = data.get("created_at")
        if created_at_str:
            if isinstance(created_at_str, str):
                created_at = datetime.fromisoformat(created_at_str)
            else:
                created_at = created_at_str
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            id=data["id"],
            agent_type=agent_type,
            capabilities=capabilities,
            owner_id=data["owner_id"],
            metadata=data.get("metadata", {}),
            session_id=data.get("session_id"),
            created_at=created_at,
        )

    def __hash__(self) -> int:
        """Make AgentIdentity hashable by id."""
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """Compare AgentIdentity by id."""
        if not isinstance(other, AgentIdentity):
            return NotImplemented
        return self.id == other.id
