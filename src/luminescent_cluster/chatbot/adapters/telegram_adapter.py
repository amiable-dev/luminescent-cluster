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
Telegram platform adapter for Luminescent Cluster chatbot.

This module implements the Telegram integration using the Bot API,
with support for both polling and webhook modes, inline queries,
and bot commands.

Design (from ADR-006):
- Thin adapter routing to ChatbotGateway
- Bot API for messaging with polling/webhook options
- Inline mode for query-based interactions
- Command registration and handling

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable, Awaitable, Any, Dict, Union
import asyncio
import logging
import re

from luminescent_cluster.chatbot.adapters.base import (
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)
from luminescent_cluster.chatbot.gateway import GatewayRequest

logger = logging.getLogger(__name__)


# =============================================================================
# Telegram Configuration
# =============================================================================


@dataclass
class TelegramConfig:
    """
    Configuration for Telegram adapter.

    Attributes:
        bot_token: Telegram bot token from @BotFather
        webhook_url: Optional webhook URL for receiving updates
        use_webhook: Whether to use webhook mode (default False = polling)
        allowed_updates: List of update types to receive
    """

    bot_token: str
    webhook_url: Optional[str] = None
    use_webhook: bool = False
    allowed_updates: List[str] = field(
        default_factory=lambda: [
            "message",
            "edited_message",
            "channel_post",
            "inline_query",
            "callback_query",
            "chosen_inline_result",
        ]
    )


# =============================================================================
# Inline Query Models
# =============================================================================


@dataclass
class InlineQuery:
    """
    Telegram inline query.

    Attributes:
        id: Unique query identifier
        from_user_id: User who sent the query
        query: Query text
        offset: Pagination offset
    """

    id: str
    from_user_id: str
    query: str
    offset: str = ""
    chat_type: Optional[str] = None


@dataclass
class InlineQueryResultArticle:
    """
    Inline query result - Article type.

    Attributes:
        id: Unique result identifier
        title: Title of the result
        message_text: Text to send when selected
        description: Optional description
        thumb_url: Optional thumbnail URL
    """

    id: str
    title: str
    message_text: str
    description: Optional[str] = None
    thumb_url: Optional[str] = None
    parse_mode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Telegram API format."""
        result = {
            "type": "article",
            "id": self.id,
            "title": self.title,
            "input_message_content": {
                "message_text": self.message_text,
            },
        }

        if self.description:
            result["description"] = self.description
        if self.thumb_url:
            result["thumb_url"] = self.thumb_url
        if self.parse_mode:
            result["input_message_content"]["parse_mode"] = self.parse_mode

        return result


@dataclass
class InlineQueryResultPhoto:
    """
    Inline query result - Photo type.

    Attributes:
        id: Unique result identifier
        photo_url: URL of the photo
        thumb_url: URL of the thumbnail
        title: Optional title
        caption: Optional caption
    """

    id: str
    photo_url: str
    thumb_url: str
    title: Optional[str] = None
    caption: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Telegram API format."""
        result = {
            "type": "photo",
            "id": self.id,
            "photo_url": self.photo_url,
            "thumb_url": self.thumb_url,
        }

        if self.title:
            result["title"] = self.title
        if self.caption:
            result["caption"] = self.caption

        return result


# =============================================================================
# Keyboard Models
# =============================================================================


@dataclass
class InlineButton:
    """
    Inline keyboard button.

    Attributes:
        text: Button text
        callback_data: Data to send on press
        url: Optional URL to open
    """

    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Telegram API format."""
        result = {"text": self.text}

        if self.callback_data:
            result["callback_data"] = self.callback_data
        if self.url:
            result["url"] = self.url

        return result


@dataclass
class InlineKeyboard:
    """
    Inline keyboard markup.

    Attributes:
        buttons: 2D list of buttons (rows x columns)
    """

    buttons: List[List[InlineButton]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Telegram API format."""
        return {"inline_keyboard": [[btn.to_dict() for btn in row] for row in self.buttons]}


# =============================================================================
# Telegram Adapter Implementation
# =============================================================================


