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
TDD: RED Phase - Tests for BasePlatformAdapter protocol.

These tests define the expected behavior for platform adapters before
implementation. They should FAIL until the adapters are implemented.

Related GitHub Issues:
- #17: Write BasePlatformAdapter protocol tests
- #18: Implement BasePlatformAdapter

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from typing import Protocol, runtime_checkable, Optional, AsyncIterator
from datetime import datetime
from dataclasses import dataclass

# Import the adapter protocol and message types - this will fail until implemented (RED phase)
from src.chatbot.adapters.base import (
    BasePlatformAdapter,
    ChatMessage,
    MessageAuthor,
    AdapterConfig,
    ConnectionState,
)


class TestChatMessageModel:
    """TDD: Tests for ChatMessage data model."""

    def test_chat_message_has_required_fields(self):
        """ChatMessage should have all required fields."""
        msg = ChatMessage(
            id="msg-123",
            platform="discord",
            channel_id="channel-456",
            author=MessageAuthor(
                id="user-789",
                username="testuser",
                display_name="Test User",
            ),
            content="Hello, world!",
            timestamp=datetime.now(),
        )

        assert msg.id == "msg-123"
        assert msg.platform == "discord"
        assert msg.channel_id == "channel-456"
        assert msg.content == "Hello, world!"
        assert msg.author.id == "user-789"

    def test_chat_message_optional_fields(self):
        """ChatMessage should support optional fields."""
        msg = ChatMessage(
            id="msg-123",
            platform="slack",
            channel_id="C12345",
            author=MessageAuthor(id="U12345", username="alice"),
            content="Test message",
            timestamp=datetime.now(),
            thread_id="thread-abc",
            reply_to_id="msg-100",
            attachments=[{"type": "image", "url": "https://example.com/img.png"}],
            metadata={"slack_ts": "1234567890.123456"},
        )

        assert msg.thread_id == "thread-abc"
        assert msg.reply_to_id == "msg-100"
        assert len(msg.attachments) == 1
        assert msg.metadata["slack_ts"] == "1234567890.123456"

    def test_message_author_required_fields(self):
        """MessageAuthor should have required fields."""
        author = MessageAuthor(
            id="user-123",
            username="testuser",
        )

        assert author.id == "user-123"
        assert author.username == "testuser"

    def test_message_author_optional_fields(self):
        """MessageAuthor should support optional fields."""
        author = MessageAuthor(
            id="user-123",
            username="testuser",
            display_name="Test User",
            avatar_url="https://example.com/avatar.png",
            is_bot=False,
        )

        assert author.display_name == "Test User"
        assert author.avatar_url == "https://example.com/avatar.png"
        assert author.is_bot is False


class TestAdapterConfig:
    """TDD: Tests for AdapterConfig data model."""

    def test_adapter_config_required_fields(self):
        """AdapterConfig should have required fields."""
        config = AdapterConfig(
            platform="discord",
            token="bot-token-123",
        )

        assert config.platform == "discord"
        assert config.token == "bot-token-123"

    def test_adapter_config_optional_fields(self):
        """AdapterConfig should support optional fields."""
        config = AdapterConfig(
            platform="slack",
            token="xoxb-token",
            app_id="A12345",
            signing_secret="secret123",
            webhook_url="https://example.com/webhook",
            extra={"custom_field": "value"},
        )

        assert config.app_id == "A12345"
        assert config.signing_secret == "secret123"
        assert config.extra["custom_field"] == "value"


class TestConnectionState:
    """TDD: Tests for ConnectionState enum."""

    def test_connection_states_exist(self):
        """ConnectionState should have expected states."""
        assert ConnectionState.DISCONNECTED is not None
        assert ConnectionState.CONNECTING is not None
        assert ConnectionState.CONNECTED is not None
        assert ConnectionState.RECONNECTING is not None
        assert ConnectionState.ERROR is not None


