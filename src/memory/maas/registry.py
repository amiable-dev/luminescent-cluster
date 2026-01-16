# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS Agent Registry - ADR-003 Phase 4.2 (Issues #138-143).

Singleton registry for agent identity management:
- Register agents with capabilities
- Track active/inactive agents
- Manage sessions
- Thread-safe operations with RLock

Design follows ExtensionRegistry pattern (src/extensions/registry.py).
"""

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Optional

from src.memory.maas.types import (
    AgentCapability,
    AgentIdentity,
    AgentType,
    get_default_capabilities,
)


class DuplicateAgentError(Exception):
    """Raised when attempting to register an agent with duplicate ID."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent with ID '{agent_id}' already exists")


@dataclass
class SessionInfo:
    """Information about an active session.

    Attributes:
        session_id: Unique session identifier.
        agent_id: Agent associated with this session.
        started_at: When the session started.
        metadata: Additional session metadata.
    """

    session_id: str
    agent_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """Singleton registry for agent identity management.

    The AgentRegistry maintains a registry of all agents participating
    in MaaS, their capabilities, active/inactive status, and sessions.

    Thread-safe: All operations use RLock for synchronization.

    Usage (registering agents):
        registry = AgentRegistry.get()
        agent_id = registry.register_agent(
            agent_type=AgentType.CLAUDE_CODE,
            owner_id="user-123",
        )

    Usage (checking agents):
        registry = AgentRegistry.get()
        agent = registry.get_agent(agent_id)
        if agent and registry.is_agent_active(agent_id):
            # Agent is active
            pass

    Attributes:
        _agents: Dict mapping agent_id to AgentIdentity.
        _active: Set of active agent IDs.
        _sessions: Dict mapping session_id to SessionInfo.
        _agent_sessions: Dict mapping agent_id to session_id.
        _owner_index: Dict mapping owner_id to set of agent_ids.
    """

    # Singleton management
    _instance: ClassVar[Optional["AgentRegistry"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self):
        """Initialize the registry (internal use only)."""
        self._agents: dict[str, AgentIdentity] = {}
        self._active: set[str] = set()
        self._sessions: dict[str, SessionInfo] = {}
        self._agent_sessions: dict[str, str] = {}  # agent_id -> session_id
        self._owner_index: dict[str, set[str]] = defaultdict(set)
        self._rlock = threading.RLock()

    @classmethod
    def get(cls) -> "AgentRegistry":
        """Get the singleton AgentRegistry instance.

        Thread-safe: Uses double-checked locking pattern.

        Returns:
            The singleton AgentRegistry instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing only).

        Warning:
            This should only be used in test fixtures to ensure
            clean state between tests. Never call in production code.
        """
        with cls._lock:
            cls._instance = None

    def register_agent(
        self,
        agent_type: AgentType,
        owner_id: str,
        agent_id: Optional[str] = None,
        capabilities: Optional[set[AgentCapability]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Register a new agent in the registry.

        Args:
            agent_type: Type of agent (CLAUDE_CODE, GPT_AGENT, etc.).
            owner_id: User ID that owns this agent.
            agent_id: Optional custom agent ID (generated if not provided).
            capabilities: Optional custom capabilities (defaults used if not provided).
            metadata: Optional metadata dict.

        Returns:
            The agent ID.

        Raises:
            DuplicateAgentError: If agent_id already exists.

        Example:
            agent_id = registry.register_agent(
                agent_type=AgentType.CLAUDE_CODE,
                owner_id="user-123",
            )
        """
        with self._rlock:
            # Generate ID if not provided
            if agent_id is None:
                agent_id = f"agent-{uuid.uuid4().hex[:12]}"

            # Check for duplicate
            if agent_id in self._agents:
                raise DuplicateAgentError(agent_id)

            # Use default capabilities if not provided
            if capabilities is None:
                capabilities = get_default_capabilities(agent_type)

            # Create identity
            identity = AgentIdentity(
                id=agent_id,
                agent_type=agent_type,
                owner_id=owner_id,
                capabilities=capabilities,
                metadata=metadata or {},
            )

            # Register
            self._agents[agent_id] = identity
            self._active.add(agent_id)
            self._owner_index[owner_id].add(agent_id)

            return agent_id

    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get an agent by ID.

        Args:
            agent_id: The agent ID to look up.

        Returns:
            AgentIdentity if found, None otherwise.
        """
        with self._rlock:
            return self._agents.get(agent_id)

    def get_agents_by_owner(self, owner_id: str) -> list[AgentIdentity]:
        """Get all agents owned by a user.

        Args:
            owner_id: The owner's user ID.

        Returns:
            List of AgentIdentity objects.
        """
        with self._rlock:
            agent_ids = self._owner_index.get(owner_id, set())
            return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_active_agents(self) -> list[AgentIdentity]:
        """Get all active agents.

        Returns:
            List of active AgentIdentity objects.
        """
        with self._rlock:
            return [self._agents[aid] for aid in self._active if aid in self._agents]

    def deactivate_agent(self, agent_id: str) -> bool:
        """Deactivate an agent.

        Args:
            agent_id: The agent ID to deactivate.

        Returns:
            True if agent was deactivated, False if not found.
        """
        with self._rlock:
            if agent_id not in self._agents:
                return False

            self._active.discard(agent_id)

            # End any active session
            if agent_id in self._agent_sessions:
                session_id = self._agent_sessions.pop(agent_id)
                if session_id in self._sessions:
                    del self._sessions[session_id]
                agent = self._agents[agent_id]
                agent.session_id = None

            return True

    def is_agent_active(self, agent_id: str) -> bool:
        """Check if an agent is active.

        Args:
            agent_id: The agent ID to check.

        Returns:
            True if agent is active, False otherwise.
        """
        with self._rlock:
            return agent_id in self._active

    def start_session(
        self,
        agent_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Start a new session for an agent.

        Args:
            agent_id: The agent to start a session for.
            metadata: Optional session metadata.

        Returns:
            Session ID if successful, None if agent not found.
        """
        with self._rlock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return None

            # End existing session if any
            if agent_id in self._agent_sessions:
                old_session_id = self._agent_sessions[agent_id]
                if old_session_id in self._sessions:
                    del self._sessions[old_session_id]

            # Create new session
            session_id = f"session-{uuid.uuid4().hex[:12]}"
            session = SessionInfo(
                session_id=session_id,
                agent_id=agent_id,
                metadata=metadata or {},
            )

            # Store session
            self._sessions[session_id] = session
            self._agent_sessions[agent_id] = session_id

            # Update agent
            agent.session_id = session_id

            return session_id

    def end_session(self, agent_id: str) -> bool:
        """End an agent's session.

        Args:
            agent_id: The agent whose session to end.

        Returns:
            True if session was ended, False if no session.
        """
        with self._rlock:
            if agent_id not in self._agent_sessions:
                return False

            session_id = self._agent_sessions.pop(agent_id)
            if session_id in self._sessions:
                del self._sessions[session_id]

            agent = self._agents.get(agent_id)
            if agent:
                agent.session_id = None

            return True

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session information.

        Args:
            session_id: The session ID to look up.

        Returns:
            Session info dict if found, None otherwise.
        """
        with self._rlock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            return {
                "session_id": session.session_id,
                "agent_id": session.agent_id,
                "started_at": session.started_at.isoformat(),
                "metadata": session.metadata,
            }

    def agent_count(self) -> int:
        """Get total number of registered agents.

        Returns:
            Number of registered agents.
        """
        with self._rlock:
            return len(self._agents)

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dict with registry stats.
        """
        with self._rlock:
            agents_by_type: dict[AgentType, int] = defaultdict(int)
            for agent in self._agents.values():
                agents_by_type[agent.agent_type] += 1

            return {
                "total_agents": len(self._agents),
                "active_agents": len(self._active),
                "total_sessions": len(self._sessions),
                "agents_by_type": dict(agents_by_type),
            }
