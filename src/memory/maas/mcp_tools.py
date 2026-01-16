# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS MCP Tools - ADR-003 Phase 4.2 (Issues #150-155).

MCP tool functions for multi-agent collaboration:
- Agent management: register_agent, get_agent_info, get_agents_for_user
- Handoff: initiate_handoff, accept_handoff, complete_handoff, get_pending_handoffs
- Pools: create_pool, join_pool, leave_pool, share_memory_to_scope, query_shared
- KB search: search_code_kb, search_decisions, search_incidents

These functions are designed to be exposed via the MCP server.
"""

from typing import Any, Optional

from src.memory.maas.handoff import HandoffContext, HandoffManager
from src.memory.maas.pool import PoolRegistry
from src.memory.maas.registry import AgentRegistry
from src.memory.maas.scope import PermissionModel, SharedScope
from src.memory.maas.services import CodeKBService, DecisionService, IncidentService
from src.memory.maas.types import AgentType, get_default_capabilities


# =============================================================================
# Agent Management Tools
# =============================================================================


async def register_agent(
    agent_type: str,
    owner_id: str,
    agent_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Register a new agent in the MaaS system.

    Args:
        agent_type: Type of agent (claude_code, gpt_agent, custom_pipeline, human).
        owner_id: User ID that owns this agent.
        agent_id: Optional custom agent ID.
        metadata: Optional agent metadata.

    Returns:
        Dict with agent_id and status.
    """
    registry = AgentRegistry.get()

    try:
        agent_type_enum = AgentType(agent_type)
    except ValueError:
        return {"error": f"Invalid agent_type: {agent_type}", "status": "error"}

    registered_id = registry.register_agent(
        agent_type=agent_type_enum,
        owner_id=owner_id,
        agent_id=agent_id,
        metadata=metadata,
    )

    return {
        "agent_id": registered_id,
        "status": "registered",
    }


async def get_agent_info(agent_id: str) -> dict[str, Any]:
    """Get information about an agent.

    Args:
        agent_id: The agent ID.

    Returns:
        Dict with agent information.
    """
    registry = AgentRegistry.get()
    agent = registry.get_agent(agent_id)

    if agent is None:
        return {"error": f"Agent not found: {agent_id}", "status": "error"}

    return {
        "id": agent.id,
        "agent_type": str(agent.agent_type),
        "owner_id": agent.owner_id,
        "capabilities": [str(c) for c in agent.capabilities],
        "metadata": agent.metadata,
        "session_id": agent.session_id,
        "created_at": agent.created_at.isoformat(),
    }


async def get_agents_for_user(user_id: str) -> dict[str, Any]:
    """Get all agents owned by a user.

    Args:
        user_id: The user ID.

    Returns:
        Dict with list of agents.
    """
    registry = AgentRegistry.get()
    agents = registry.get_agents_by_owner(user_id)

    return {
        "agents": [
            {
                "id": a.id,
                "agent_type": str(a.agent_type),
                "capabilities": [str(c) for c in a.capabilities],
            }
            for a in agents
        ]
    }


# =============================================================================
# Handoff Tools
# =============================================================================


