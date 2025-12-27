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
TDD: RED Phase - Tests for Slack adapter.

These tests define the expected behavior for the Slack platform adapter
before implementation. They should FAIL until the adapter is implemented.

Related GitHub Issues:
- #44: Test SlackAdapter connection lifecycle
- #45: Test Slack message parsing
- #46: Implement SlackAdapter
- #47: Test Slack thread context
- #48: Test Slack App Home tab
- #49: Implement Slack App Home

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from datetime import datetime
from typing import Optional, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import the adapter - this will fail until implemented (RED phase)
from src.chatbot.adapters.slack_adapter import (
    SlackAdapter,
    SlackConfig,
    SlackMessage,
    SlackBlock,
    SlackAppHomeView,
)

from src.chatbot.adapters.base import (
    BasePlatformAdapter,
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)


# =============================================================================
# Slack Configuration Tests
# =============================================================================


class TestSlackConfig:
    """TDD: Tests for Slack configuration."""

    def test_config_has_required_fields(self):
        """SlackConfig should have required fields."""
        config = SlackConfig(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
            signing_secret="test-signing-secret",
        )

        assert config.bot_token == "xoxb-test-token"
        assert config.app_token == "xapp-test-token"
        assert config.signing_secret == "test-signing-secret"

    def test_config_has_optional_fields(self):
        """SlackConfig should support optional fields."""
        config = SlackConfig(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
            signing_secret="test-signing-secret",
            socket_mode=True,
            default_channel="C123456",
        )

        assert config.socket_mode is True
        assert config.default_channel == "C123456"

    def test_config_defaults_to_socket_mode(self):
        """SlackConfig should default to Socket Mode."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )

        assert config.socket_mode is True


# =============================================================================
# Connection Lifecycle Tests (Issue #44)
# =============================================================================


class TestSlackAdapterConnection:
    """TDD: Tests for Slack adapter connection lifecycle."""

    @pytest.fixture
    def config(self):
        """Create test Slack config."""
        return SlackConfig(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
            signing_secret="test-secret",
        )

    def test_adapter_implements_protocol(self, config):
        """SlackAdapter should implement BasePlatformAdapter."""
        adapter = SlackAdapter(config)
        assert isinstance(adapter, BasePlatformAdapter)

    def test_adapter_has_platform_name(self, config):
        """SlackAdapter should identify as 'slack' platform."""
        adapter = SlackAdapter(config)
        assert adapter.platform == "slack"

    def test_adapter_starts_disconnected(self, config):
        """SlackAdapter should start in DISCONNECTED state."""
        adapter = SlackAdapter(config)
        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_connects_with_socket_mode(self, config):
        """SlackAdapter should connect using Socket Mode."""
        adapter = SlackAdapter(config)

        with patch.object(adapter, "_socket_mode_handler") as mock_handler:
            mock_handler.connect_async = AsyncMock()
            mock_handler.start_async = AsyncMock()

            await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_adapter_disconnects_successfully(self, config):
        """SlackAdapter should disconnect gracefully."""
        adapter = SlackAdapter(config)

        with patch.object(adapter, "_socket_mode_handler") as mock_handler:
            mock_handler.connect_async = AsyncMock()
            mock_handler.start_async = AsyncMock()
            mock_handler.close_async = AsyncMock()

            await adapter.connect()
            await adapter.disconnect()

            assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_handles_connection_error(self, config):
        """SlackAdapter should handle connection errors."""
        adapter = SlackAdapter(config)

        # Mock the _connect_socket_mode method to raise an error
        with patch.object(
            adapter, "_connect_socket_mode", side_effect=Exception("Connection failed")
        ):
            with pytest.raises(Exception):
                await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.ERROR

    def test_adapter_exposes_bot_user_id(self, config):
        """SlackAdapter should expose bot user ID."""
        adapter = SlackAdapter(config)
        adapter._bot_user_id = "U123456789"

        assert adapter.bot_user_id == "U123456789"


# =============================================================================
# Message Parsing Tests (Issue #45)
# =============================================================================


class TestSlackMessageParsing:
    """TDD: Tests for Slack message parsing and normalization."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        return SlackAdapter(config)

    def test_parse_simple_message(self, adapter):
        """Should parse simple Slack message to ChatMessage."""
        slack_event = {
            "type": "message",
            "text": "Hello, world!",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
            "event_ts": "1234567890.123456",
        }

        # Mock user info lookup
        adapter._user_cache = {"U123456": {"name": "testuser", "real_name": "Test User"}}

        chat_msg = adapter.parse_message(slack_event)

        assert chat_msg.content == "Hello, world!"
        assert chat_msg.author.id == "U123456"
        assert chat_msg.channel_id == "C789012"
        assert chat_msg.platform == "slack"

    def test_parse_message_with_user_mention(self, adapter):
        """Should parse message with user mention."""
        slack_event = {
            "type": "message",
            "text": "Hello <@U987654>!",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
        }

        adapter._user_cache = {
            "U123456": {"name": "sender", "real_name": "Sender"},
            "U987654": {"name": "mentioned", "real_name": "Mentioned User"},
        }

        chat_msg = adapter.parse_message(slack_event)

        assert "<@U987654>" in chat_msg.content
        assert "U987654" in chat_msg.metadata.get("mentions", [])

    def test_parse_message_with_channel_mention(self, adapter):
        """Should parse message with channel mention."""
        slack_event = {
            "type": "message",
            "text": "Check out <#C111222>!",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
        }

        adapter._user_cache = {"U123456": {"name": "user1"}}

        chat_msg = adapter.parse_message(slack_event)

        assert "<#C111222>" in chat_msg.content
        assert "channel_mentions" in chat_msg.metadata

    def test_parse_message_with_emoji(self, adapter):
        """Should handle Slack emoji format."""
        slack_event = {
            "type": "message",
            "text": "Hello :wave: :custom_emoji:",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
        }

        adapter._user_cache = {"U123456": {"name": "user1"}}

        chat_msg = adapter.parse_message(slack_event)

        assert ":wave:" in chat_msg.content or "emojis" in chat_msg.metadata

    def test_parse_message_with_file_attachment(self, adapter):
        """Should parse file attachments."""
        slack_event = {
            "type": "message",
            "text": "Check this file",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
            "files": [
                {
                    "id": "F123456",
                    "name": "document.pdf",
                    "mimetype": "application/pdf",
                    "url_private": "https://files.slack.com/...",
                    "size": 12345,
                }
            ],
        }

        adapter._user_cache = {"U123456": {"name": "user1"}}

        chat_msg = adapter.parse_message(slack_event)

        assert len(chat_msg.attachments) == 1
        assert chat_msg.attachments[0]["filename"] == "document.pdf"
        assert chat_msg.attachments[0]["content_type"] == "application/pdf"

    def test_parse_bot_message(self, adapter):
        """Should identify messages from bots."""
        slack_event = {
            "type": "message",
            "subtype": "bot_message",
            "text": "I am a bot",
            "bot_id": "B123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
        }

        chat_msg = adapter.parse_message(slack_event)

        assert chat_msg.author.is_bot is True

    def test_parse_dm_message(self, adapter):
        """Should identify direct messages."""
        slack_event = {
            "type": "message",
            "text": "Private message",
            "user": "U123456",
            "channel": "D789012",  # DM channels start with D
            "ts": "1234567890.123456",
            "channel_type": "im",
        }

        adapter._user_cache = {"U123456": {"name": "user1"}}

        chat_msg = adapter.parse_message(slack_event)

        assert chat_msg.is_direct_message is True

    def test_parse_message_with_blocks(self, adapter):
        """Should handle Block Kit messages."""
        slack_event = {
            "type": "message",
            "text": "Fallback text",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Rich *formatted* text"},
                },
                {
                    "type": "divider",
                },
            ],
        }

        adapter._user_cache = {"U123456": {"name": "user1"}}

        chat_msg = adapter.parse_message(slack_event)

        # Should have blocks in metadata or use fallback text
        assert "blocks" in chat_msg.metadata or chat_msg.content == "Fallback text"


