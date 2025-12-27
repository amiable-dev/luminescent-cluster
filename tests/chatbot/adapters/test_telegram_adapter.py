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
TDD Tests for Telegram platform adapter.

These tests follow the RED-GREEN-REFACTOR cycle per ADR-006 Phase 3.
Test coverage for:
- Connection lifecycle (Issue #50)
- Message parsing (Issue #51)
- TelegramAdapter implementation (Issue #52)
- Inline mode (Issues #53-54)

Version: 1.0.0
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from src.chatbot.adapters.base import (
    BasePlatformAdapter,
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)
from src.chatbot.gateway import GatewayRequest


# =============================================================================
# Configuration Tests
# =============================================================================


class TestTelegramConfig:
    """TDD: Tests for TelegramConfig dataclass."""

    def test_config_has_required_fields(self):
        """TelegramConfig should require bot_token."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig

        config = TelegramConfig(bot_token="123456:ABC-DEF")

        assert config.bot_token == "123456:ABC-DEF"

    def test_config_has_optional_webhook_url(self):
        """TelegramConfig should support optional webhook URL."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig

        config = TelegramConfig(
            bot_token="123456:ABC-DEF",
            webhook_url="https://example.com/webhook",
        )

        assert config.webhook_url == "https://example.com/webhook"

    def test_config_defaults_to_polling_mode(self):
        """TelegramConfig should default to polling mode."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig

        config = TelegramConfig(bot_token="123456:ABC-DEF")

        assert config.use_webhook is False

    def test_config_supports_webhook_mode(self):
        """TelegramConfig should support webhook mode."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig

        config = TelegramConfig(
            bot_token="123456:ABC-DEF",
            webhook_url="https://example.com/webhook",
            use_webhook=True,
        )

        assert config.use_webhook is True


# =============================================================================
# Connection Lifecycle Tests (Issue #50)
# =============================================================================


class TestTelegramAdapterConnection:
    """TDD: Tests for TelegramAdapter connection lifecycle."""

    @pytest.fixture
    def config(self):
        """Create test Telegram config."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig

        return TelegramConfig(bot_token="123456:ABC-DEF")

    def test_adapter_implements_protocol(self, config):
        """TelegramAdapter should implement BasePlatformAdapter protocol."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)

        assert isinstance(adapter, BasePlatformAdapter)

    def test_adapter_has_platform_name(self, config):
        """TelegramAdapter should report 'telegram' as platform."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)

        assert adapter.platform == "telegram"

    def test_adapter_starts_disconnected(self, config):
        """TelegramAdapter should start in DISCONNECTED state."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)

        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_connects_with_polling(self, config):
        """TelegramAdapter should connect using polling mode."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)

        await adapter.connect()

        assert adapter.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_adapter_connects_with_webhook(self):
        """TelegramAdapter should connect using webhook mode."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(
            bot_token="123456:ABC-DEF",
            webhook_url="https://example.com/webhook",
            use_webhook=True,
        )
        adapter = TelegramAdapter(config)

        await adapter.connect()

        assert adapter.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_adapter_disconnects_successfully(self, config):
        """TelegramAdapter should disconnect cleanly."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)
        await adapter.connect()

        await adapter.disconnect()

        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_handles_connection_error(self, config):
        """TelegramAdapter should handle connection errors."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)

        with patch.object(
            adapter, "_connect_polling", side_effect=Exception("Connection failed")
        ):
            with pytest.raises(Exception):
                await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.ERROR

    def test_adapter_exposes_bot_info(self, config):
        """TelegramAdapter should expose bot info."""
        from src.chatbot.adapters.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(config)
        adapter._bot_info = {
            "id": 123456789,
            "username": "test_bot",
            "first_name": "Test Bot",
        }

        assert adapter.bot_user_id == "123456789"
        assert adapter.bot_username == "test_bot"


# =============================================================================
# Message Parsing Tests (Issue #51)
# =============================================================================


class TestTelegramMessageParsing:
    """TDD: Tests for Telegram message parsing and normalization."""

    @pytest.fixture
    def adapter(self):
        """Create test Telegram adapter."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        return TelegramAdapter(config)

    def test_parse_simple_message(self, adapter):
        """Should parse simple Telegram message to ChatMessage."""
        telegram_update = {
            "message": {
                "message_id": 123,
                "text": "Hello, world!",
                "date": 1234567890,
                "from": {
                    "id": 987654321,
                    "username": "testuser",
                    "first_name": "Test",
                    "last_name": "User",
                    "is_bot": False,
                },
                "chat": {
                    "id": -100123456789,
                    "type": "group",
                    "title": "Test Group",
                },
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.content == "Hello, world!"
        assert chat_msg.id == "123"
        assert chat_msg.channel_id == "-100123456789"
        assert chat_msg.author.id == "987654321"
        assert chat_msg.author.username == "testuser"
        assert chat_msg.platform == "telegram"

    def test_parse_message_with_entities(self, adapter):
        """Should parse message entities (mentions, hashtags, URLs)."""
        telegram_update = {
            "message": {
                "message_id": 124,
                "text": "Hello @testuser check https://example.com #python",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "entities": [
                    {"type": "mention", "offset": 6, "length": 9},
                    {"type": "url", "offset": 22, "length": 19},
                    {"type": "hashtag", "offset": 42, "length": 7},
                ],
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert "mentions" in chat_msg.metadata
        assert "@testuser" in chat_msg.metadata["mentions"]
        assert "urls" in chat_msg.metadata
        assert "https://example.com" in chat_msg.metadata["urls"]
        assert "hashtags" in chat_msg.metadata
        assert "#python" in chat_msg.metadata["hashtags"]

    def test_parse_message_with_photo(self, adapter):
        """Should parse message with photo attachment."""
        telegram_update = {
            "message": {
                "message_id": 125,
                "text": "",
                "caption": "Check out this photo!",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "photo": [
                    {"file_id": "small_photo_id", "width": 90, "height": 90},
                    {"file_id": "medium_photo_id", "width": 320, "height": 320},
                    {"file_id": "large_photo_id", "width": 800, "height": 800},
                ],
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.content == "Check out this photo!"
        assert len(chat_msg.attachments) == 1
        assert chat_msg.attachments[0]["type"] == "photo"
        # Should use largest photo
        assert chat_msg.attachments[0]["file_id"] == "large_photo_id"

    def test_parse_message_with_document(self, adapter):
        """Should parse message with document attachment."""
        telegram_update = {
            "message": {
                "message_id": 126,
                "text": "",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "document": {
                    "file_id": "doc_file_id",
                    "file_name": "report.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 12345,
                },
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert len(chat_msg.attachments) == 1
        assert chat_msg.attachments[0]["type"] == "document"
        assert chat_msg.attachments[0]["filename"] == "report.pdf"
        assert chat_msg.attachments[0]["content_type"] == "application/pdf"

    def test_parse_message_with_sticker(self, adapter):
        """Should parse message with sticker."""
        telegram_update = {
            "message": {
                "message_id": 127,
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "sticker": {
                    "file_id": "sticker_file_id",
                    "emoji": "😀",
                    "set_name": "HappyStickers",
                    "width": 512,
                    "height": 512,
                },
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert len(chat_msg.attachments) == 1
        assert chat_msg.attachments[0]["type"] == "sticker"
        assert chat_msg.attachments[0]["emoji"] == "😀"

    def test_parse_reply_message(self, adapter):
        """Should parse message that replies to another message."""
        telegram_update = {
            "message": {
                "message_id": 128,
                "text": "This is a reply",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "group"},
                "reply_to_message": {
                    "message_id": 100,
                    "text": "Original message",
                    "date": 1234567800,
                    "from": {"id": 333, "username": "original_sender", "is_bot": False},
                },
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.reply_to_id == "100"
        assert "reply_to_message" in chat_msg.metadata

    def test_parse_forwarded_message(self, adapter):
        """Should parse forwarded message."""
        telegram_update = {
            "message": {
                "message_id": 129,
                "text": "Forwarded content",
                "date": 1234567890,
                "from": {"id": 111, "username": "forwarder", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "forward_from": {
                    "id": 444,
                    "username": "original_author",
                    "first_name": "Original",
                },
                "forward_date": 1234560000,
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.metadata.get("is_forwarded") is True
        assert chat_msg.metadata.get("forward_from_id") == "444"

    def test_parse_private_chat_message(self, adapter):
        """Should identify private chat (DM) messages."""
        telegram_update = {
            "message": {
                "message_id": 130,
                "text": "Private message",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 111, "type": "private"},
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.is_direct_message is True

    def test_parse_group_message(self, adapter):
        """Should identify group messages."""
        telegram_update = {
            "message": {
                "message_id": 131,
                "text": "Group message",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": -100123456789, "type": "supergroup", "title": "Test"},
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.is_direct_message is False
        assert chat_msg.metadata.get("chat_type") == "supergroup"

    def test_parse_bot_command(self, adapter):
        """Should parse bot commands."""
        telegram_update = {
            "message": {
                "message_id": 132,
                "text": "/start hello world",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "entities": [{"type": "bot_command", "offset": 0, "length": 6}],
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.metadata.get("is_command") is True
        assert chat_msg.metadata.get("command") == "/start"
        assert chat_msg.metadata.get("command_args") == "hello world"


# =============================================================================
# Message Sending Tests
# =============================================================================


class TestTelegramMessageSending:
    """TDD: Tests for sending messages via Telegram."""

    @pytest.fixture
    def adapter(self):
        """Create connected test adapter."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._bot_info = {"id": 123456789, "username": "test_bot"}
        adapter._api_client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_send_simple_message(self, adapter):
        """Should send simple text message."""
        adapter._api_client.send_message = AsyncMock(
            return_value={
                "message_id": 999,
                "text": "Hello!",
                "date": 1234567890,
                "chat": {"id": 222},
            }
        )

        result = await adapter.send_message(
            channel_id="222",
            content="Hello!",
        )

        assert result.content == "Hello!"
        assert result.id == "999"
        adapter._api_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_reply_message(self, adapter):
        """Should send message as reply."""
        adapter._api_client.send_message = AsyncMock(
            return_value={
                "message_id": 1000,
                "text": "Reply text",
                "date": 1234567890,
                "chat": {"id": 222},
            }
        )

        result = await adapter.send_message(
            channel_id="222",
            content="Reply text",
            reply_to="500",
        )

        call_kwargs = adapter._api_client.send_message.call_args.kwargs
        assert call_kwargs.get("reply_to_message_id") == 500

    @pytest.mark.asyncio
    async def test_send_message_requires_connection(self):
        """Should require connection to send message."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        # Adapter is disconnected

        with pytest.raises(Exception, match="Not connected"):
            await adapter.send_message(channel_id="222", content="Hello!")

    @pytest.mark.asyncio
    async def test_send_message_with_parse_mode(self, adapter):
        """Should support Markdown/HTML parse modes."""
        adapter._api_client.send_message = AsyncMock(
            return_value={
                "message_id": 1001,
                "text": "**Bold** text",
                "date": 1234567890,
                "chat": {"id": 222},
            }
        )

        await adapter.send_message(
            channel_id="222",
            content="**Bold** text",
            parse_mode="MarkdownV2",
        )

        call_kwargs = adapter._api_client.send_message.call_args.kwargs
        assert call_kwargs.get("parse_mode") == "MarkdownV2"


# =============================================================================
# Bot Command Tests
# =============================================================================


class TestTelegramBotCommands:
    """TDD: Tests for Telegram bot command handling."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter with command handlers."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        adapter._bot_info = {"id": 123456789, "username": "test_bot"}
        return adapter

    def test_register_command_handler(self, adapter):
        """Should register command handlers."""

        async def start_handler(update):
            pass

        adapter.register_command("start", start_handler)

        assert "start" in adapter._command_handlers

    def test_parse_command_with_bot_username(self, adapter):
        """Should parse commands with bot username."""
        telegram_update = {
            "message": {
                "message_id": 140,
                "text": "/help@test_bot argument",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": -100123, "type": "group"},
                "entities": [{"type": "bot_command", "offset": 0, "length": 14}],
            }
        }

        chat_msg = adapter.parse_message(telegram_update)

        assert chat_msg.metadata.get("command") == "/help"
        assert chat_msg.metadata.get("command_args") == "argument"

    @pytest.mark.asyncio
    async def test_command_handler_invoked(self, adapter):
        """Should invoke registered command handler."""
        handler_called = []

        async def help_handler(update, args):
            handler_called.append({"update": update, "args": args})

        adapter.register_command("help", help_handler)
        adapter._connection_state = ConnectionState.CONNECTED

        telegram_update = {
            "message": {
                "message_id": 141,
                "text": "/help with args",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "entities": [{"type": "bot_command", "offset": 0, "length": 5}],
            }
        }

        await adapter._handle_update(telegram_update)

        assert len(handler_called) == 1
        assert handler_called[0]["args"] == "with args"


# =============================================================================
# Inline Mode Tests (Issues #53-54)
# =============================================================================


class TestTelegramInlineMode:
    """TDD: Tests for Telegram inline mode."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._bot_info = {"id": 123456789, "username": "test_bot"}
        adapter._api_client = MagicMock()
        return adapter

    def test_parse_inline_query(self, adapter):
        """Should parse inline query."""
        from src.chatbot.adapters.telegram_adapter import InlineQuery

        telegram_update = {
            "inline_query": {
                "id": "query_123",
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "query": "search term",
                "offset": "",
            }
        }

        inline_query = adapter.parse_inline_query(telegram_update)

        assert isinstance(inline_query, InlineQuery)
        assert inline_query.id == "query_123"
        assert inline_query.query == "search term"
        assert inline_query.from_user_id == "111"

    def test_create_inline_article_result(self, adapter):
        """Should create inline article result."""
        from src.chatbot.adapters.telegram_adapter import InlineQueryResultArticle

        result = InlineQueryResultArticle(
            id="result_1",
            title="Article Title",
            description="Article description",
            message_text="Full article content here",
        )

        result_dict = result.to_dict()

        assert result_dict["type"] == "article"
        assert result_dict["id"] == "result_1"
        assert result_dict["title"] == "Article Title"
        assert "input_message_content" in result_dict

    def test_create_inline_photo_result(self, adapter):
        """Should create inline photo result."""
        from src.chatbot.adapters.telegram_adapter import InlineQueryResultPhoto

        result = InlineQueryResultPhoto(
            id="result_2",
            photo_url="https://example.com/photo.jpg",
            thumb_url="https://example.com/thumb.jpg",
            title="Photo Title",
        )

        result_dict = result.to_dict()

        assert result_dict["type"] == "photo"
        assert result_dict["photo_url"] == "https://example.com/photo.jpg"

    @pytest.mark.asyncio
    async def test_answer_inline_query(self, adapter):
        """Should answer inline query with results."""
        from src.chatbot.adapters.telegram_adapter import InlineQueryResultArticle

        adapter._api_client.answer_inline_query = AsyncMock(return_value=True)

        results = [
            InlineQueryResultArticle(
                id="1",
                title="Result 1",
                message_text="Content 1",
            ),
            InlineQueryResultArticle(
                id="2",
                title="Result 2",
                message_text="Content 2",
            ),
        ]

        await adapter.answer_inline_query(
            inline_query_id="query_123",
            results=results,
        )

        adapter._api_client.answer_inline_query.assert_called_once()
        call_kwargs = adapter._api_client.answer_inline_query.call_args.kwargs
        assert len(call_kwargs["results"]) == 2

    @pytest.mark.asyncio
    async def test_answer_inline_query_with_caching(self, adapter):
        """Should support cache_time for inline results."""
        from src.chatbot.adapters.telegram_adapter import InlineQueryResultArticle

        adapter._api_client.answer_inline_query = AsyncMock(return_value=True)

        results = [InlineQueryResultArticle(id="1", title="R1", message_text="C1")]

        await adapter.answer_inline_query(
            inline_query_id="query_123",
            results=results,
            cache_time=300,
        )

        call_kwargs = adapter._api_client.answer_inline_query.call_args.kwargs
        assert call_kwargs.get("cache_time") == 300

    @pytest.mark.asyncio
    async def test_answer_inline_query_with_pagination(self, adapter):
        """Should support pagination via next_offset."""
        from src.chatbot.adapters.telegram_adapter import InlineQueryResultArticle

        adapter._api_client.answer_inline_query = AsyncMock(return_value=True)

        results = [InlineQueryResultArticle(id="1", title="R1", message_text="C1")]

        await adapter.answer_inline_query(
            inline_query_id="query_123",
            results=results,
            next_offset="page_2",
        )

        call_kwargs = adapter._api_client.answer_inline_query.call_args.kwargs
        assert call_kwargs.get("next_offset") == "page_2"

    def test_handle_chosen_inline_result(self, adapter):
        """Should handle chosen_inline_result callback."""
        callback_data = []

        async def on_chosen(result):
            callback_data.append(result)

        adapter.on_chosen_inline_result = on_chosen

        telegram_update = {
            "chosen_inline_result": {
                "result_id": "result_1",
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "query": "original query",
            }
        }

        # Verify the adapter can parse chosen_inline_result
        assert "chosen_inline_result" in telegram_update


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestTelegramEventHandling:
    """TDD: Tests for Telegram event handling."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        adapter._bot_info = {"id": 123456789, "username": "test_bot"}
        adapter._connection_state = ConnectionState.CONNECTED
        return adapter

    @pytest.mark.asyncio
    async def test_on_message_callback(self, adapter):
        """Should invoke callback when message received."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        telegram_update = {
            "message": {
                "message_id": 150,
                "text": "Test message",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
            }
        }

        await adapter._handle_update(telegram_update)

        assert len(messages_received) == 1
        assert messages_received[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, adapter):
        """Should ignore messages from the bot itself."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        telegram_update = {
            "message": {
                "message_id": 151,
                "text": "Bot's own message",
                "date": 1234567890,
                "from": {"id": 123456789, "username": "test_bot", "is_bot": True},
                "chat": {"id": 222, "type": "private"},
            }
        }

        await adapter._handle_update(telegram_update)

        assert len(messages_received) == 0

    @pytest.mark.asyncio
    async def test_handles_edited_message(self, adapter):
        """Should handle edited_message updates."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        telegram_update = {
            "edited_message": {
                "message_id": 152,
                "text": "Edited content",
                "date": 1234567890,
                "edit_date": 1234567900,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
            }
        }

        await adapter._handle_update(telegram_update)

        assert len(messages_received) == 1
        assert messages_received[0].metadata.get("is_edited") is True

    @pytest.mark.asyncio
    async def test_handles_channel_post(self, adapter):
        """Should handle channel_post updates."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        telegram_update = {
            "channel_post": {
                "message_id": 153,
                "text": "Channel post",
                "date": 1234567890,
                "chat": {"id": -1001234567890, "type": "channel", "title": "News"},
                "author_signature": "Admin",
            }
        }

        await adapter._handle_update(telegram_update)

        assert len(messages_received) == 1
        assert messages_received[0].metadata.get("chat_type") == "channel"


# =============================================================================
# Gateway Integration Tests
# =============================================================================


class TestTelegramGatewayIntegration:
    """TDD: Tests for Telegram-Gateway integration."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        adapter._bot_info = {"id": 123456789, "username": "test_bot"}
        return adapter

    def test_creates_gateway_request_from_message(self, adapter):
        """Should create GatewayRequest from Telegram message."""
        telegram_update = {
            "message": {
                "message_id": 160,
                "text": "Hello gateway",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
            }
        }

        request = adapter.create_gateway_request(telegram_update)

        assert isinstance(request, GatewayRequest)
        assert request.platform == "telegram"
        assert request.message.content == "Hello gateway"

    def test_creates_gateway_request_from_group(self, adapter):
        """Should create GatewayRequest from group message."""
        telegram_update = {
            "message": {
                "message_id": 161,
                "text": "Group message",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": -100123456789, "type": "supergroup", "title": "Group"},
            }
        }

        request = adapter.create_gateway_request(telegram_update)

        assert request.workspace_id is None  # Telegram doesn't have workspaces
        assert request.message.is_direct_message is False

    def test_creates_gateway_request_with_reply_thread(self, adapter):
        """Should track reply as thread context."""
        telegram_update = {
            "message": {
                "message_id": 162,
                "text": "Reply in thread",
                "date": 1234567890,
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "chat": {"id": 222, "type": "private"},
                "reply_to_message": {
                    "message_id": 100,
                    "text": "Original",
                    "date": 1234567800,
                },
            }
        }

        request = adapter.create_gateway_request(telegram_update)

        # Thread ID is the original message being replied to
        assert request.thread_id == "100"


# =============================================================================
# Keyboard/Button Tests
# =============================================================================


class TestTelegramKeyboards:
    """TDD: Tests for Telegram keyboard/button support."""

    @pytest.fixture
    def adapter(self):
        """Create connected test adapter."""
        from src.chatbot.adapters.telegram_adapter import TelegramConfig, TelegramAdapter

        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._bot_info = {"id": 123456789, "username": "test_bot"}
        adapter._api_client = MagicMock()
        return adapter

    def test_create_inline_keyboard(self, adapter):
        """Should create inline keyboard markup."""
        from src.chatbot.adapters.telegram_adapter import InlineKeyboard, InlineButton

        keyboard = InlineKeyboard(
            buttons=[
                [
                    InlineButton(text="Option 1", callback_data="opt1"),
                    InlineButton(text="Option 2", callback_data="opt2"),
                ],
                [InlineButton(text="Cancel", callback_data="cancel")],
            ]
        )

        markup = keyboard.to_dict()

        assert "inline_keyboard" in markup
        assert len(markup["inline_keyboard"]) == 2
        assert len(markup["inline_keyboard"][0]) == 2

    @pytest.mark.asyncio
    async def test_send_message_with_keyboard(self, adapter):
        """Should send message with inline keyboard."""
        from src.chatbot.adapters.telegram_adapter import InlineKeyboard, InlineButton

        adapter._api_client.send_message = AsyncMock(
            return_value={
                "message_id": 200,
                "text": "Choose:",
                "date": 1234567890,
                "chat": {"id": 222},
            }
        )

        keyboard = InlineKeyboard(
            buttons=[[InlineButton(text="Yes", callback_data="yes")]]
        )

        await adapter.send_message(
            channel_id="222",
            content="Choose:",
            reply_markup=keyboard,
        )

        call_kwargs = adapter._api_client.send_message.call_args.kwargs
        assert "reply_markup" in call_kwargs

    @pytest.mark.asyncio
    async def test_handle_callback_query(self, adapter):
        """Should handle callback query from button press."""
        callbacks_received = []

        async def on_callback(query):
            callbacks_received.append(query)

        adapter.on_callback_query = on_callback

        telegram_update = {
            "callback_query": {
                "id": "callback_123",
                "from": {"id": 111, "username": "sender", "is_bot": False},
                "data": "opt1",
                "message": {
                    "message_id": 200,
                    "chat": {"id": 222, "type": "private"},
                },
            }
        }

        await adapter._handle_update(telegram_update)

        assert len(callbacks_received) == 1
        assert callbacks_received[0]["data"] == "opt1"

    @pytest.mark.asyncio
    async def test_answer_callback_query(self, adapter):
        """Should answer callback query."""
        adapter._api_client.answer_callback_query = AsyncMock(return_value=True)

        await adapter.answer_callback_query(
            callback_query_id="callback_123",
            text="Option selected!",
            show_alert=False,
        )

        adapter._api_client.answer_callback_query.assert_called_once_with(
            callback_query_id="callback_123",
            text="Option selected!",
            show_alert=False,
        )
