# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS Scope Types - ADR-003 Phase 4.2 (Issues #132-137).

Defines scope and permission types for multi-agent memory sharing:
- SharedScope: Visibility levels (AGENT_PRIVATE < USER < PROJECT < TEAM < GLOBAL)
- PermissionModel: Access levels (READ < WRITE < ADMIN)
- AgentScope: Combines agent identity with visibility constraints
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.memory.maas.types import AgentIdentity


class SharedScope(str, Enum):
    """Visibility scope hierarchy for shared memories.

    Scope determines who can see a memory:
    - AGENT_PRIVATE: Only the owning agent (default)
    - USER: All agents owned by the same user
    - PROJECT: All agents working on the same project
    - TEAM: All agents in the same team/organization
    - GLOBAL: All agents in the system (use sparingly)

    Ordering: AGENT_PRIVATE < USER < PROJECT < TEAM < GLOBAL

    Security Model:
    An agent with scope X can read memories with scope <= X.
    An agent cannot read memories with scope > X.
    """

    AGENT_PRIVATE = "agent_private"
    USER = "user"
    PROJECT = "project"
    TEAM = "team"
    GLOBAL = "global"

    @property
    def level(self) -> int:
        """Numeric level for comparison.

        Returns:
            Integer level (0-4) for this scope.
        """
        levels = {
            SharedScope.AGENT_PRIVATE: 0,
            SharedScope.USER: 1,
            SharedScope.PROJECT: 2,
            SharedScope.TEAM: 3,
            SharedScope.GLOBAL: 4,
        }
        return levels[self]

    def can_access(self, target: "SharedScope") -> bool:
        """Check if this scope can access target scope.

        Args:
            target: The scope to check access for.

        Returns:
            True if this scope can read from target scope.

        Example:
            >>> SharedScope.PROJECT.can_access(SharedScope.USER)
            True
            >>> SharedScope.USER.can_access(SharedScope.PROJECT)
            False
        """
        return self.level >= target.level

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value


class PermissionModel(str, Enum):
    """Permission levels for pool/resource access.

    Hierarchy: READ < WRITE < ADMIN

    - READ: Can query and retrieve memories
    - WRITE: Can add and update memories (includes READ)
    - ADMIN: Can manage pool membership and settings (includes WRITE)
    """

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

    @property
    def level(self) -> int:
        """Numeric level for comparison.

        Returns:
            Integer level (0-2) for this permission.
        """
        levels = {
            PermissionModel.READ: 0,
            PermissionModel.WRITE: 1,
            PermissionModel.ADMIN: 2,
        }
        return levels[self]

    def includes(self, other: "PermissionModel") -> bool:
        """Check if this permission includes another.

        Args:
            other: The permission to check inclusion for.

        Returns:
            True if this permission includes the other.

        Example:
            >>> PermissionModel.ADMIN.includes(PermissionModel.READ)
            True
            >>> PermissionModel.READ.includes(PermissionModel.WRITE)
            False
        """
        return self.level >= other.level

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value


@dataclass
class AgentScope:
    """Combines agent identity with visibility constraints.

    AgentScope represents an agent's view of shared memory, constrained
    by their visibility level and context (project, team, etc.).

    Attributes:
        agent: The agent identity.
        visibility: Maximum visibility scope for this agent.
        project_id: Optional project context.
        team_id: Optional team context.

    Example:
        >>> scope = AgentScope(
        ...     agent=identity,
        ...     visibility=SharedScope.PROJECT,
        ...     project_id="proj-456",
        ... )
        >>> scope.can_read_from(SharedScope.USER)
        True
    """

    agent: "AgentIdentity"
    visibility: SharedScope = SharedScope.USER
    project_id: Optional[str] = None
    team_id: Optional[str] = None

    def can_read_from(self, target_scope: SharedScope) -> bool:
        """Check if this agent scope can read from target scope.

        Args:
            target_scope: The scope to check read access for.

        Returns:
            True if this agent can read from the target scope.
        """
        return self.visibility.can_access(target_scope)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of the scope.
        """
        return {
            "agent": self.agent.to_dict(),
            "visibility": str(self.visibility),
            "project_id": self.project_id,
            "team_id": self.team_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentScope":
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            AgentScope instance.
        """
        from src.memory.maas.types import AgentIdentity

        return cls(
            agent=AgentIdentity.from_dict(data["agent"]),
            visibility=SharedScope(data["visibility"]),
            project_id=data.get("project_id"),
            team_id=data.get("team_id"),
        )