# =============================================================================
# Message Sending Tests
# =============================================================================


class TestSlackMessageSending:
    """TDD: Tests for sending messages via Slack."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter in connected state."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._bot_user_id = "U123456789"
        return adapter

    @pytest.mark.asyncio
    async def test_send_simple_message(self, adapter):
        """Should send simple text message."""
        adapter._web_client = MagicMock()
        adapter._web_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123456", "channel": "C123"}
        )

        result = await adapter.send_message("C123456", "Hello!")

        adapter._web_client.chat_postMessage.assert_called_once()
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_send_message_to_thread(self, adapter):
        """Should send message to thread."""
        adapter._web_client = MagicMock()
        adapter._web_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123457", "channel": "C123"}
        )

        result = await adapter.send_message(
            "C123456",
            "Thread reply",
            reply_to="1234567890.123456",
        )

        call_kwargs = adapter._web_client.chat_postMessage.call_args.kwargs
        assert call_kwargs.get("thread_ts") == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_send_message_with_blocks(self, adapter):
        """Should send message with Block Kit blocks."""
        adapter._web_client = MagicMock()
        adapter._web_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123456", "channel": "C123"}
        )

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Bold* text"}},
        ]

        result = await adapter.send_message("C123456", "Fallback", blocks=blocks)

        call_kwargs = adapter._web_client.chat_postMessage.call_args.kwargs
        assert "blocks" in call_kwargs

    @pytest.mark.asyncio
    async def test_send_message_requires_connection(self):
        """Should raise error if not connected."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._connection_state = ConnectionState.DISCONNECTED

        with pytest.raises(Exception) as exc_info:
            await adapter.send_message("C123456", "Hello!")

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_send_ephemeral_message(self, adapter):
        """Should send ephemeral message visible only to one user."""
        adapter._web_client = MagicMock()
        adapter._web_client.chat_postEphemeral = AsyncMock(
            return_value={"ok": True, "message_ts": "1234567890.123456"}
        )

        await adapter.send_ephemeral("C123456", "U789012", "Only you can see this")

        adapter._web_client.chat_postEphemeral.assert_called_once()
        call_kwargs = adapter._web_client.chat_postEphemeral.call_args.kwargs
        assert call_kwargs.get("user") == "U789012"


