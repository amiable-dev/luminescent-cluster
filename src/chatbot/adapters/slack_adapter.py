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
Slack platform adapter for Luminescent Cluster chatbot.

This module implements the Slack integration using Socket Mode for
real-time messaging, with support for threads, App Home, and slash commands.

Design (from ADR-006):
- Thin adapter routing to ChatbotGateway
- Socket Mode for WebSocket-based communication
- Thread context tracking via thread_ts
- App Home tab for user dashboard

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable, Awaitable, Any, Dict
import asyncio
import logging
import re

from src.chatbot.adapters.base import (
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)
from src.chatbot.gateway import GatewayRequest

logger = logging.getLogger(__name__)


# =============================================================================
# Slack Configuration
# =============================================================================


@dataclass
class SlackConfig:
    """
    Configuration for Slack adapter.

    Attributes:
        bot_token: Slack bot token (xoxb-...)
        app_token: Slack app-level token for Socket Mode (xapp-...)
        signing_secret: Slack signing secret for request verification
        socket_mode: Whether to use Socket Mode (default True)
        default_channel: Optional default channel for messages
    """

    bot_token: str
    app_token: str
    signing_secret: str
    socket_mode: bool = True
    default_channel: Optional[str] = None


# =============================================================================
# Slack Block Kit Models
# =============================================================================


@dataclass
class SlackBlock:
    """
    Slack Block Kit block.

    Attributes:
        type: Block type (section, header, divider, actions, etc.)
        data: Block data
    """

    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Slack API format."""
        result = {"type": self.type}
        result.update(self.data)
        return result


@dataclass
class SlackAppHomeView:
    """
    Slack App Home view definition.

    Attributes:
        blocks: List of Block Kit blocks
        private_metadata: Optional private metadata string
        external_id: Optional external ID
    """

    blocks: List[Dict[str, Any]] = field(default_factory=list)
    private_metadata: Optional[str] = None
    external_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Slack API format."""
        result = {
            "type": "home",
            "blocks": self.blocks,
        }

        if self.private_metadata:
            result["private_metadata"] = self.private_metadata
        if self.external_id:
            result["external_id"] = self.external_id

        return result


# Legacy alias for compatibility
SlackMessage = ChatMessage


# =============================================================================
# Slack Adapter Implementation
# =============================================================================


