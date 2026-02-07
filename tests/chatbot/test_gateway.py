# Copyright 2024-2025 Amiable Development
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
TDD: RED Phase - Tests for ChatbotGateway.

These tests define the expected behavior for the central message routing
gateway before implementation. They should FAIL until the gateway is implemented.

Related GitHub Issues:
- #33: Test ChatbotGateway message routing
- #34: Test ChatbotGateway MCP integration
- #35: Implement ChatbotGateway
- #36: Test invocation policy (mention/DM/prefix)
- #37: Implement invocation policy

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from datetime import datetime
from typing import Optional, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

# Import the gateway - this will fail until implemented (RED phase)
from luminescent_cluster.chatbot.gateway import (
    ChatbotGateway,
    GatewayConfig,
    InvocationPolicy,
    InvocationType,
    GatewayRequest,
    GatewayResponse,
)

from luminescent_cluster.chatbot.adapters.base import ChatMessage, MessageAuthor
from luminescent_cluster.chatbot.context import ThreadContextManager
from luminescent_cluster.chatbot.rate_limiter import TokenBucketRateLimiter, RateLimitConfig


class TestGatewayConfig:
    """TDD: Tests for GatewayConfig data model."""

    def test_config_has_default_values(self):
        """GatewayConfig should have sensible defaults."""
        config = GatewayConfig()

        assert config.default_model is not None
        assert config.max_response_tokens > 0
        assert config.system_prompt is not None

    def test_config_custom_values(self):
        """GatewayConfig should accept custom values."""
        config = GatewayConfig(
            default_model="gpt-4o",
            max_response_tokens=4096,
            system_prompt="You are a helpful assistant.",
            enable_context=True,
            enable_rate_limiting=True,
        )

        assert config.default_model == "gpt-4o"
        assert config.max_response_tokens == 4096
        assert config.system_prompt == "You are a helpful assistant."
        assert config.enable_context is True
        assert config.enable_rate_limiting is True


class TestInvocationPolicy:
    """TDD: Tests for invocation policy (Issue #36)."""

    def test_invocation_types_exist(self):
        """InvocationType enum should define supported invocation methods."""
        assert InvocationType.MENTION is not None
        assert InvocationType.DIRECT_MESSAGE is not None
        assert InvocationType.PREFIX is not None
        assert InvocationType.ALWAYS is not None

    def test_policy_with_defaults(self):
        """InvocationPolicy should have default configuration."""
        policy = InvocationPolicy()

        # Default: respond to mentions and DMs
        assert InvocationType.MENTION in policy.enabled_types
        assert InvocationType.DIRECT_MESSAGE in policy.enabled_types

    def test_policy_with_prefix(self):
        """InvocationPolicy should support prefix-based invocation."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.PREFIX],
            prefix="!ask",
        )

        assert policy.prefix == "!ask"

    def test_policy_with_custom_mention_pattern(self):
        """InvocationPolicy should support custom mention patterns."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION],
            mention_patterns=["@bot", "<@BOT_ID>"],
        )

        assert "@bot" in policy.mention_patterns

    def test_should_respond_to_mention(self):
        """Policy should detect when to respond to mentions."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION],
            bot_user_id="BOT123",
        )

        # Message that mentions bot
        msg = ChatMessage(
            id="msg-1",
            content="<@BOT123> hello there",
            author=MessageAuthor(id="user-1", username="user"),
            channel_id="ch-1",
            timestamp=datetime.now(),
        )

        assert policy.should_respond(msg) is True

    def test_should_respond_to_dm(self):
        """Policy should detect when to respond to DMs."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.DIRECT_MESSAGE],
        )

        # Direct message
        msg = ChatMessage(
            id="msg-1",
            content="hello there",
            author=MessageAuthor(id="user-1", username="user"),
            channel_id="dm-user-1",
            timestamp=datetime.now(),
            is_direct_message=True,
        )

        assert policy.should_respond(msg) is True

    def test_should_respond_to_prefix(self):
        """Policy should detect prefix-based invocation."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.PREFIX],
            prefix="!ask",
        )

        msg = ChatMessage(
            id="msg-1",
            content="!ask what is the weather?",
            author=MessageAuthor(id="user-1", username="user"),
            channel_id="ch-1",
            timestamp=datetime.now(),
        )

        assert policy.should_respond(msg) is True

    def test_should_not_respond_without_trigger(self):
        """Policy should not respond to messages without triggers."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION, InvocationType.PREFIX],
            bot_user_id="BOT123",
            prefix="!ask",
        )

        msg = ChatMessage(
            id="msg-1",
            content="just a regular message",
            author=MessageAuthor(id="user-1", username="user"),
            channel_id="ch-1",
            timestamp=datetime.now(),
        )

        assert policy.should_respond(msg) is False

    def test_extract_content_removes_mention(self):
        """Policy should extract content after removing mention."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION],
            bot_user_id="BOT123",
        )

        msg = ChatMessage(
            id="msg-1",
            content="<@BOT123> what is 2+2?",
            author=MessageAuthor(id="user-1", username="user"),
            channel_id="ch-1",
            timestamp=datetime.now(),
        )

        content = policy.extract_content(msg)
        assert content == "what is 2+2?"

    def test_extract_content_removes_prefix(self):
        """Policy should extract content after removing prefix."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.PREFIX],
            prefix="!ask",
        )

        msg = ChatMessage(
            id="msg-1",
            content="!ask what is the weather?",
            author=MessageAuthor(id="user-1", username="user"),
            channel_id="ch-1",
            timestamp=datetime.now(),
        )

        content = policy.extract_content(msg)
        assert content == "what is the weather?"