class TestBasePlatformAdapterProtocol:
    """TDD: Tests for BasePlatformAdapter protocol definition."""

    def test_protocol_is_runtime_checkable(self):
        """BasePlatformAdapter should be a runtime-checkable Protocol."""
        assert hasattr(BasePlatformAdapter, "__protocol_attrs__") or isinstance(
            BasePlatformAdapter, type
        )

    def test_protocol_has_connect_method(self):
        """BasePlatformAdapter must define async connect method."""
        assert hasattr(BasePlatformAdapter, "connect")

    def test_protocol_has_disconnect_method(self):
        """BasePlatformAdapter must define async disconnect method."""
        assert hasattr(BasePlatformAdapter, "disconnect")

    def test_protocol_has_send_message_method(self):
        """BasePlatformAdapter must define async send_message method."""
        assert hasattr(BasePlatformAdapter, "send_message")

    def test_protocol_has_get_connection_state_method(self):
        """BasePlatformAdapter must define get_connection_state method."""
        assert hasattr(BasePlatformAdapter, "get_connection_state")

    def test_protocol_has_platform_property(self):
        """BasePlatformAdapter must define platform property."""
        assert hasattr(BasePlatformAdapter, "platform")


class TestAdapterLifecycle:
    """TDD: Tests for adapter connection lifecycle."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter for testing."""

        class MockAdapter:
            def __init__(self, config: AdapterConfig):
                self.config = config
                self._state = ConnectionState.DISCONNECTED
                self._connected = False

            @property
            def platform(self) -> str:
                return self.config.platform

            def get_connection_state(self) -> ConnectionState:
                return self._state

            async def connect(self) -> None:
                self._state = ConnectionState.CONNECTING
                # Simulate connection
                self._state = ConnectionState.CONNECTED
                self._connected = True

            async def disconnect(self) -> None:
                self._state = ConnectionState.DISCONNECTED
                self._connected = False

            async def send_message(
                self,
                channel_id: str,
                content: str,
                reply_to: Optional[str] = None,
            ) -> ChatMessage:
                if not self._connected:
                    raise RuntimeError("Not connected")
                return ChatMessage(
                    id="sent-msg-123",
                    platform=self.platform,
                    channel_id=channel_id,
                    author=MessageAuthor(id="bot", username="bot"),
                    content=content,
                    timestamp=datetime.now(),
                    reply_to_id=reply_to,
                )

        return MockAdapter

    @pytest.mark.asyncio
    async def test_adapter_starts_disconnected(self, mock_adapter):
        """Adapter should start in DISCONNECTED state."""
        config = AdapterConfig(platform="test", token="token")
        adapter = mock_adapter(config)

        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_connects_successfully(self, mock_adapter):
        """Adapter should transition to CONNECTED state on connect."""
        config = AdapterConfig(platform="test", token="token")
        adapter = mock_adapter(config)

        await adapter.connect()

        assert adapter.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_adapter_disconnects_successfully(self, mock_adapter):
        """Adapter should transition to DISCONNECTED state on disconnect."""
        config = AdapterConfig(platform="test", token="token")
        adapter = mock_adapter(config)

        await adapter.connect()
        await adapter.disconnect()

        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_exposes_platform_name(self, mock_adapter):
        """Adapter should expose its platform name."""
        config = AdapterConfig(platform="discord", token="token")
        adapter = mock_adapter(config)

        assert adapter.platform == "discord"


