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
TDD: Tests for gateway security - fail-closed behavior.

Part of Issue #76: Fix Gateway Fail-Open Security Issue.

ADR Reference: ADR-007 Cross-ADR Integration Guide, Section 1b
"""

import pytest
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.chatbot.gateway import (
    ChatbotGateway,
    GatewayConfig,
    InvocationPolicy,
    InvocationType,
    GatewayRequest,
    GatewayResponse,
)
from src.chatbot.adapters.base import ChatMessage, MessageAuthor
from src.extensions.registry import ExtensionRegistry


class TestGatewayFailClosedSecurity:
    """Tests that gateway fails closed on access control exceptions."""

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
            tokens_used=100,
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
    async def test_gateway_fails_closed_on_access_control_exception(
        self, gateway, test_message
    ):
        """Gateway denies request when access control raises exception."""
        registry = ExtensionRegistry.get()
        mock_controller = MagicMock()
        mock_controller.check_channel_access.side_effect = Exception("SSO service unavailable")
        registry.chatbot_access_controller = mock_controller

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        # Should return None (deny) or error response, NOT process the request
        response = await gateway.process(request)

        # Either returns None (silently denied) or an error response
        if response is not None:
            assert response.error is not None
            assert "access" in response.error.lower() or "denied" in response.error.lower()

    @pytest.mark.asyncio
    async def test_gateway_logs_access_control_exception_at_error_level(
        self, gateway, test_message, caplog
    ):
        """Gateway logs access control exceptions at ERROR level, not WARNING."""
        registry = ExtensionRegistry.get()
        mock_controller = MagicMock()
        mock_controller.check_channel_access.side_effect = Exception("SSO service unavailable")
        registry.chatbot_access_controller = mock_controller

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        with caplog.at_level(logging.ERROR):
            await gateway.process(request)

        # Should log at ERROR level, not WARNING
        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_logs) > 0, "Should log at ERROR level on access control failure"

    @pytest.mark.asyncio
    async def test_gateway_does_not_call_llm_on_access_control_exception(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway does not call LLM when access control fails."""
        registry = ExtensionRegistry.get()
        mock_controller = MagicMock()
        mock_controller.check_channel_access.side_effect = Exception("SSO down")
        registry.chatbot_access_controller = mock_controller

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        # LLM should NOT be called when access control fails
        mock_llm_provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_gateway_allows_when_access_control_succeeds(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway allows request when access control succeeds."""
        registry = ExtensionRegistry.get()
        mock_controller = MagicMock()
        mock_controller.check_channel_access.return_value = (True, None)
        registry.chatbot_access_controller = mock_controller

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        response = await gateway.process(request)

        # Should process the request
        mock_llm_provider.chat.assert_called_once()
        assert response is not None
        assert response.error is None

    @pytest.mark.asyncio
    async def test_gateway_denies_when_access_control_returns_false(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway denies request when access control returns (False, reason)."""
        registry = ExtensionRegistry.get()
        mock_controller = MagicMock()
        mock_controller.check_channel_access.return_value = (False, "Not in allowlist")
        registry.chatbot_access_controller = mock_controller

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        response = await gateway.process(request)

        # Should deny (return None for silent deny)
        assert response is None
        mock_llm_provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_gateway_works_without_access_controller(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway works normally when no access controller is registered (OSS mode)."""
        registry = ExtensionRegistry.get()
        # Ensure no controller is registered
        assert registry.chatbot_access_controller is None

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        response = await gateway.process(request)

        # Should process the request
        mock_llm_provider.chat.assert_called_once()
        assert response is not None