class TestGatewayRequest:
    """TDD: Tests for GatewayRequest data model."""

    def test_request_has_required_fields(self):
        """GatewayRequest should have required fields."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
            ),
            platform="discord",
        )

        assert request.message.content == "Hello"
        assert request.platform == "discord"

    def test_request_optional_fields(self):
        """GatewayRequest should support optional fields."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
            ),
            platform="slack",
            thread_id="thread-123",
            workspace_id="ws-456",
            tenant_id="tenant-789",
        )

        assert request.thread_id == "thread-123"
        assert request.workspace_id == "ws-456"
        assert request.tenant_id == "tenant-789"


class TestGatewayResponse:
    """TDD: Tests for GatewayResponse data model."""

    def test_response_has_required_fields(self):
        """GatewayResponse should have required fields."""
        response = GatewayResponse(
            content="Hello there!",
            tokens_used=15,
        )

        assert response.content == "Hello there!"
        assert response.tokens_used == 15

    def test_response_optional_fields(self):
        """GatewayResponse should support optional fields."""
        response = GatewayResponse(
            content="Hello!",
            tokens_used=10,
            model="gpt-4o-mini",
            latency_ms=150.0,
            metadata={"finish_reason": "stop"},
        )

        assert response.model == "gpt-4o-mini"
        assert response.latency_ms == 150.0
        assert response.metadata["finish_reason"] == "stop"