class TelegramAdapter:
    """
    Telegram platform adapter implementing BasePlatformAdapter protocol.

    Provides integration with Telegram for:
    - Polling or webhook-based updates
    - Message parsing with entities
    - Inline mode queries
    - Bot commands
    - Inline keyboards

    Example:
        config = TelegramConfig(bot_token="123456:ABC-DEF")
        adapter = TelegramAdapter(config)

        @adapter.on_message
        async def handle_message(msg: ChatMessage):
            print(f"Received: {msg.content}")

        await adapter.connect()
    """

    def __init__(self, config: TelegramConfig):
        """
        Initialize Telegram adapter.

        Args:
            config: Telegram configuration
        """
        self.config = config
        self._connection_state = ConnectionState.DISCONNECTED
        self._api_client = None
        self._polling_task: Optional[asyncio.Task] = None
        self._bot_info: Dict[str, Any] = {}

        # Command handlers
        self._command_handlers: Dict[str, Callable] = {}

        # Event callbacks
        self.on_message: Optional[Callable[[ChatMessage], Awaitable[None]]] = None
        self.on_callback_query: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        self.on_inline_query: Optional[Callable[[InlineQuery], Awaitable[None]]] = None
        self.on_chosen_inline_result: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None

    @property
    def platform(self) -> str:
        """Return platform identifier."""
        return "telegram"

    @property
    def bot_user_id(self) -> Optional[str]:
        """Return bot's user ID."""
        bot_id = self._bot_info.get("id")
        return str(bot_id) if bot_id else None

    @property
    def bot_username(self) -> Optional[str]:
        """Return bot's username."""
        return self._bot_info.get("username")

    def get_connection_state(self) -> ConnectionState:
        """Return current connection state."""
        return self._connection_state

    async def connect(self) -> None:
        """
        Connect to Telegram Bot API.

        Raises:
            Exception: If connection fails
        """
        self._connection_state = ConnectionState.CONNECTING

        try:
            if self.config.use_webhook:
                await self._connect_webhook()
            else:
                await self._connect_polling()

            self._connection_state = ConnectionState.CONNECTED
            logger.info("Connected to Telegram")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            logger.error(f"Failed to connect to Telegram: {e}")
            raise

    async def _connect_polling(self) -> None:
        """Connect using long polling."""
        try:
            from telegram import Bot
            from telegram.ext import Application

            application = Application.builder().token(self.config.bot_token).build()
            self._api_client = _TelegramAPIClient(application.bot)

            # Get bot info
            bot_info = await application.bot.get_me()
            self._bot_info = {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
            }

            # Start polling in background
            self._polling_task = asyncio.create_task(self._poll_updates(application))

        except ImportError:
            logger.warning("python-telegram-bot not installed, using mock client")
            self._api_client = _MockTelegramClient()
            self._bot_info = {"id": 123456789, "username": "test_bot", "first_name": "Test Bot"}

    async def _connect_webhook(self) -> None:
        """Connect using webhook mode."""
        try:
            from telegram import Bot

            bot = Bot(token=self.config.bot_token)
            self._api_client = _TelegramAPIClient(bot)

            # Get bot info
            bot_info = await bot.get_me()
            self._bot_info = {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
            }

            # Set webhook
            await bot.set_webhook(
                url=self.config.webhook_url,
                allowed_updates=self.config.allowed_updates,
            )

        except ImportError:
            logger.warning("python-telegram-bot not installed, using mock client")
            self._api_client = _MockTelegramClient()
            self._bot_info = {"id": 123456789, "username": "test_bot", "first_name": "Test Bot"}

    async def _poll_updates(self, application) -> None:
        """Poll for updates (background task)."""
        offset = 0

        while self._connection_state == ConnectionState.CONNECTED:
            try:
                updates = await application.bot.get_updates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=self.config.allowed_updates,
                )

                for update in updates:
                    offset = update.update_id + 1
                    await self._handle_update(update.to_dict())

            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        if self.config.use_webhook and self._api_client:
            try:
                await self._api_client.delete_webhook()
            except Exception as e:
                logger.warning(f"Error deleting webhook: {e}")

        self._connection_state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from Telegram")

    def register_command(self, command: str, handler: Callable) -> None:
        """
        Register a bot command handler.

        Args:
            command: Command name (without /)
            handler: Async handler function
        """
        self._command_handlers[command] = handler

    def parse_message(self, telegram_update: Dict[str, Any]) -> ChatMessage:
        """
        Parse Telegram update to ChatMessage.

        Args:
            telegram_update: Telegram update payload

        Returns:
            Normalized ChatMessage
        """
        # Get message from various update types
        message_data = (
            telegram_update.get("message")
            or telegram_update.get("edited_message")
            or telegram_update.get("channel_post")
            or telegram_update.get("edited_channel_post")
            or {}
        )

        # Extract basic fields
        message_id = str(message_data.get("message_id", ""))
        text = message_data.get("text", "") or message_data.get("caption", "")
        timestamp = message_data.get("date", 0)

        # Get author info
        from_user = message_data.get("from", {})
        is_channel = "channel_post" in telegram_update or "edited_channel_post" in telegram_update

        if is_channel:
            author = MessageAuthor(
                id="channel",
                username=message_data.get("author_signature", "channel"),
                is_bot=False,
            )
        else:
            author = MessageAuthor(
                id=str(from_user.get("id", "")),
                username=from_user.get("username", ""),
                display_name=f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
                is_bot=from_user.get("is_bot", False),
            )

        # Get chat info
        chat = message_data.get("chat", {})
        chat_id = str(chat.get("id", ""))
        chat_type = chat.get("type", "private")

        # Check for reply
        reply_to = message_data.get("reply_to_message")
        reply_to_id = str(reply_to.get("message_id")) if reply_to else None

        # Build metadata
        metadata: Dict[str, Any] = {
            "chat_type": chat_type,
        }

        # Parse entities
        entities = message_data.get("entities", [])
        mentions = []
        urls = []
        hashtags = []
        is_command = False
        command = None
        command_args = None

        for entity in entities:
            entity_type = entity.get("type")
            offset = entity.get("offset", 0)
            length = entity.get("length", 0)
            entity_text = text[offset : offset + length]

            if entity_type == "mention":
                mentions.append(entity_text)
            elif entity_type == "url":
                urls.append(entity_text)
            elif entity_type == "hashtag":
                hashtags.append(entity_text)
            elif entity_type == "bot_command" and offset == 0:
                is_command = True
                # Remove @bot_username if present
                cmd_text = entity_text.split("@")[0]
                command = cmd_text
                command_args = text[length:].strip()

        if mentions:
            metadata["mentions"] = mentions
        if urls:
            metadata["urls"] = urls
        if hashtags:
            metadata["hashtags"] = hashtags
        if is_command:
            metadata["is_command"] = True
            metadata["command"] = command
            metadata["command_args"] = command_args

        # Check for edited message
        if telegram_update.get("edited_message") or telegram_update.get("edited_channel_post"):
            metadata["is_edited"] = True

        # Check for forwarded message
        if message_data.get("forward_from") or message_data.get("forward_from_chat"):
            metadata["is_forwarded"] = True
            forward_from = message_data.get("forward_from", {})
            if forward_from:
                metadata["forward_from_id"] = str(forward_from.get("id"))

        # Store reply_to_message in metadata
        if reply_to:
            metadata["reply_to_message"] = reply_to

        # Parse attachments
        attachments = []

        # Photo (use largest)
        if "photo" in message_data:
            photos = message_data["photo"]
            largest = max(photos, key=lambda p: p.get("width", 0) * p.get("height", 0))
            attachments.append(
                {
                    "type": "photo",
                    "file_id": largest.get("file_id"),
                    "width": largest.get("width"),
                    "height": largest.get("height"),
                }
            )

        # Document
        if "document" in message_data:
            doc = message_data["document"]
            attachments.append(
                {
                    "type": "document",
                    "file_id": doc.get("file_id"),
                    "filename": doc.get("file_name"),
                    "content_type": doc.get("mime_type"),
                    "size": doc.get("file_size"),
                }
            )

        # Sticker
        if "sticker" in message_data:
            sticker = message_data["sticker"]
            attachments.append(
                {
                    "type": "sticker",
                    "file_id": sticker.get("file_id"),
                    "emoji": sticker.get("emoji"),
                    "set_name": sticker.get("set_name"),
                }
            )

        # Convert timestamp
        try:
            dt = datetime.fromtimestamp(timestamp)
        except (ValueError, TypeError):
            dt = datetime.now()

        return ChatMessage(
            id=message_id,
            content=text,
            author=author,
            channel_id=chat_id,
            timestamp=dt,
            platform="telegram",
            thread_id=None,  # Telegram doesn't have threads like Discord/Slack
            reply_to_id=reply_to_id,
            is_direct_message=(chat_type == "private"),
            attachments=attachments,
            metadata=metadata,
        )

    def parse_inline_query(self, telegram_update: Dict[str, Any]) -> InlineQuery:
        """
        Parse inline query from update.

        Args:
            telegram_update: Telegram update payload

        Returns:
            InlineQuery object
        """
        query_data = telegram_update.get("inline_query", {})

        return InlineQuery(
            id=query_data.get("id", ""),
            from_user_id=str(query_data.get("from", {}).get("id", "")),
            query=query_data.get("query", ""),
            offset=query_data.get("offset", ""),
            chat_type=query_data.get("chat_type"),
        )

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboard] = None,
    ) -> ChatMessage:
        """
        Send a message to a Telegram chat.

        Args:
            channel_id: Chat ID to send to
            content: Message text
            reply_to: Optional message ID to reply to
            parse_mode: Optional parse mode (Markdown, MarkdownV2, HTML)
            reply_markup: Optional inline keyboard

        Returns:
            The sent ChatMessage

        Raises:
            Exception: If not connected or send fails
        """
        if self._connection_state != ConnectionState.CONNECTED:
            raise Exception("Not connected to Telegram")

        kwargs: Dict[str, Any] = {
            "chat_id": int(channel_id),
            "text": content,
        }

        if reply_to:
            kwargs["reply_to_message_id"] = int(reply_to)

        if parse_mode:
            kwargs["parse_mode"] = parse_mode

        if reply_markup:
            kwargs["reply_markup"] = reply_markup.to_dict()

        response = await self._api_client.send_message(**kwargs)

        return ChatMessage(
            id=str(response.get("message_id", "")),
            content=content,
            author=MessageAuthor(
                id=self.bot_user_id or "",
                username=self.bot_username or "bot",
            ),
            channel_id=channel_id,
            timestamp=datetime.now(),
            platform="telegram",
        )

    async def answer_inline_query(
        self,
        inline_query_id: str,
        results: List[Union[InlineQueryResultArticle, InlineQueryResultPhoto]],
        cache_time: int = 300,
        next_offset: Optional[str] = None,
    ) -> None:
        """
        Answer an inline query.

        Args:
            inline_query_id: Query ID to answer
            results: List of inline query results
            cache_time: Cache time in seconds
            next_offset: Offset for next page of results
        """
        kwargs: Dict[str, Any] = {
            "inline_query_id": inline_query_id,
            "results": [r.to_dict() for r in results],
            "cache_time": cache_time,
        }

        if next_offset:
            kwargs["next_offset"] = next_offset

        await self._api_client.answer_inline_query(**kwargs)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> None:
        """
        Answer a callback query from inline button.

        Args:
            callback_query_id: Callback query ID
            text: Optional notification text
            show_alert: Whether to show as alert
        """
        await self._api_client.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )

    async def _handle_update(self, update: Dict[str, Any]) -> None:
        """
        Handle incoming Telegram update.

        Args:
            update: Telegram update payload
        """
        # Handle message updates
        if "message" in update or "edited_message" in update or "channel_post" in update:
            message_data = (
                update.get("message") or update.get("edited_message") or update.get("channel_post")
            )

            # Ignore own messages
            from_user = message_data.get("from", {})
            if str(from_user.get("id")) == self.bot_user_id:
                return

            chat_msg = self.parse_message(update)

            # Check for command
            if chat_msg.metadata.get("is_command"):
                command = chat_msg.metadata.get("command", "").lstrip("/")
                if command in self._command_handlers:
                    await self._command_handlers[command](
                        update, chat_msg.metadata.get("command_args", "")
                    )
                    return

            # Invoke message callback
            if self.on_message:
                await self.on_message(chat_msg)

        # Handle callback queries
        elif "callback_query" in update:
            callback_data = update["callback_query"]
            if self.on_callback_query:
                await self.on_callback_query(callback_data)

        # Handle inline queries
        elif "inline_query" in update:
            inline_query = self.parse_inline_query(update)
            if self.on_inline_query:
                await self.on_inline_query(inline_query)

        # Handle chosen inline result
        elif "chosen_inline_result" in update:
            if self.on_chosen_inline_result:
                await self.on_chosen_inline_result(update["chosen_inline_result"])

    def create_gateway_request(self, telegram_update: Dict[str, Any]) -> GatewayRequest:
        """
        Create GatewayRequest from Telegram update.

        Args:
            telegram_update: Telegram update payload

        Returns:
            GatewayRequest for ChatbotGateway
        """
        chat_msg = self.parse_message(telegram_update)

        # Use reply_to_id as thread context
        thread_id = chat_msg.reply_to_id

        return GatewayRequest(
            message=chat_msg,
            platform="telegram",
            thread_id=thread_id,
            workspace_id=None,  # Telegram doesn't have workspaces
        )


