# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Tests for MaaS MCP Tools - ADR-003 Phase 4.2 (Issues #150-155).

TDD RED phase: Write tests first, then implement.
"""

import pytest

from src.memory.maas.registry import AgentRegistry
from src.memory.maas.scope import PermissionModel, SharedScope
from src.memory.maas.types import AgentCapability, AgentType


class TestAgentMCPTools:
    """Test MCP tools for agent management."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    @pytest.mark.asyncio
    async def test_register_agent_tool(self):
        """Verify register_agent MCP tool works."""
        from src.memory.maas.mcp_tools import register_agent

        result = await register_agent(
            agent_type="claude_code",
            owner_id="user-123",
        )

        assert "agent_id" in result
        assert result["status"] == "registered"

    @pytest.mark.asyncio
    async def test_get_agent_info_tool(self):
        """Verify get_agent_info MCP tool works."""
        from src.memory.maas.mcp_tools import get_agent_info, register_agent

        reg_result = await register_agent(
            agent_type="claude_code",
            owner_id="user-123",
        )
        agent_id = reg_result["agent_id"]

        result = await get_agent_info(agent_id=agent_id)

        assert result["id"] == agent_id
        assert result["agent_type"] == "claude_code"
        assert result["owner_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_get_agents_for_user_tool(self):
        """Verify get_agents_for_user MCP tool works."""
        from src.memory.maas.mcp_tools import get_agents_for_user, register_agent

        await register_agent(agent_type="claude_code", owner_id="user-123")
        await register_agent(agent_type="gpt_agent", owner_id="user-123")

        result = await get_agents_for_user(user_id="user-123")

        assert len(result["agents"]) == 2


class TestHandoffMCPTools:
    """Test MCP tools for handoff management."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    @pytest.mark.asyncio
    async def test_initiate_handoff_tool(self):
        """Verify initiate_handoff MCP tool works."""
        from src.memory.maas.mcp_tools import initiate_handoff, register_agent

        # Create agents with appropriate capabilities
        source = await register_agent(
            agent_type="claude_code",
            owner_id="user-123",
        )
        target = await register_agent(
            agent_type="gpt_agent",
            owner_id="user-123",
        )

        result = await initiate_handoff(
            source_agent_id=source["agent_id"],
            target_agent_id=target["agent_id"],
            task_description="Complete the task",
        )

        assert "handoff_id" in result
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_accept_handoff_tool(self):
        """Verify accept_handoff MCP tool works."""
        from src.memory.maas.mcp_tools import (
            accept_handoff,
            initiate_handoff,
            register_agent,
        )

        source = await register_agent(agent_type="claude_code", owner_id="user-123")
        target = await register_agent(agent_type="gpt_agent", owner_id="user-123")

        init_result = await initiate_handoff(
            source_agent_id=source["agent_id"],
            target_agent_id=target["agent_id"],
            task_description="Test task",
        )

        result = await accept_handoff(
            handoff_id=init_result["handoff_id"],
            agent_id=target["agent_id"],
        )

        assert result["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_complete_handoff_tool(self):
        """Verify complete_handoff MCP tool works."""
        from src.memory.maas.mcp_tools import (
            accept_handoff,
            complete_handoff,
            initiate_handoff,
            register_agent,
        )

        source = await register_agent(agent_type="claude_code", owner_id="user-123")
        target = await register_agent(agent_type="gpt_agent", owner_id="user-123")

        init_result = await initiate_handoff(
            source_agent_id=source["agent_id"],
            target_agent_id=target["agent_id"],
            task_description="Test task",
        )
        await accept_handoff(
            handoff_id=init_result["handoff_id"],
            agent_id=target["agent_id"],
        )

        result = await complete_handoff(
            handoff_id=init_result["handoff_id"],
            agent_id=target["agent_id"],
            result={"outcome": "success"},
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_pending_handoffs_tool(self):
        """Verify get_pending_handoffs MCP tool works."""
        from src.memory.maas.mcp_tools import (
            get_pending_handoffs,
            initiate_handoff,
            register_agent,
        )

        source = await register_agent(agent_type="claude_code", owner_id="user-123")
        target = await register_agent(agent_type="gpt_agent", owner_id="user-123")

        await initiate_handoff(
            source_agent_id=source["agent_id"],
            target_agent_id=target["agent_id"],
            task_description="Test task",
        )

        result = await get_pending_handoffs(agent_id=target["agent_id"])

        assert len(result["handoffs"]) == 1


class TestPoolMCPTools:
    """Test MCP tools for pool management."""

    def setup_method(self):
        """Reset registries before each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    def teardown_method(self):
        """Reset registries after each test."""
        from src.memory.maas.handoff import HandoffManager
        from src.memory.maas.pool import PoolRegistry
        from src.memory.maas.registry import AgentRegistry

        AgentRegistry.reset()
        PoolRegistry.reset()
        HandoffManager.reset()

    @pytest.mark.asyncio
    async def test_create_pool_tool(self):
        """Verify create_pool MCP tool works."""
        from src.memory.maas.mcp_tools import create_pool

        result = await create_pool(
            name="test-pool",
            owner_id="user-123",
            scope="project",
        )

        assert "pool_id" in result
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_join_pool_tool(self):
        """Verify join_pool MCP tool works."""
        from src.memory.maas.mcp_tools import create_pool, join_pool, register_agent

        pool_result = await create_pool(
            name="test-pool",
            owner_id="user-123",
            scope="project",
        )
        agent_result = await register_agent(
            agent_type="claude_code",
            owner_id="user-456",
        )

        result = await join_pool(
            pool_id=pool_result["pool_id"],
            agent_id=agent_result["agent_id"],
            permission="read",
        )

        assert result["status"] == "joined"

    @pytest.mark.asyncio
    async def test_leave_pool_tool(self):
        """Verify leave_pool MCP tool works."""
        from src.memory.maas.mcp_tools import (
            create_pool,
            join_pool,
            leave_pool,
            register_agent,
        )

        pool_result = await create_pool(name="test-pool", owner_id="user-123", scope="project")
        agent_result = await register_agent(agent_type="claude_code", owner_id="user-456")
        await join_pool(
            pool_id=pool_result["pool_id"],
            agent_id=agent_result["agent_id"],
            permission="read",
        )

        result = await leave_pool(
            pool_id=pool_result["pool_id"],
            agent_id=agent_result["agent_id"],
        )

        assert result["status"] == "left"

    @pytest.mark.asyncio
    async def test_share_memory_to_scope_tool(self):
        """Verify share_memory_to_scope MCP tool works."""
        from src.memory.maas.mcp_tools import (
            create_pool,
            join_pool,
            register_agent,
            share_memory_to_scope,
        )

        pool_result = await create_pool(name="test-pool", owner_id="user-123", scope="project")
        agent_result = await register_agent(agent_type="claude_code", owner_id="user-123")
        await join_pool(
            pool_id=pool_result["pool_id"],
            agent_id=agent_result["agent_id"],
            permission="write",
        )

        result = await share_memory_to_scope(
            pool_id=pool_result["pool_id"],
            memory_id="mem-123",
            agent_id=agent_result["agent_id"],
            scope="project",
        )

        assert result["status"] == "shared"

    @pytest.mark.asyncio
    async def test_query_shared_tool(self):
        """Verify query_shared MCP tool works."""
        from src.memory.maas.mcp_tools import (
            create_pool,
            join_pool,
            query_shared,
            register_agent,
            share_memory_to_scope,
        )

        pool_result = await create_pool(name="test-pool", owner_id="user-123", scope="project")
        agent_result = await register_agent(agent_type="claude_code", owner_id="user-123")
        await join_pool(
            pool_id=pool_result["pool_id"],
            agent_id=agent_result["agent_id"],
            permission="write",
        )
        await share_memory_to_scope(
            pool_id=pool_result["pool_id"],
            memory_id="mem-123",
            agent_id=agent_result["agent_id"],
            scope="user",
        )

        result = await query_shared(
            pool_id=pool_result["pool_id"],
            agent_id=agent_result["agent_id"],
            max_scope="project",
        )

        assert "memories" in result
        assert len(result["memories"]) == 1


class TestKBMCPTools:
    """Test MCP tools for knowledge base search."""

    @pytest.mark.asyncio
    async def test_search_code_kb_tool(self):
        """Verify search_code_kb MCP tool works."""
        from src.memory.maas.mcp_tools import search_code_kb

        result = await search_code_kb(
            query="authentication",
            limit=5,
        )

        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_decisions_tool(self):
        """Verify search_decisions MCP tool works."""
        from src.memory.maas.mcp_tools import search_decisions

        result = await search_decisions(
            query="database choice",
            limit=5,
        )

        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_incidents_tool(self):
        """Verify search_incidents MCP tool works."""
        from src.memory.maas.mcp_tools import search_incidents

        result = await search_incidents(
            query="outage",
            limit=5,
        )

        assert "results" in result