class TestChatbotGatewayBasics:
    """TDD: Tests for basic ChatbotGateway operations (Issue #33)."""

    def test_create_gateway(self):
        """Should create gateway with config."""
        config = GatewayConfig()
        gateway = ChatbotGateway(config)

        assert gateway.config is not None

    def test_gateway_has_invocation_policy(self):
        """Gateway should have invocation policy."""
        gateway = ChatbotGateway()

        assert gateway.invocation_policy is not None

    def test_gateway_with_custom_policy(self):
        """Gateway should accept custom invocation policy."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.PREFIX],
            prefix="!bot",
        )
        gateway = ChatbotGateway(invocation_policy=policy)

        assert gateway.invocation_policy.prefix == "!bot"


class TestMessageRouting:
    """TDD: Tests for message routing (Issue #33)."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="Hello there!",
                tokens_used=20,
                model="gpt-4o-mini",
            )
        )
        return provider

    @pytest.fixture
    def gateway(self, mock_llm_provider):
        """Create gateway with mock provider."""
        policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION, InvocationType.DIRECT_MESSAGE],
            bot_user_id="BOT123",
        )
        gateway = ChatbotGateway(invocation_policy=policy)
        gateway.llm_provider = mock_llm_provider
        return gateway

    @pytest.mark.asyncio
    async def test_process_message_returns_response(self, gateway):
        """Gateway should process message and return response."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="<@BOT123> Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
            ),
            platform="discord",
        )

        response = await gateway.process(request)

        assert response is not None
        assert response.content == "Hello there!"
        assert response.tokens_used == 20

    @pytest.mark.asyncio
    async def test_process_skips_non_triggered_messages(self, gateway):
        """Gateway should skip messages that don't trigger invocation."""
        gateway.invocation_policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION],
            bot_user_id="BOT123",
        )

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Just a regular message",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
            ),
            platform="discord",
        )

        response = await gateway.process(request)

        assert response is None

    @pytest.mark.asyncio
    async def test_process_extracts_content(self, gateway):
        """Gateway should extract content (remove mention/prefix)."""
        gateway.invocation_policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION],
            bot_user_id="BOT123",
        )

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="<@BOT123> what is 2+2?",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
            ),
            platform="discord",
        )

        await gateway.process(request)

        # Check that LLM received extracted content
        call_args = gateway.llm_provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        user_message = next(m for m in messages if m["role"] == "user")
        assert "what is 2+2?" in user_message["content"]


class TestContextIntegration:
    """TDD: Tests for context manager integration."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="I'm doing well!",
                tokens_used=15,
                model="gpt-4o-mini",
            )
        )
        return provider

    @pytest.fixture
    def gateway(self, mock_llm_provider):
        """Create gateway with context enabled."""
        config = GatewayConfig(enable_context=True)
        gateway = ChatbotGateway(config)
        gateway.llm_provider = mock_llm_provider
        gateway.context_manager = ThreadContextManager()
        return gateway

    @pytest.mark.asyncio
    async def test_gateway_uses_context_manager(self, gateway):
        """Gateway should use context manager for conversation history."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello!",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
            thread_id="thread-123",
        )

        # First message
        await gateway.process(request)

        # Second message in same thread
        request2 = GatewayRequest(
            message=ChatMessage(
                id="msg-2",
                content="How are you?",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
            thread_id="thread-123",
        )

        await gateway.process(request2)

        # Context should have both messages
        ctx = gateway.context_manager.get_or_create("thread-123", "ch-1")
        assert len(ctx.messages) >= 2

    @pytest.mark.asyncio
    async def test_gateway_includes_context_in_llm_call(self, gateway):
        """Gateway should include conversation context in LLM call."""
        # Add prior context
        gateway.context_manager.add_message("thread-123", "user", "Hello!")
        gateway.context_manager.add_message("thread-123", "assistant", "Hi there!")

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-3",
                content="What's my name?",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
            thread_id="thread-123",
        )

        await gateway.process(request)

        # LLM should receive full context
        call_args = gateway.llm_provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]

        # Should have system + prior messages + new message
        assert len(messages) >= 3


