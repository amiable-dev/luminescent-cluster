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
Base platform adapter protocol and data models.

This module defines the common interface for all chat platform adapters
(Discord, Slack, Telegram, WhatsApp). Each platform adapter implements
the BasePlatformAdapter protocol.

Design Principles (from ADR-006):
1. Thin adapters - route to existing MCP infrastructure
2. LLM agnostic - OpenAI-compatible API for provider flexibility
3. Platform normalization - consistent message format across platforms

Version: 1.0.0
"""

from typing import Protocol, Optional, Any, runtime_checkable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import re


class ConnectionState(Enum):
    """Connection state for platform adapters."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()


@dataclass
class MessageAuthor:
    """
    Normalized representation of a message author.

    Attributes:
        id: Platform-specific user identifier
        username: User's username/handle
        display_name: User's display name (optional)
        avatar_url: URL to user's avatar image (optional)
        is_bot: Whether the author is a bot (optional)
    """

    id: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_bot: Optional[bool] = None


@dataclass
class ChatMessage:
    """
    Normalized chat message representation.

    This dataclass provides a platform-agnostic representation of chat messages.
    Platform-specific adapters convert their native message formats to this
    common format.

    Attributes:
        id: Unique message identifier
        content: Message text content
        author: Message author information
        channel_id: Channel/conversation identifier
        timestamp: When the message was sent
        platform: Platform name (discord, slack, telegram, whatsapp)
        thread_id: Thread/conversation thread ID (optional)
        reply_to_id: ID of message being replied to (optional)
        is_direct_message: Whether this is a DM/private message
        attachments: List of attachment metadata (optional)
        metadata: Platform-specific metadata (optional)
    """

    id: str
    content: str
    author: MessageAuthor
    channel_id: str
    timestamp: datetime
    platform: str = ""
    thread_id: Optional[str] = None
    reply_to_id: Optional[str] = None
    is_direct_message: bool = False
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterConfig:
    """
    Configuration for platform adapters.

    Attributes:
        platform: Platform name (discord, slack, telegram, whatsapp)
        token: Bot/API token for authentication
        app_id: Application ID (platform-specific, optional)
        signing_secret: Webhook signing secret (optional)
        webhook_url: Webhook endpoint URL (optional)
        extra: Additional platform-specific configuration (optional)
    """

    platform: str
    token: str
    app_id: Optional[str] = None
    signing_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BasePlatformAdapter(Protocol):
    """
    Protocol defining the interface for chat platform adapters.

    All platform adapters (Discord, Slack, Telegram, WhatsApp) must
    implement this protocol to integrate with the ChatbotGateway.

    Lifecycle:
        1. Create adapter with AdapterConfig
        2. Call connect() to establish connection
        3. Process messages via callbacks or polling
        4. Call disconnect() when shutting down

    Example:
        config = AdapterConfig(platform="discord", token="bot-token")
        adapter = DiscordAdapter(config)

        await adapter.connect()
        # Process messages...
        await adapter.disconnect()

    Version: 1.0.0

    Related: ADR-006 Chatbot Platform Integrations
    """

    @property
    def platform(self) -> str:
        """
        Get the platform name.

        Returns:
            Platform identifier (e.g., "discord", "slack")
        """
        ...

    def get_connection_state(self) -> ConnectionState:
        """
        Get the current connection state.

        Returns:
            Current ConnectionState enum value.
        """
        ...

    async def connect(self) -> None:
        """
        Establish connection to the platform.

        This should authenticate with the platform API and set up
        any necessary event handlers or webhooks.

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
        """
        ...

    async def disconnect(self) -> None:
        """
        Disconnect from the platform.

        This should cleanly close connections and clean up resources.
        """
        ...

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
    ) -> ChatMessage:
        """
        Send a message to a channel.

        Args:
            channel_id: Target channel/conversation ID
            content: Message content to send
            reply_to: Optional message ID to reply to

        Returns:
            ChatMessage representing the sent message

        Raises:
            RuntimeError: If not connected
            PermissionError: If bot lacks permission to send
        """
        ...


# =============================================================================
# Message Normalization Utilities
# =============================================================================

# Pattern for Discord mentions: <@123456789> or <@!123456789>
DISCORD_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")

# Pattern for Slack mentions: <@U12345>
SLACK_MENTION_PATTERN = re.compile(r"<@([A-Z0-9]+)>")

# Pattern for Telegram mentions: @username
TELEGRAM_MENTION_PATTERN = re.compile(r"@(\w+)")


def normalize_mentions(content: str, platform: str) -> str:
    """
    Normalize platform-specific mentions to a standard format.

    Different platforms represent mentions differently:
    - Discord: <@123456789> or <@!123456789>
    - Slack: <@U12345>
    - Telegram: @username

    This function converts all mentions to a consistent format
    that can be processed uniformly.

    Args:
        content: Raw message content with platform-specific mentions
        platform: Platform name (discord, slack, telegram, whatsapp)

    Returns:
        Content with normalized mentions

    Example:
        >>> normalize_mentions("Hello <@123>!", "discord")
        "Hello @user_123!"
    """
    if platform == "discord":
        # Convert <@123> or <@!123> to @user_123
        return DISCORD_MENTION_PATTERN.sub(r"@user_\1", content)

    elif platform == "slack":
        # Convert <@U12345> to @user_U12345
        return SLACK_MENTION_PATTERN.sub(r"@user_\1", content)

    elif platform == "telegram":
        # Telegram already uses @username, keep as-is
        return content

    elif platform == "whatsapp":
        # WhatsApp doesn't have a standard mention format in API
        return content

    # Unknown platform, return unchanged
    return content


def extract_mentions(content: str, platform: str) -> list[str]:
    """
    Extract user IDs from mentions in message content.

    Args:
        content: Message content with mentions
        platform: Platform name

    Returns:
        List of user IDs mentioned in the message
    """
    if platform == "discord":
        return DISCORD_MENTION_PATTERN.findall(content)

    elif platform == "slack":
        return SLACK_MENTION_PATTERN.findall(content)

    elif platform == "telegram":
        return TELEGRAM_MENTION_PATTERN.findall(content)

    return []


def is_bot_mentioned(
    content: str,
    bot_id: str,
    platform: str,
) -> bool:
    """
    Check if the bot is mentioned in the message.

    Args:
        content: Message content
        bot_id: Bot's user ID on the platform
        platform: Platform name

    Returns:
        True if bot is mentioned
    """
    mentions = extract_mentions(content, platform)
    return bot_id in mentions
