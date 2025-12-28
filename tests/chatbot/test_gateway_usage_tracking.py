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
TDD: Tests for usage tracking in gateway.

Part of Issue #75: Add Usage Tracking After LLM Response.

ADR Reference: ADR-007 Cross-ADR Integration Guide
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.chatbot.gateway import (
    ChatbotGateway,
    GatewayConfig,
    InvocationPolicy,
    InvocationType,
    GatewayRequest,
)
from src.chatbot.adapters.base import ChatMessage, MessageAuthor
from src.extensions.registry import ExtensionRegistry


class TestGatewayUsageTracking:
    """Tests that gateway tracks usage after LLM response."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=MagicMock(
            content="Test response",
            tokens_used=150,
            model="test-model",
        ))
        return provider

    @pytest.fixture
    def gateway(self, mock_llm_provider):
        """Create a gateway with mock LLM provider."""
        config = GatewayConfig(
            system_prompt="You are a test assistant.",
            enable_context=False,
            enable_rate_limiting=False,
        )
        policy = InvocationPolicy(
            enabled_types=[InvocationType.ALWAYS],
        )
        gateway = ChatbotGateway(
            config=config,
            invocation_policy=policy,
        )
        gateway.llm_provider = mock_llm_provider
        return gateway

    @pytest.fixture
    def test_message(self):
        """Create a test message."""
        return ChatMessage(
            id="msg-123",
            channel_id="channel-456",
            content="Hello bot!",
            author=MessageAuthor(
                id="user-789",
                username="testuser",
                display_name="Test User",
                is_bot=False,
            ),
            timestamp=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_gateway_tracks_usage_after_llm_response(
        self, gateway, test_message
    ):
        """Gateway calls usage_tracker.track() after successful LLM response."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock()
        registry.usage_tracker = mock_tracker

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        # Usage tracker should be called
        mock_tracker.track.assert_called_once()

    @pytest.mark.asyncio
    async def test_gateway_tracks_correct_operation_type(
        self, gateway, test_message
    ):
        """Gateway tracks 'chatbot_response' operation type."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock()
        registry.usage_tracker = mock_tracker

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        call_args = mock_tracker.track.call_args
        assert call_args.kwargs.get("operation") == "chatbot_response" or \
               call_args.args[0] == "chatbot_response"

    @pytest.mark.asyncio
    async def test_gateway_tracks_token_count(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway tracks correct token count from LLM response."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock()
        registry.usage_tracker = mock_tracker

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        call_args = mock_tracker.track.call_args
        tokens = call_args.kwargs.get("tokens") or call_args.args[1]
        assert tokens == 150  # matches mock_llm_provider

    @pytest.mark.asyncio
    async def test_gateway_tracks_metadata(
        self, gateway, test_message
    ):
        """Gateway includes relevant metadata in usage tracking."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock()
        registry.usage_tracker = mock_tracker

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        call_args = mock_tracker.track.call_args
        metadata = call_args.kwargs.get("metadata") or call_args.args[2]

        # Should include relevant context
        assert "user_id" in metadata
        assert "workspace_id" in metadata or "platform" in metadata

    @pytest.mark.asyncio
    async def test_gateway_skips_tracking_when_not_configured(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway skips usage tracking when no tracker registered."""
        registry = ExtensionRegistry.get()
        assert registry.usage_tracker is None

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        # Should not raise, should return response normally
        response = await gateway.process(request)

        assert response is not None
        assert response.content == "Test response"

    @pytest.mark.asyncio
    async def test_gateway_handles_tracker_exception_gracefully(
        self, gateway, test_message
    ):
        """Gateway handles usage tracker exceptions without crashing."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock()
        mock_tracker.track.side_effect = Exception("Tracker failed")
        registry.usage_tracker = mock_tracker

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        # Should return response despite tracker failure
        response = await gateway.process(request)

        assert response is not None
        assert response.content == "Test response"

    @pytest.mark.asyncio
    async def test_gateway_does_not_track_on_llm_error(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway does not track usage when LLM request fails."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock()
        registry.usage_tracker = mock_tracker

        # Make LLM fail
        mock_llm_provider.chat.side_effect = Exception("LLM unavailable")

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        # Should NOT track usage on failure
        mock_tracker.track.assert_not_called()
