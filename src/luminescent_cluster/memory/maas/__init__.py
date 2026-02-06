# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory as a Service (MaaS) - ADR-003 Phase 4.2.

Multi-agent collaboration support enabling agents to:
- Share memories across agent boundaries
- Hand off tasks with context preservation
- Query shared knowledge bases
- Maintain isolated scopes for security

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Memory as a Service (MaaS)                    │
    ├─────────────────────────────────────────────────────────────────┤
    │   ┌───────────┐     ┌───────────┐     ┌───────────┐             │
    │   │ Code KB   │     │ Decision  │     │ Incident  │             │
    │   │ Service   │     │ Service   │     │ Service   │             │
    │   └─────┬─────┘     └─────┬─────┘     └─────┬─────┘             │
    │         └───────────────┬─┴─────────────────┘                   │
    │                         ▼                                        │
    │              ┌─────────────────────┐                            │
    │              │   MaaS Service      │                            │
    │              │   (Orchestrator)    │                            │
    │              └─────────────────────┘                            │
    │                         │                                        │
    │    ┌────────────────────┼────────────────────┐                  │
    │    ▼                    ▼                    ▼                  │
    │ ┌─────────┐      ┌─────────────┐      ┌──────────┐             │
    │ │ Claude  │      │ GPT Agent   │      │ Custom   │             │
    │ │ Code    │      │             │      │ Pipeline │             │
    │ └─────────┘      └─────────────┘      └──────────┘             │
    └─────────────────────────────────────────────────────────────────┘

Related:
- ADR-003: Memory Architecture
- GitHub Issues: #132-167
"""

from luminescent_cluster.memory.maas.handoff import (
    Handoff,
    HandoffCapacityError,
    HandoffContext,
    HandoffManager,
    HandoffStatus,
)
from luminescent_cluster.memory.maas.pool import (
    DuplicatePoolError,
    PoolCapacityError,
    PoolRegistry,
    PoolStatus,
    SharedMemoryPool,
)
from luminescent_cluster.memory.maas.provider import MaaSMemoryProvider
from luminescent_cluster.memory.maas.registry import AgentRegistry, DuplicateAgentError, RegistryCapacityError
from luminescent_cluster.memory.maas.scope import (
    AgentScope,
    PermissionModel,
    SharedScope,
)
from luminescent_cluster.memory.maas.security import (
    AgentRateLimiter,
    MaaSAuditLogger,
    MemoryPoisoningDefense,
    MEXTRAValidator,
)
from luminescent_cluster.memory.maas.services import (
    CodeKBService,
    DecisionService,
    IncidentService,
)
from luminescent_cluster.memory.maas.types import (
    AgentCapability,
    AgentIdentity,
    AgentType,
    get_default_capabilities,
)

__all__ = [
    # Types
    "AgentType",
    "AgentCapability",
    "AgentIdentity",
    "get_default_capabilities",
    # Scopes
    "SharedScope",
    "PermissionModel",
    "AgentScope",
    # Registry
    "AgentRegistry",
    "DuplicateAgentError",
    "RegistryCapacityError",
    # Pools
    "PoolRegistry",
    "SharedMemoryPool",
    "PoolStatus",
    "DuplicatePoolError",
    "PoolCapacityError",
    # Handoff
    "HandoffManager",
    "Handoff",
    "HandoffContext",
    "HandoffStatus",
    "HandoffCapacityError",
    # Provider
    "MaaSMemoryProvider",
    # Services
    "CodeKBService",
    "DecisionService",
    "IncidentService",
    # Security
    "MEXTRAValidator",
    "MemoryPoisoningDefense",
    "AgentRateLimiter",
    "MaaSAuditLogger",
]