async def initiate_handoff(
    source_agent_id: str,
    target_agent_id: str,
    task_description: str,
    current_state: Optional[dict[str, Any]] = None,
    relevant_memories: Optional[list[str]] = None,
    relevant_files: Optional[list[str]] = None,
    ttl_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Initiate a handoff from source to target agent.

    Args:
        source_agent_id: Agent initiating the handoff.
        target_agent_id: Agent receiving the handoff.
        task_description: Description of the task.
        current_state: Current task state (optional).
        relevant_memories: List of relevant memory IDs (optional).
        relevant_files: List of relevant file paths (optional).
        ttl_seconds: Time-to-live in seconds (optional).

    Returns:
        Dict with handoff_id and status.
    """
    manager = HandoffManager.get()

    context = HandoffContext(
        task_description=task_description,
        current_state=current_state or {},
        relevant_memories=relevant_memories or [],
        relevant_files=relevant_files or [],
    )

    handoff_id = manager.initiate_handoff(
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        context=context,
        ttl_seconds=ttl_seconds,
    )

    if handoff_id is None:
        return {
            "error": "Failed to initiate handoff. Check agent capabilities.",
            "status": "error",
        }

    return {
        "handoff_id": handoff_id,
        "status": "pending",
    }


async def accept_handoff(handoff_id: str, agent_id: str) -> dict[str, Any]:
    """Accept a handoff.

    Args:
        handoff_id: The handoff to accept.
        agent_id: The agent accepting (must be target).

    Returns:
        Dict with status.
    """
    manager = HandoffManager.get()

    success = manager.accept_handoff(handoff_id, agent_id)

    if not success:
        return {"error": "Failed to accept handoff", "status": "error"}

    handoff = manager.get_handoff(handoff_id)
    return {
        "status": "accepted",
        "context": handoff.context.to_dict() if handoff else None,
    }


async def complete_handoff(
    handoff_id: str,
    agent_id: str,
    result: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Complete a handoff.

    Args:
        handoff_id: The handoff to complete.
        agent_id: The agent completing (must be target).
        result: Optional result data.

    Returns:
        Dict with status.
    """
    manager = HandoffManager.get()

    success = manager.complete_handoff(handoff_id, agent_id, result)

    if not success:
        return {"error": "Failed to complete handoff", "status": "error"}

    return {"status": "completed"}


async def get_pending_handoffs(agent_id: str) -> dict[str, Any]:
    """Get pending handoffs for an agent.

    Args:
        agent_id: The target agent ID.

    Returns:
        Dict with list of pending handoffs.
    """
    manager = HandoffManager.get()

    handoffs = manager.get_pending_handoffs(agent_id)

    return {
        "handoffs": [
            {
                "id": h.id,
                "source_agent_id": h.source_agent_id,
                "task_description": h.context.task_description,
                "created_at": h.created_at.isoformat(),
            }
            for h in handoffs
        ]
    }


# =============================================================================
# Pool Tools
# =============================================================================


async def create_pool(
    name: str,
    owner_id: str,
    scope: str,
    pool_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a shared memory pool.

    Args:
        name: Pool name.
        owner_id: User ID that owns the pool.
        scope: Visibility scope (agent_private, user, project, team, global).
        pool_id: Optional custom pool ID.
        metadata: Optional pool metadata.

    Returns:
        Dict with pool_id and status.
    """
    registry = PoolRegistry.get()

    try:
        scope_enum = SharedScope(scope)
    except ValueError:
        return {"error": f"Invalid scope: {scope}", "status": "error"}

    created_id = registry.create_pool(
        name=name,
        owner_id=owner_id,
        scope=scope_enum,
        pool_id=pool_id,
        metadata=metadata,
    )

    return {
        "pool_id": created_id,
        "status": "created",
    }


async def join_pool(
    pool_id: str,
    agent_id: str,
    permission: str,
) -> dict[str, Any]:
    """Join an agent to a pool.

    Args:
        pool_id: The pool to join.
        agent_id: The agent joining.
        permission: Permission level (read, write, admin).

    Returns:
        Dict with status.
    """
    registry = PoolRegistry.get()

    try:
        perm_enum = PermissionModel(permission)
    except ValueError:
        return {"error": f"Invalid permission: {permission}", "status": "error"}

    success = registry.join_pool(pool_id, agent_id, perm_enum)

    if not success:
        return {"error": "Failed to join pool", "status": "error"}

    return {"status": "joined"}


async def leave_pool(pool_id: str, agent_id: str) -> dict[str, Any]:
    """Remove an agent from a pool.

    Args:
        pool_id: The pool to leave.
        agent_id: The agent leaving.

    Returns:
        Dict with status.
    """
    registry = PoolRegistry.get()

    success = registry.leave_pool(pool_id, agent_id)

    if not success:
        return {"error": "Failed to leave pool", "status": "error"}

    return {"status": "left"}


async def share_memory_to_scope(
    pool_id: str,
    memory_id: str,
    agent_id: str,
    scope: str,
) -> dict[str, Any]:
    """Share a memory to a pool with specified scope.

    Args:
        pool_id: The pool to share to.
        memory_id: The memory to share.
        agent_id: The agent sharing.
        scope: Visibility scope for the share.

    Returns:
        Dict with status.
    """
    registry = PoolRegistry.get()

    try:
        scope_enum = SharedScope(scope)
    except ValueError:
        return {"error": f"Invalid scope: {scope}", "status": "error"}

    success = registry.share_memory(pool_id, memory_id, agent_id, scope_enum)

    if not success:
        return {"error": "Failed to share memory (insufficient permission)", "status": "error"}

    return {"status": "shared"}


async def query_shared(
    pool_id: str,
    agent_id: str,
    max_scope: str,
) -> dict[str, Any]:
    """Query shared memories in a pool.

    Args:
        pool_id: The pool to query.
        agent_id: The agent querying.
        max_scope: Maximum scope to include.

    Returns:
        Dict with list of memories.
    """
    registry = PoolRegistry.get()

    try:
        scope_enum = SharedScope(max_scope)
    except ValueError:
        return {"error": f"Invalid scope: {max_scope}", "status": "error"}

    memories = registry.query_shared(pool_id, agent_id, scope_enum)

    return {"memories": memories}


# =============================================================================
# Knowledge Base Search Tools
# =============================================================================


async def search_code_kb(
    query: str,
    service_filter: Optional[str] = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search the code knowledge base.

    Args:
        query: Search query.
        service_filter: Optional service name filter.
        limit: Maximum results.

    Returns:
        Dict with search results.
    """
    service = CodeKBService()
    results = service.search(query, service_filter, limit)

    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]
    }


async def search_decisions(
    query: str,
    topic_filter: Optional[str] = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search ADRs and decisions.

    Args:
        query: Search query.
        topic_filter: Optional topic filter.
        limit: Maximum results.

    Returns:
        Dict with search results.
    """
    service = DecisionService()
    results = service.search(query, topic_filter, limit)

    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]
    }


async def search_incidents(
    query: str,
    service_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search incident history.

    Args:
        query: Search query.
        service_filter: Optional service name filter.
        severity_filter: Optional severity filter.
        limit: Maximum results.

    Returns:
        Dict with search results.
    """
    service = IncidentService()
    results = service.search(query, service_filter, severity_filter, limit)

    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]
    }
