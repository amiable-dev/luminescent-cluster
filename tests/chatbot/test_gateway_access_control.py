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
TDD: RED Phase - Tests for Gateway Access Control Integration.

These tests define the expected behavior for access control integration
in the chatbot gateway. They should FAIL until the integration is implemented.

Related GitHub Issues:
- #62: Test gateway access control integration (this file)
- #63: Integrate ChatbotAccessController in gateway

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from luminescent_cluster.chatbot.gateway import (
    ChatbotGateway,
    GatewayConfig,
    InvocationPolicy,
    InvocationType,
    GatewayRequest,
    GatewayResponse,
)
from luminescent_cluster.chatbot.adapters.base import ChatMessage, MessageAuthor
from luminescent_cluster.extensions.registry import ExtensionRegistry
from luminescent_cluster.extensions.protocols import ChatbotAccessController


class MockAccessController:
    """Mock access controller for testing."""

    def __init__(
        self,
        channel_allowed: bool = True,
        channel_reason: Optional[str] = None,
        command_allowed: bool = True,
        command_reason: Optional[str] = None,
        allowed_channels: Optional[list[str]] = None,
    ):
        self.channel_allowed = channel_allowed
        self.channel_reason = channel_reason
        self.command_allowed = command_allowed
        self.command_reason = command_reason
        self.allowed_channels = allowed_channels or []
        self.check_channel_calls: list[dict] = []
        self.check_command_calls: list[dict] = []

    def check_channel_access(
        self,
        user_id: str,
        channel_id: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Record call and return configured response."""
        self.check_channel_calls.append(
            {
                "user_id": user_id,
                "channel_id": channel_id,
                "workspace_id": workspace_id,
            }
        )
        return self.channel_allowed, self.channel_reason

    def check_command_access(
        self,
        user_id: str,
        command: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Record call and return configured response."""
        self.check_command_calls.append(
            {
                "user_id": user_id,
                "command": command,
                "workspace_id": workspace_id,
            }
        )
        return self.command_allowed, self.command_reason

    def get_allowed_channels(
        self,
        workspace_id: str,
    ) -> list[str]:
        """Return configured allowed channels."""
        return self.allowed_channels


def create_test_message(
    user_id: str = "user-123",
    channel_id: str = "channel-456",
    content: str = "Hello, bot!",
    is_direct_message: bool = False,
) -> ChatMessage:
    """Create a test message."""
    return ChatMessage(
        id="msg-001",
        content=content,
        author=MessageAuthor(id=user_id, username="testuser"),
        channel_id=channel_id,
        timestamp=datetime.now(),
        is_direct_message=is_direct_message,
    )


def create_mock_llm_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock()
    provider.chat.return_value = MagicMock(
        content="Hello! How can I help?",
        tokens_used=50,
    )
    return provider


@pytest.fixture
def mock_llm_provider():
    """Fixture for mock LLM provider."""
    return create_mock_llm_provider()


@pytest.fixture
def gateway(mock_llm_provider):
    """Create a gateway with test configuration."""
    config = GatewayConfig(
        default_model="test-model",
        max_response_tokens=1000,
        system_prompt="You are a test assistant.",
    )
    policy = InvocationPolicy(
        enabled_types=[InvocationType.ALWAYS],
    )
    gw = ChatbotGateway(
        config=config,
        invocation_policy=policy,
    )
    gw.llm_provider = mock_llm_provider
    return gw


@pytest.fixture
def clean_registry():
    """Reset the extension registry after each test."""
    registry = ExtensionRegistry.get()
    original_controller = registry.chatbot_access_controller
    yield registry
    registry.chatbot_access_controller = original_controller


class TestGatewayAccessControlIntegration:
    """Tests for access control integration in the gateway."""

    @pytest.mark.asyncio
    async def test_gateway_denies_access_when_controller_denies(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """
        Gateway should return None when access controller denies channel access.

        When a ChatbotAccessController is registered and returns (False, reason),
        the gateway should silently deny the request by returning None.
        """
        # Arrange: Register a denying access controller
        controller = MockAccessController(
            channel_allowed=False,
            channel_reason="Channel not in allowlist",
        )
        clean_registry.chatbot_access_controller = controller

        message = create_test_message()
        request = GatewayRequest(
            message=message,
            platform="test",
            workspace_id="ws-789",
        )

        # Act
        response = await gateway.process(request)

        # Assert: Request should be denied (None response)
        assert response is None
        # LLM should not be called
        mock_llm_provider.chat.assert_not_called()
        # Controller should have been called
        assert len(controller.check_channel_calls) == 1
        assert controller.check_channel_calls[0] == {
            "user_id": "user-123",
            "channel_id": "channel-456",
            "workspace_id": "ws-789",
        }

    @pytest.mark.asyncio
    async def test_gateway_allows_access_when_controller_allows(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """
        Gateway should process message when access controller allows.

        When a ChatbotAccessController is registered and returns (True, None),
        the gateway should proceed with normal message processing.
        """
        # Arrange: Register an allowing access controller
        controller = MockAccessController(
            channel_allowed=True,
            channel_reason=None,
        )
        clean_registry.chatbot_access_controller = controller

        message = create_test_message(content="@bot hello")
        request = GatewayRequest(
            message=message,
            platform="test",
            workspace_id="ws-789",
        )

        # Act
        response = await gateway.process(request)

        # Assert: Request should be processed
        assert response is not None
        assert response.content is not None
        # LLM should be called
        mock_llm_provider.chat.assert_called_once()
        # Controller should have been called
        assert len(controller.check_channel_calls) == 1

    @pytest.mark.asyncio
    async def test_gateway_allows_access_when_no_controller_registered(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """
        Gateway should allow all access when no controller is registered.

        This is the permissive OSS default: without a registered access
        controller, all channels and commands are allowed.
        """
        # Arrange: Ensure no controller is registered
        clean_registry.chatbot_access_controller = None

        message = create_test_message()
        request = GatewayRequest(
            message=message,
            platform="test",
            workspace_id="ws-789",
        )

        # Act
        response = await gateway.process(request)

        # Assert: Request should be processed (permissive default)
        assert response is not None
        mock_llm_provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_access_control_uses_correct_user_id(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """Access control should receive the correct user ID from the message."""
        controller = MockAccessController(channel_allowed=True)
        clean_registry.chatbot_access_controller = controller

        message = create_test_message(user_id="specific-user-id")
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        await gateway.process(request)

        assert controller.check_channel_calls[0]["user_id"] == "specific-user-id"

    @pytest.mark.asyncio
    async def test_access_control_uses_correct_channel_id(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """Access control should receive the correct channel ID from the message."""
        controller = MockAccessController(channel_allowed=True)
        clean_registry.chatbot_access_controller = controller

        message = create_test_message(channel_id="specific-channel-id")
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        await gateway.process(request)

        assert controller.check_channel_calls[0]["channel_id"] == "specific-channel-id"

    @pytest.mark.asyncio
    async def test_access_control_uses_correct_workspace_id(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """Access control should receive the correct workspace ID from the request."""
        controller = MockAccessController(channel_allowed=True)
        clean_registry.chatbot_access_controller = controller

        message = create_test_message()
        request = GatewayRequest(message=message, platform="test", workspace_id="my-workspace-123")

        await gateway.process(request)

        assert controller.check_channel_calls[0]["workspace_id"] == "my-workspace-123"

    @pytest.mark.asyncio
    async def test_access_control_uses_empty_workspace_when_none(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """Access control should use empty string when workspace_id is None."""
        controller = MockAccessController(channel_allowed=True)
        clean_registry.chatbot_access_controller = controller

        message = create_test_message()
        request = GatewayRequest(message=message, platform="test", workspace_id=None)

        await gateway.process(request)

        assert controller.check_channel_calls[0]["workspace_id"] == ""

    @pytest.mark.asyncio
    async def test_access_control_checked_before_rate_limiting(
        self, mock_llm_provider, clean_registry
    ):
        """
        Access control should be checked before rate limiting.

        Denied requests should not count against rate limits.
        """
        from luminescent_cluster.chatbot.rate_limiter import TokenBucketRateLimiter, RateLimitConfig

        # Arrange: Create gateway with rate limiting
        config = GatewayConfig(
            default_model="test-model",
            enable_rate_limiting=True,
        )
        policy = InvocationPolicy(enabled_types=[InvocationType.ALWAYS])

        gw = ChatbotGateway(
            config=config,
            invocation_policy=policy,
        )
        gw.llm_provider = mock_llm_provider

        # Wrap rate limiter with spy
        rate_limiter_spy = MagicMock(wraps=gw.rate_limiter)
        gw.rate_limiter = rate_limiter_spy

        # Register denying controller
        controller = MockAccessController(channel_allowed=False)
        clean_registry.chatbot_access_controller = controller

        message = create_test_message()
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        # Act
        response = await gw.process(request)

        # Assert: Access denied, rate limiter not checked
        assert response is None
        rate_limiter_spy.check.assert_not_called()

    @pytest.mark.asyncio
    async def test_access_control_checked_after_invocation_policy(
        self, mock_llm_provider, clean_registry
    ):
        """
        Access control is only checked for messages that match invocation policy.

        If a message doesn't match the invocation policy (e.g., not a mention),
        access control should not be called.
        """
        # Arrange: Create gateway that only responds to mentions
        config = GatewayConfig(default_model="test-model")
        policy = InvocationPolicy(
            enabled_types=[InvocationType.MENTION],
            bot_user_id="BOT123",
        )
        gw = ChatbotGateway(
            config=config,
            invocation_policy=policy,
        )
        gw.llm_provider = mock_llm_provider

        controller = MockAccessController(channel_allowed=True)
        clean_registry.chatbot_access_controller = controller

        # Message that doesn't mention bot
        message = create_test_message(content="hello world")
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        # Act
        response = await gw.process(request)

        # Assert: Invocation policy rejects, access control not called
        assert response is None
        assert len(controller.check_channel_calls) == 0

    @pytest.mark.asyncio
    async def test_access_control_allows_direct_messages(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """
        Access control should work correctly with direct messages.
        """
        controller = MockAccessController(channel_allowed=True)
        clean_registry.chatbot_access_controller = controller

        message = create_test_message(
            channel_id="dm-user-123",
            is_direct_message=True,
        )
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        response = await gateway.process(request)

        assert response is not None
        assert controller.check_channel_calls[0]["channel_id"] == "dm-user-123"


class TestAccessControlProtocolCompliance:
    """Tests to verify MockAccessController matches the protocol."""

    def test_mock_implements_protocol(self):
        """MockAccessController should implement ChatbotAccessController protocol."""
        controller = MockAccessController()
        # Protocol is runtime_checkable
        assert isinstance(controller, ChatbotAccessController)

    def test_check_channel_access_signature(self):
        """check_channel_access should have correct signature."""
        controller = MockAccessController()
        result = controller.check_channel_access(
            user_id="user-1",
            channel_id="ch-1",
            workspace_id="ws-1",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert result[1] is None or isinstance(result[1], str)

    def test_check_command_access_signature(self):
        """check_command_access should have correct signature."""
        controller = MockAccessController()
        result = controller.check_command_access(
            user_id="user-1",
            command="/config",
            workspace_id="ws-1",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)

    def test_get_allowed_channels_signature(self):
        """get_allowed_channels should have correct signature."""
        controller = MockAccessController(allowed_channels=["ch-1", "ch-2"])
        result = controller.get_allowed_channels(workspace_id="ws-1")
        assert isinstance(result, list)
        assert all(isinstance(ch, str) for ch in result)


class TestCommandAccessControl:
    """Tests for command-level access control (future enhancement)."""

    @pytest.mark.asyncio
    async def test_command_access_control_integration(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """
        Command access control should be checked for command messages.

        Note: This test documents future behavior. Command extraction and
        checking can be added when slash commands are implemented in gateway.
        """
        controller = MockAccessController(
            channel_allowed=True,
            command_allowed=False,
            command_reason="Admin only command",
        )
        clean_registry.chatbot_access_controller = controller

        # A message that looks like a command
        message = create_test_message(content="/admin reset-cache")
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        # For now, gateway only checks channel access
        # When command access is added, this test should verify denial
        response = await gateway.process(request)

        # Currently: channel access is allowed, so message is processed
        assert len(controller.check_channel_calls) == 1
        # Future: command access would also be checked
        # assert len(controller.check_command_calls) == 1


class TestAccessControlErrorHandling:
    """Tests for error handling in access control."""

    @pytest.mark.asyncio
    async def test_access_control_exception_denies_request(
        self, gateway, mock_llm_provider, clean_registry
    ):
        """
        If access control raises an exception, gateway should deny the request.

        Fail-closed behavior (ADR-007 Section 1b): security requires denying
        requests when access control cannot be verified. This prevents
        unauthorized access during SSO/database outages.
        """
        # Create a controller that raises an exception
        controller = MockAccessController()
        controller.check_channel_access = MagicMock(
            side_effect=Exception("Database connection failed")
        )
        clean_registry.chatbot_access_controller = controller

        message = create_test_message()
        request = GatewayRequest(message=message, platform="test", workspace_id="ws-789")

        # Act
        response = await gateway.process(request)

        # Assert: Should fail-closed and deny the message
        assert response is not None
        assert response.error == "access_control_error"
        mock_llm_provider.chat.assert_not_called()
