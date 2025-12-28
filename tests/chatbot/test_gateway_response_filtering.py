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
TDD: Tests for response filtering in gateway.

Part of Issue #74: Integrate Response Filtering in Gateway.

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
    GatewayResponse,
)
from src.chatbot.adapters.base import ChatMessage, MessageAuthor
from src.extensions.registry import ExtensionRegistry


class TestResponseFilterProtocol:
    """Tests that ResponseFilter protocol exists and is properly defined."""

    def test_response_filter_protocol_exists(self):
        """ResponseFilter protocol is defined in protocols module."""
        from src.extensions.protocols import ResponseFilter

        assert ResponseFilter is not None

    def test_response_filter_version_exists(self):
        """ResponseFilter has a version constant."""
        from src.extensions.protocols import RESPONSE_FILTER_VERSION

        assert RESPONSE_FILTER_VERSION is not None

    def test_response_filter_version_is_semver(self):
        """ResponseFilter version follows SemVer."""
        import re
        from src.extensions.protocols import RESPONSE_FILTER_VERSION

        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, RESPONSE_FILTER_VERSION)


class TestResponseFilterRegistry:
    """Tests that ExtensionRegistry has response_filter slot."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_registry_has_response_filter_slot(self):
        """ExtensionRegistry has response_filter attribute."""
        registry = ExtensionRegistry.get()
        assert hasattr(registry, "response_filter")

    def test_registry_response_filter_defaults_to_none(self):
        """response_filter defaults to None."""
        registry = ExtensionRegistry.get()
        assert registry.response_filter is None

    def test_registry_status_includes_response_filter(self):
        """get_status() includes response_filter status."""
        registry = ExtensionRegistry.get()
        status = registry.get_status()
        assert "response_filter" in status


class TestGatewayResponseFiltering:
    """Tests that gateway applies response filtering."""

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
            content="LLM response with password=secret123",
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
            content="Show config",
            author=MessageAuthor(
                id="user-789",
                username="testuser",
                display_name="Test User",
                is_bot=False,
            ),
            timestamp=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_gateway_applies_response_filter(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway filters LLM response through ResponseFilter."""
        registry = ExtensionRegistry.get()
        mock_filter = MagicMock()
        mock_filter.filter_response.return_value = "filtered response"
        registry.response_filter = mock_filter

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        response = await gateway.process(request)

        # Filter should be called with response content
        mock_filter.filter_response.assert_called_once()
        assert response.content == "filtered response"

    @pytest.mark.asyncio
    async def test_gateway_passes_channel_visibility_to_filter(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway passes is_public_channel to filter."""
        registry = ExtensionRegistry.get()
        mock_filter = MagicMock()
        mock_filter.filter_response.return_value = "filtered"
        registry.response_filter = mock_filter

        # Test with public channel (not a DM)
        test_message.is_direct_message = False
        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        await gateway.process(request)

        # Check that is_public_channel was passed
        call_kwargs = mock_filter.filter_response.call_args
        assert "is_public_channel" in call_kwargs.kwargs or len(call_kwargs.args) >= 3

    @pytest.mark.asyncio
    async def test_gateway_skips_filter_when_not_configured(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway skips filtering when no filter registered."""
        registry = ExtensionRegistry.get()
        assert registry.response_filter is None

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        # Should not raise, should return unfiltered response
        response = await gateway.process(request)

        assert response is not None
        assert response.content == "LLM response with password=secret123"

    @pytest.mark.asyncio
    async def test_gateway_handles_filter_exception_gracefully(
        self, gateway, test_message, mock_llm_provider
    ):
        """Gateway handles filter exceptions without crashing."""
        registry = ExtensionRegistry.get()
        mock_filter = MagicMock()
        mock_filter.filter_response.side_effect = Exception("Filter failed")
        registry.response_filter = mock_filter

        request = GatewayRequest(
            message=test_message,
            platform="test",
            workspace_id="ws-123",
        )

        # Should return original response, not crash
        response = await gateway.process(request)

        assert response is not None
        # Original response should be returned on filter failure
        assert response.content == "LLM response with password=secret123"