# =============================================================================
# Thread Context Tests (Issue #47)
# =============================================================================


class TestSlackThreadContext:
    """TDD: Tests for Slack thread context handling."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._user_cache = {"U123456": {"name": "user1"}}
        return adapter

    def test_extract_thread_ts_from_reply(self, adapter):
        """Should extract thread_ts from threaded message."""
        slack_event = {
            "type": "message",
            "text": "Thread reply",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123457",
            "thread_ts": "1234567890.123456",  # Parent message ts
        }

        chat_msg = adapter.parse_message(slack_event)

        assert chat_msg.thread_id == "1234567890.123456"

    def test_parent_message_has_no_thread_id(self, adapter):
        """Parent message should not have thread_id."""
        slack_event = {
            "type": "message",
            "text": "Parent message",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
            # No thread_ts = parent message
        }

        chat_msg = adapter.parse_message(slack_event)

        assert chat_msg.thread_id is None

    def test_broadcast_reply_detected(self, adapter):
        """Should detect broadcast replies."""
        slack_event = {
            "type": "message",
            "text": "Broadcast reply",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123457",
            "thread_ts": "1234567890.123456",
            "subtype": "thread_broadcast",
        }

        chat_msg = adapter.parse_message(slack_event)

        assert chat_msg.metadata.get("is_broadcast") is True

    @pytest.mark.asyncio
    async def test_reply_to_thread(self, adapter):
        """Should send reply to existing thread."""
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._web_client = MagicMock()
        adapter._web_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123458", "channel": "C123"}
        )

        await adapter.send_message(
            "C789012",
            "My reply",
            reply_to="1234567890.123456",
        )

        call_kwargs = adapter._web_client.chat_postMessage.call_args.kwargs
        assert call_kwargs["thread_ts"] == "1234567890.123456"


# =============================================================================
# App Home Tests (Issue #48)
# =============================================================================


class TestSlackAppHome:
    """TDD: Tests for Slack App Home tab."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        return adapter

    def test_create_app_home_view(self):
        """Should create App Home view with blocks."""
        view = SlackAppHomeView(
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "Welcome!"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": "Hello there"}},
            ]
        )

        view_dict = view.to_dict()

        assert view_dict["type"] == "home"
        assert len(view_dict["blocks"]) == 2

    @pytest.mark.asyncio
    async def test_publish_app_home(self, adapter):
        """Should publish App Home view for user."""
        adapter._web_client = MagicMock()
        adapter._web_client.views_publish = AsyncMock(return_value={"ok": True})

        view = SlackAppHomeView(
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": "Your dashboard"}},
            ]
        )

        await adapter.publish_app_home("U123456", view)

        adapter._web_client.views_publish.assert_called_once()
        call_kwargs = adapter._web_client.views_publish.call_args.kwargs
        assert call_kwargs["user_id"] == "U123456"

    @pytest.mark.asyncio
    async def test_handle_app_home_opened(self, adapter):
        """Should handle app_home_opened event."""
        home_views = []

        async def on_app_home_opened(user_id: str):
            home_views.append(user_id)

        adapter.on_app_home_opened = on_app_home_opened

        event = {
            "type": "app_home_opened",
            "user": "U123456",
            "tab": "home",
        }

        await adapter._handle_app_home_opened(event)

        assert "U123456" in home_views

    def test_app_home_view_with_actions(self):
        """Should support interactive elements in App Home."""
        view = SlackAppHomeView(
            blocks=[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Click me"},
                            "action_id": "button_click",
                        }
                    ],
                }
            ]
        )

        view_dict = view.to_dict()

        assert view_dict["blocks"][0]["type"] == "actions"