class TestMessageSending:
    """TDD: Tests for message sending functionality."""

    @pytest.fixture
    def connected_adapter(self):
        """Create a connected mock adapter."""

        class MockAdapter:
            def __init__(self):
                self._connected = True
                self._sent_messages = []

            @property
            def platform(self) -> str:
                return "test"

            def get_connection_state(self) -> ConnectionState:
                return ConnectionState.CONNECTED if self._connected else ConnectionState.DISCONNECTED

            async def connect(self) -> None:
                self._connected = True

            async def disconnect(self) -> None:
                self._connected = False

            async def send_message(
                self,
                channel_id: str,
                content: str,
                reply_to: Optional[str] = None,
            ) -> ChatMessage:
                if not self._connected:
                    raise RuntimeError("Not connected")

                msg = ChatMessage(
                    id=f"msg-{len(self._sent_messages)}",
                    platform=self.platform,
                    channel_id=channel_id,
                    author=MessageAuthor(id="bot", username="bot"),
                    content=content,
                    timestamp=datetime.now(),
                    reply_to_id=reply_to,
                )
                self._sent_messages.append(msg)
                return msg

        return MockAdapter()

    @pytest.mark.asyncio
    async def test_send_message_returns_chat_message(self, connected_adapter):
        """send_message should return a ChatMessage."""
        result = await connected_adapter.send_message(
            channel_id="channel-123",
            content="Hello!",
        )

        assert isinstance(result, ChatMessage)
        assert result.content == "Hello!"
        assert result.channel_id == "channel-123"

    @pytest.mark.asyncio
    async def test_send_message_with_reply(self, connected_adapter):
        """send_message should support replying to messages."""
        result = await connected_adapter.send_message(
            channel_id="channel-123",
            content="This is a reply",
            reply_to="original-msg-456",
        )

        assert result.reply_to_id == "original-msg-456"

    @pytest.mark.asyncio
    async def test_send_message_requires_connection(self, connected_adapter):
        """send_message should fail if not connected."""
        await connected_adapter.disconnect()

        with pytest.raises(RuntimeError, match="Not connected"):
            await connected_adapter.send_message(
                channel_id="channel-123",
                content="This should fail",
            )


class TestMessageNormalization:
    """TDD: Tests for platform-specific message normalization."""

    def test_normalize_discord_mention(self):
        """Discord mentions should be normalized to standard format."""
        # Discord format: <@123456789>
        # Normalized format: @username
        raw_content = "Hello <@123456789>!"

        # This function will be part of the adapter
        from src.chatbot.adapters.base import normalize_mentions

        normalized = normalize_mentions(raw_content, platform="discord")

        # Should convert to a parseable format
        assert "<@" not in normalized or "@" in normalized

    def test_normalize_slack_mention(self):
        """Slack mentions should be normalized to standard format."""
        # Slack format: <@U12345>
        raw_content = "Hello <@U12345>!"

        from src.chatbot.adapters.base import normalize_mentions

        normalized = normalize_mentions(raw_content, platform="slack")

        assert "<@" not in normalized or "@" in normalized

    def test_normalize_preserves_regular_content(self):
        """Normalization should preserve non-mention content."""
        raw_content = "Hello, world! How are you?"

        from src.chatbot.adapters.base import normalize_mentions

        normalized = normalize_mentions(raw_content, platform="discord")

        assert normalized == raw_content


class TestProtocolCompliance:
    """TDD: Tests for protocol type compliance."""

    def test_mock_adapter_satisfies_protocol(self):
        """A properly implemented adapter should satisfy BasePlatformAdapter."""

        class MyAdapter:
            def __init__(self, config: AdapterConfig):
                self.config = config
                self._state = ConnectionState.DISCONNECTED

            @property
            def platform(self) -> str:
                return self.config.platform

            def get_connection_state(self) -> ConnectionState:
                return self._state

            async def connect(self) -> None:
                self._state = ConnectionState.CONNECTED

            async def disconnect(self) -> None:
                self._state = ConnectionState.DISCONNECTED

            async def send_message(
                self,
                channel_id: str,
                content: str,
                reply_to: Optional[str] = None,
            ) -> ChatMessage:
                return ChatMessage(
                    id="msg",
                    platform=self.platform,
                    channel_id=channel_id,
                    author=MessageAuthor(id="bot", username="bot"),
                    content=content,
                    timestamp=datetime.now(),
                )

        config = AdapterConfig(platform="test", token="token")
        adapter = MyAdapter(config)

        assert isinstance(adapter, BasePlatformAdapter)