class SlackAdapter:
    """
    Slack platform adapter implementing BasePlatformAdapter protocol.

    Provides integration with Slack for:
    - Socket Mode real-time messaging
    - Thread context tracking
    - App Home tab
    - Slash commands
    - Ephemeral messages

    Example:
        config = SlackConfig(
            bot_token="xoxb-your-token",
            app_token="xapp-your-token",
            signing_secret="your-secret",
        )
        adapter = SlackAdapter(config)

        @adapter.on_message
        async def handle_message(msg: ChatMessage):
            print(f"Received: {msg.content}")

        await adapter.connect()
    """

    def __init__(self, config: SlackConfig):
        """
        Initialize Slack adapter.

        Args:
            config: Slack configuration
        """
        self.config = config
        self._connection_state = ConnectionState.DISCONNECTED
        self._socket_mode_handler = None
        self._web_client = None
        self._bot_user_id: Optional[str] = None

        # User info cache
        self._user_cache: Dict[str, Dict[str, Any]] = {}

        # Event callbacks
        self.on_message: Optional[Callable[[ChatMessage], Awaitable[None]]] = None
        self.on_app_home_opened: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_slash_command: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None

    @property
    def platform(self) -> str:
        """Return platform identifier."""
        return "slack"

    @property
    def bot_user_id(self) -> Optional[str]:
        """Return bot's user ID."""
        return self._bot_user_id

    def get_connection_state(self) -> ConnectionState:
        """Return current connection state."""
        return self._connection_state

    async def connect(self) -> None:
        """
        Connect to Slack using Socket Mode.

        Raises:
            Exception: If connection fails
        """
        self._connection_state = ConnectionState.CONNECTING

        try:
            if self.config.socket_mode:
                await self._connect_socket_mode()
            else:
                await self._connect_web_api()

            self._connection_state = ConnectionState.CONNECTED
            logger.info("Connected to Slack")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            logger.error(f"Failed to connect to Slack: {e}")
            raise

    async def _connect_socket_mode(self) -> None:
        """Connect using Socket Mode."""
        try:
            from slack_bolt.async_app import AsyncApp
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

            app = AsyncApp(token=self.config.bot_token)
            self._socket_mode_handler = AsyncSocketModeHandler(app, self.config.app_token)
            self._web_client = app.client

            # Get bot user ID
            auth_result = await self._web_client.auth_test()
            self._bot_user_id = auth_result["user_id"]

            # Start socket mode
            await self._socket_mode_handler.connect_async()
            await self._socket_mode_handler.start_async()

        except ImportError:
            logger.warning("slack_bolt not installed, using mock client")
            self._web_client = _MockSlackClient()
            self._socket_mode_handler = _MockSocketModeHandler()
            self._bot_user_id = "U123456789"
            await self._socket_mode_handler.connect_async()
            await self._socket_mode_handler.start_async()

    async def _connect_web_api(self) -> None:
        """Connect using Web API only (no real-time events)."""
        try:
            from slack_sdk.web.async_client import AsyncWebClient

            self._web_client = AsyncWebClient(token=self.config.bot_token)

            # Get bot user ID
            auth_result = await self._web_client.auth_test()
            self._bot_user_id = auth_result["user_id"]

        except ImportError:
            logger.warning("slack_sdk not installed, using mock client")
            self._web_client = _MockSlackClient()
            self._bot_user_id = "U123456789"

    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        if self._socket_mode_handler:
            try:
                await self._socket_mode_handler.close_async()
            except Exception as e:
                logger.warning(f"Error closing socket mode handler: {e}")

        self._connection_state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from Slack")

    def parse_message(self, slack_event: Dict[str, Any]) -> ChatMessage:
        """
        Parse Slack event to ChatMessage.

        Args:
            slack_event: Slack event payload

        Returns:
            Normalized ChatMessage
        """
        # Handle message_changed subtype
        if slack_event.get("subtype") == "message_changed":
            message_data = slack_event.get("message", {})
            text = message_data.get("text", "")
            user_id = message_data.get("user", "")
            ts = message_data.get("ts", slack_event.get("ts", ""))
        else:
            text = slack_event.get("text", "")
            user_id = slack_event.get("user", slack_event.get("bot_id", ""))
            ts = slack_event.get("ts", "")

        channel_id = slack_event.get("channel", "")

        # Get author info
        is_bot = slack_event.get("subtype") == "bot_message" or "bot_id" in slack_event
        user_info = self._user_cache.get(user_id, {})

        author = MessageAuthor(
            id=user_id,
            username=user_info.get("name", user_id),
            display_name=user_info.get("real_name"),
            is_bot=is_bot,
        )

        # Extract attachments
        attachments = []
        for file_info in slack_event.get("files", []):
            attachments.append({
                "id": file_info.get("id"),
                "filename": file_info.get("name"),
                "url": file_info.get("url_private"),
                "content_type": file_info.get("mimetype"),
                "size": file_info.get("size"),
            })

        # Determine if DM
        channel_type = slack_event.get("channel_type", "")
        is_dm = channel_id.startswith("D") or channel_type == "im"

        # Extract thread_ts
        thread_ts = slack_event.get("thread_ts")
        if thread_ts == ts:
            thread_ts = None  # Parent message

        # Build metadata
        metadata = {}

        # Extract user mentions
        mentions = re.findall(r"<@(U[A-Z0-9]+)>", text)
        if mentions:
            metadata["mentions"] = mentions

        # Extract channel mentions
        channel_mentions = re.findall(r"<#(C[A-Z0-9]+)(?:\|[^>]+)?>", text)
        if channel_mentions:
            metadata["channel_mentions"] = channel_mentions

        # Handle blocks
        if "blocks" in slack_event:
            metadata["blocks"] = slack_event["blocks"]

        # Handle broadcast replies
        if slack_event.get("subtype") == "thread_broadcast":
            metadata["is_broadcast"] = True

        # Convert ts to datetime
        try:
            timestamp = datetime.fromtimestamp(float(ts.split(".")[0]))
        except (ValueError, IndexError):
            timestamp = datetime.now()

        return ChatMessage(
            id=ts,
            content=text,
            author=author,
            channel_id=channel_id,
            timestamp=timestamp,
            platform="slack",
            thread_id=thread_ts,
            is_direct_message=is_dm,
            attachments=attachments,
            metadata=metadata,
        )

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatMessage:
        """
        Send a message to a Slack channel.

        Args:
            channel_id: Channel ID to send to
            content: Message text (used as fallback for blocks)
            reply_to: Optional thread_ts to reply to
            blocks: Optional Block Kit blocks

        Returns:
            The sent ChatMessage

        Raises:
            Exception: If not connected or send fails
        """
        if self._connection_state != ConnectionState.CONNECTED:
            raise Exception("Not connected to Slack")

        kwargs = {
            "channel": channel_id,
            "text": content,
        }

        if reply_to:
            kwargs["thread_ts"] = reply_to

        if blocks:
            kwargs["blocks"] = blocks

        response = await self._web_client.chat_postMessage(**kwargs)

        return ChatMessage(
            id=response.get("ts", ""),
            content=content,
            author=MessageAuthor(
                id=self._bot_user_id or "",
                username="bot",
            ),
            channel_id=channel_id,
            timestamp=datetime.now(),
            platform="slack",
        )

    async def send_ephemeral(
        self,
        channel_id: str,
        user_id: str,
        content: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Send ephemeral message visible only to one user.

        Args:
            channel_id: Channel ID
            user_id: User ID to show message to
            content: Message text
            blocks: Optional Block Kit blocks
        """
        if self._connection_state != ConnectionState.CONNECTED:
            raise Exception("Not connected to Slack")

        kwargs = {
            "channel": channel_id,
            "user": user_id,
            "text": content,
        }

        if blocks:
            kwargs["blocks"] = blocks

        await self._web_client.chat_postEphemeral(**kwargs)

    # =========================================================================
    # App Home Support
    # =========================================================================

    async def publish_app_home(self, user_id: str, view: SlackAppHomeView) -> None:
        """
        Publish App Home view for a user.

        Args:
            user_id: User ID to publish for
            view: App Home view definition
        """
        if self._connection_state != ConnectionState.CONNECTED:
            raise Exception("Not connected to Slack")

        await self._web_client.views_publish(
            user_id=user_id,
            view=view.to_dict(),
        )

    async def _handle_app_home_opened(self, event: Dict[str, Any]) -> None:
        """
        Handle app_home_opened event.

        Args:
            event: Slack event payload
        """
        user_id = event.get("user", "")

        if self.on_app_home_opened:
            await self.on_app_home_opened(user_id)

    # =========================================================================
    # Slash Commands
    # =========================================================================

    def parse_slash_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse slash command payload.

        Args:
            payload: Slack slash command payload

        Returns:
            Parsed command data
        """
        return {
            "command": payload.get("command", ""),
            "text": payload.get("text", ""),
            "user_id": payload.get("user_id", ""),
            "user_name": payload.get("user_name", ""),
            "channel_id": payload.get("channel_id", ""),
            "response_url": payload.get("response_url", ""),
            "trigger_id": payload.get("trigger_id", ""),
        }

    async def respond_to_command(
        self,
        response_url: str,
        text: str,
        response_type: str = "in_channel",
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Respond to a slash command using response_url.

        Args:
            response_url: Response URL from command payload
            text: Response text
            response_type: "in_channel" or "ephemeral"
            blocks: Optional Block Kit blocks
        """
        import aiohttp

        payload = {
            "text": text,
            "response_type": response_type,
        }

        if blocks:
            payload["blocks"] = blocks

        async with aiohttp.ClientSession() as session:
            async with session.post(response_url, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Failed to respond to command: {response.status}")

    # =========================================================================
    # Event Handling
    # =========================================================================

    async def _handle_message_event(self, event: Dict[str, Any]) -> None:
        """
        Handle incoming message event.

        Args:
            event: Slack event payload
        """
        # Ignore own messages
        user_id = event.get("user", event.get("message", {}).get("user", ""))
        if user_id == self._bot_user_id:
            return

        # Parse to ChatMessage
        chat_msg = self.parse_message(event)

        # Invoke callback
        if self.on_message:
            await self.on_message(chat_msg)

    # =========================================================================
    # Gateway Integration
    # =========================================================================

    def create_gateway_request(self, slack_event: Dict[str, Any]) -> GatewayRequest:
        """
        Create GatewayRequest from Slack event.

        Args:
            slack_event: Slack event payload

        Returns:
            GatewayRequest for ChatbotGateway
        """
        chat_msg = self.parse_message(slack_event)

        workspace_id = slack_event.get("team")

        return GatewayRequest(
            message=chat_msg,
            platform="slack",
            thread_id=chat_msg.thread_id,
            workspace_id=workspace_id,
        )


# =============================================================================
# Mock Clients for Testing
# =============================================================================


class _MockSlackClient:
    """Mock Slack client for testing without slack_sdk."""

    async def auth_test(self) -> Dict[str, Any]:
        return {"ok": True, "user_id": "U123456789"}

    async def chat_postMessage(self, **kwargs) -> Dict[str, Any]:
        return {"ok": True, "ts": "1234567890.123456", "channel": kwargs.get("channel")}

    async def chat_postEphemeral(self, **kwargs) -> Dict[str, Any]:
        return {"ok": True, "message_ts": "1234567890.123456"}

    async def views_publish(self, **kwargs) -> Dict[str, Any]:
        return {"ok": True}


class _MockSocketModeHandler:
    """Mock Socket Mode handler for testing."""

    async def connect_async(self) -> None:
        pass

    async def start_async(self) -> None:
        pass

    async def close_async(self) -> None:
        pass