# =============================================================================
# API Client Wrapper
# =============================================================================


class _TelegramAPIClient:
    """Wrapper around python-telegram-bot Bot for async operations."""

    def __init__(self, bot):
        self._bot = bot

    async def send_message(self, **kwargs) -> Dict[str, Any]:
        message = await self._bot.send_message(**kwargs)
        return {
            "message_id": message.message_id,
            "text": message.text,
            "date": message.date.timestamp() if message.date else 0,
            "chat": {"id": message.chat.id},
        }

    async def answer_inline_query(self, **kwargs) -> bool:
        return await self._bot.answer_inline_query(**kwargs)

    async def answer_callback_query(self, **kwargs) -> bool:
        return await self._bot.answer_callback_query(**kwargs)

    async def delete_webhook(self) -> bool:
        return await self._bot.delete_webhook()


# =============================================================================
# Mock Client for Testing
# =============================================================================


class _MockTelegramClient:
    """Mock Telegram client for testing without python-telegram-bot."""

    async def send_message(self, **kwargs) -> Dict[str, Any]:
        return {
            "message_id": 999,
            "text": kwargs.get("text", ""),
            "date": int(datetime.now().timestamp()),
            "chat": {"id": kwargs.get("chat_id")},
        }

    async def answer_inline_query(self, **kwargs) -> bool:
        return True

    async def answer_callback_query(self, **kwargs) -> bool:
        return True

    async def delete_webhook(self) -> bool:
        return True