# =============================================================================
# Slash Command Tests
# =============================================================================


class TestSlackSlashCommands:
    """TDD: Tests for Slack slash command handling."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        return adapter

    def test_parse_slash_command(self, adapter):
        """Should parse incoming slash command."""
        command_payload = {
            "command": "/ask",
            "text": "What is Python?",
            "user_id": "U123456",
            "user_name": "testuser",
            "channel_id": "C789012",
            "response_url": "https://hooks.slack.com/...",
        }

        parsed = adapter.parse_slash_command(command_payload)

        assert parsed["command"] == "/ask"
        assert parsed["text"] == "What is Python?"
        assert parsed["user_id"] == "U123456"

    @pytest.mark.asyncio
    async def test_respond_to_slash_command(self, adapter):
        """Should respond to slash command."""
        adapter._web_client = MagicMock()

        # Mock aiohttp properly with nested async context managers
        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_client_session.return_value = mock_session

            await adapter.respond_to_command(
                response_url="https://hooks.slack.com/...",
                text="Here's your answer!",
            )

            # Verify the call was made
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_respond_ephemeral_to_command(self, adapter):
        """Should respond with ephemeral message."""
        # Mock aiohttp properly with nested async context managers
        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_client_session.return_value = mock_session

            await adapter.respond_to_command(
                response_url="https://hooks.slack.com/...",
                text="Only you can see this",
                response_type="ephemeral",
            )


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestSlackEventHandling:
    """TDD: Tests for Slack event handling."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter with mock client."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._bot_user_id = "U999999"
        adapter._user_cache = {"U123456": {"name": "user1"}}
        return adapter

    @pytest.mark.asyncio
    async def test_on_message_callback(self, adapter):
        """Should invoke callback when message received."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        slack_event = {
            "type": "message",
            "text": "Test message",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
        }

        await adapter._handle_message_event(slack_event)

        assert len(messages_received) == 1
        assert messages_received[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, adapter):
        """Should ignore messages from the bot itself."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message
        adapter._user_cache["U999999"] = {"name": "bot"}

        slack_event = {
            "type": "message",
            "text": "Bot message",
            "user": "U999999",  # Same as bot
            "channel": "C789012",
            "ts": "1234567890.123456",
        }

        await adapter._handle_message_event(slack_event)

        assert len(messages_received) == 0

    @pytest.mark.asyncio
    async def test_handles_message_changed(self, adapter):
        """Should handle message_changed subtype."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        slack_event = {
            "type": "message",
            "subtype": "message_changed",
            "message": {
                "text": "Edited message",
                "user": "U123456",
                "ts": "1234567890.123456",
            },
            "channel": "C789012",
        }

        await adapter._handle_message_event(slack_event)

        # Should either handle or ignore edits
        assert len(messages_received) <= 1


# =============================================================================
# Gateway Integration Tests
# =============================================================================


class TestSlackGatewayIntegration:
    """TDD: Tests for Slack adapter integration with ChatbotGateway."""

    @pytest.fixture
    def adapter(self):
        """Create test Slack adapter."""
        config = SlackConfig(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        adapter = SlackAdapter(config)
        adapter._user_cache = {"U123456": {"name": "user1", "real_name": "User One"}}
        return adapter

    def test_creates_gateway_request_from_message(self, adapter):
        """Should create GatewayRequest from Slack event."""
        slack_event = {
            "type": "message",
            "text": "Hello bot!",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123456",
            "team": "T111222",
        }

        gateway_request = adapter.create_gateway_request(slack_event)

        assert gateway_request.platform == "slack"
        assert gateway_request.message.content == "Hello bot!"
        assert gateway_request.workspace_id == "T111222"

    def test_creates_gateway_request_from_dm(self, adapter):
        """Should create GatewayRequest from DM."""
        slack_event = {
            "type": "message",
            "text": "Private message",
            "user": "U123456",
            "channel": "D789012",
            "ts": "1234567890.123456",
            "channel_type": "im",
        }

        gateway_request = adapter.create_gateway_request(slack_event)

        assert gateway_request.message.is_direct_message is True

    def test_creates_gateway_request_with_thread(self, adapter):
        """Should include thread_id in GatewayRequest."""
        slack_event = {
            "type": "message",
            "text": "Thread reply",
            "user": "U123456",
            "channel": "C789012",
            "ts": "1234567890.123457",
            "thread_ts": "1234567890.123456",
        }

        gateway_request = adapter.create_gateway_request(slack_event)

        assert gateway_request.thread_id == "1234567890.123456"