class TestRateLimitingIntegration:
    """TDD: Tests for rate limiting integration."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="Response",
                tokens_used=10,
                model="gpt-4o-mini",
            )
        )
        return provider

    @pytest.fixture
    def gateway(self, mock_llm_provider):
        """Create gateway with rate limiting."""
        config = GatewayConfig(enable_rate_limiting=True)
        gateway = ChatbotGateway(config)
        gateway.llm_provider = mock_llm_provider
        gateway.rate_limiter = TokenBucketRateLimiter(RateLimitConfig(requests_per_minute=3))
        return gateway

    @pytest.mark.asyncio
    async def test_gateway_enforces_rate_limits(self, gateway):
        """Gateway should enforce rate limits."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
        )

        # Make requests up to limit
        for _ in range(3):
            response = await gateway.process(request)
            assert response is not None

        # Next request should be rate limited
        response = await gateway.process(request)
        assert response is None or "rate limit" in response.content.lower()

    @pytest.mark.asyncio
    async def test_gateway_records_token_usage(self, gateway):
        """Gateway should record token usage after response."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
        )

        await gateway.process(request)

        # Rate limiter should have recorded usage
        result = gateway.rate_limiter.check("user-1", tokens=0)
        assert result.remaining_tokens < 100000  # Some tokens consumed


class TestMCPIntegration:
    """TDD: Tests for MCP server integration (Issue #34)."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="Based on the MCP data...",
                tokens_used=50,
                model="gpt-4o-mini",
            )
        )
        return provider

    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client."""
        client = AsyncMock()
        client.query = AsyncMock(return_value={"results": [{"content": "MCP result data"}]})
        return client

    @pytest.fixture
    def gateway(self, mock_llm_provider, mock_mcp_client):
        """Create gateway with MCP integration."""
        config = GatewayConfig(enable_mcp=True)
        gateway = ChatbotGateway(config)
        gateway.llm_provider = mock_llm_provider
        gateway.mcp_client = mock_mcp_client
        return gateway

    @pytest.mark.asyncio
    async def test_gateway_can_query_mcp(self, gateway):
        """Gateway should be able to query MCP servers."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Search for Python tutorials",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
        )

        response = await gateway.process(request)

        assert response is not None

    @pytest.mark.asyncio
    async def test_gateway_includes_mcp_context(self, gateway):
        """Gateway should include MCP results in LLM context."""
        # Configure gateway to use MCP for queries
        gateway.mcp_enabled = True

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="What's in the knowledge base about testing?",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
            use_mcp=True,
        )

        await gateway.process(request)

        # MCP client should have been called
        gateway.mcp_client.query.assert_called()


class TestErrorHandling:
    """TDD: Tests for error handling in gateway."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider that fails."""
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=Exception("LLM service unavailable"))
        return provider

    @pytest.fixture
    def gateway(self, mock_llm_provider):
        """Create gateway with failing provider."""
        gateway = ChatbotGateway()
        gateway.llm_provider = mock_llm_provider
        return gateway

    @pytest.mark.asyncio
    async def test_gateway_handles_llm_errors(self, gateway):
        """Gateway should handle LLM errors gracefully."""
        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
        )

        response = await gateway.process(request)

        # Should return error response, not raise exception
        assert response is not None
        assert "error" in response.content.lower() or response.error is not None

    @pytest.mark.asyncio
    async def test_gateway_logs_errors(self, gateway, caplog):
        """Gateway should log errors for debugging."""
        import logging

        caplog.set_level(logging.ERROR)

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Hello",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
        )

        await gateway.process(request)

        # Should have logged the error
        assert len(caplog.records) > 0


class TestSystemPrompt:
    """TDD: Tests for system prompt configuration."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="Response",
                tokens_used=10,
                model="gpt-4o-mini",
            )
        )
        return provider

    @pytest.mark.asyncio
    async def test_gateway_uses_system_prompt(self, mock_llm_provider):
        """Gateway should include system prompt in LLM call."""
        config = GatewayConfig(system_prompt="You are a helpful coding assistant.")
        gateway = ChatbotGateway(config)
        gateway.llm_provider = mock_llm_provider

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Help me code",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
        )

        await gateway.process(request)

        call_args = mock_llm_provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        system_msg = next((m for m in messages if m["role"] == "system"), None)

        assert system_msg is not None
        assert "coding assistant" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_gateway_allows_per_request_system_prompt(self, mock_llm_provider):
        """Gateway should allow overriding system prompt per request."""
        gateway = ChatbotGateway()
        gateway.llm_provider = mock_llm_provider

        request = GatewayRequest(
            message=ChatMessage(
                id="msg-1",
                content="Translate to Spanish",
                author=MessageAuthor(id="user-1", username="user"),
                channel_id="ch-1",
                timestamp=datetime.now(),
                is_direct_message=True,
            ),
            platform="discord",
            system_prompt="You are a translation assistant.",
        )

        await gateway.process(request)

        call_args = mock_llm_provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        system_msg = next((m for m in messages if m["role"] == "system"), None)

        assert system_msg is not None
        assert "translation" in system_msg["content"]
