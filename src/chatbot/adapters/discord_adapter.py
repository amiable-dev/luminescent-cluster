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
Discord platform adapter for Luminescent Cluster chatbot.

This module implements the Discord integration using discord.py library,
providing message handling, slash commands, and thread context support.

Design (from ADR-006):
- Thin adapter routing to ChatbotGateway
- Full Discord API feature support
- Thread and reply context tracking
- Slash command registration and handling

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable, Awaitable, Any, Dict
import asyncio
import logging

from src.chatbot.adapters.base import (
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)
from src.chatbot.gateway import GatewayRequest

logger = logging.getLogger(__name__)


# =============================================================================
# Discord Configuration
# =============================================================================


@dataclass
class DiscordConfig:
    """
    Configuration for Discord adapter.

    Attributes:
        token: Discord bot token
        application_id: Discord application ID
        guild_id: Optional guild ID for guild-specific commands
        intents: List of Discord intents to enable
        command_prefix: Optional prefix for legacy commands
    """

    token: str
    application_id: str
    guild_id: Optional[str] = None
    intents: List[str] = field(
        default_factory=lambda: [
            "guilds",
            "guild_messages",
            "direct_messages",
            "message_content",
        ]
    )
    command_prefix: Optional[str] = None


# =============================================================================
# Discord Slash Command Models
# =============================================================================


@dataclass
class DiscordCommandOption:
    """
    Option for a Discord slash command.

    Attributes:
        name: Option name
        description: Option description
        type: Option type (string, integer, boolean, user, channel, number)
        required: Whether option is required
        choices: Optional list of choices
    """

    name: str
    description: str
    type: str = "string"
    required: bool = False
    choices: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format."""
        type_map = {
            "string": 3,
            "integer": 4,
            "boolean": 5,
            "user": 6,
            "channel": 7,
            "role": 8,
            "number": 10,
        }

        result = {
            "name": self.name,
            "description": self.description,
            "type": type_map.get(self.type, 3),
            "required": self.required,
        }

        if self.choices:
            result["choices"] = self.choices

        return result


@dataclass
class DiscordSlashCommand:
    """
    Discord slash command definition.

    Attributes:
        name: Command name (lowercase, no spaces)
        description: Command description
        options: List of command options
        guild_id: Optional guild-specific registration
    """

    name: str
    description: str
    options: List[DiscordCommandOption] = field(default_factory=list)
    guild_id: Optional[str] = None

    def to_registration_dict(self) -> Dict[str, Any]:
        """Convert to Discord API registration format."""
        return {
            "name": self.name,
            "description": self.description,
            "options": [opt.to_dict() for opt in self.options],
        }


@dataclass
class DiscordInteraction:
    """
    Parsed Discord interaction data.

    Attributes:
        command_name: Name of the invoked command
        options: Dictionary of option values
        user_id: ID of user who invoked command
        username: Username of invoking user
        channel_id: Channel where command was invoked
        guild_id: Guild where command was invoked
    """

    command_name: str
    options: Dict[str, Any]
    user_id: str
    username: str
    channel_id: str
    guild_id: Optional[str] = None


# Legacy alias for compatibility
DiscordMessage = ChatMessage


# =============================================================================
# Discord Adapter Implementation
# =============================================================================


class DiscordAdapter:
    """
    Discord platform adapter implementing BasePlatformAdapter protocol.

    Provides integration with Discord for:
    - Message receiving and sending
    - Thread and reply context
    - Slash command handling
    - DM support

    Example:
        config = DiscordConfig(
            token="your-bot-token",
            application_id="your-app-id",
        )
        adapter = DiscordAdapter(config)

        @adapter.on_message
        async def handle_message(msg: ChatMessage):
            print(f"Received: {msg.content}")

        await adapter.connect()
    """

    def __init__(self, config: DiscordConfig):
        """
        Initialize Discord adapter.

        Args:
            config: Discord configuration
        """
        self.config = config
        self._connection_state = ConnectionState.DISCONNECTED
        self._discord_client = None
        self._bot_user_id: Optional[str] = None

        # Event callbacks
        self.on_message: Optional[Callable[[ChatMessage], Awaitable[None]]] = None
        self.on_ready: Optional[Callable[[], Awaitable[None]]] = None
        self.on_interaction: Optional[Callable[[DiscordInteraction], Awaitable[None]]] = None

        # Registered commands
        self._commands: List[DiscordSlashCommand] = []

    @property
    def platform(self) -> str:
        """Return platform identifier."""
        return "discord"

    @property
    def bot_user_id(self) -> Optional[str]:
        """Return bot's user ID."""
        if self._discord_client and self._discord_client.user:
            return str(self._discord_client.user.id)
        return self._bot_user_id

    def get_connection_state(self) -> ConnectionState:
        """Return current connection state."""
        return self._connection_state

    async def connect(self) -> None:
        """
        Connect to Discord gateway.

        Raises:
            Exception: If connection fails
        """
        self._connection_state = ConnectionState.CONNECTING

        try:
            if self._discord_client is None:
                self._create_client()

            # Start the client in background
            await self._discord_client.start(self.config.token)
            await self._discord_client.wait_until_ready()

            self._connection_state = ConnectionState.CONNECTED
            self._bot_user_id = str(self._discord_client.user.id)
            logger.info(f"Connected to Discord as {self._discord_client.user}")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            logger.error(f"Failed to connect to Discord: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Discord gateway."""
        if self._discord_client:
            await self._discord_client.close()

        self._connection_state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from Discord")

    def _create_client(self) -> None:
        """Create Discord client with intents."""
        try:
            import discord

            # Build intents from config
            intents = discord.Intents.default()

            if "message_content" in self.config.intents:
                intents.message_content = True
            if "guild_messages" in self.config.intents:
                intents.guild_messages = True
            if "direct_messages" in self.config.intents:
                intents.dm_messages = True
            if "guilds" in self.config.intents:
                intents.guilds = True

            self._discord_client = discord.Client(intents=intents)

            # Set up event handlers
            @self._discord_client.event
            async def on_ready():
                await self._handle_ready()

            @self._discord_client.event
            async def on_message(message):
                await self._handle_message(message)

        except ImportError:
            logger.warning("discord.py not installed, using mock client")
            self._discord_client = _MockDiscordClient()

    async def _handle_ready(self) -> None:
        """Handle Discord ready event."""
        logger.info(f"Discord bot ready: {self._discord_client.user}")

        if self.on_ready:
            await self.on_ready()

    async def _handle_message(self, discord_msg: Any) -> None:
        """
        Handle incoming Discord message.

        Args:
            discord_msg: Discord message object
        """
        # Ignore own messages
        if self._discord_client.user and discord_msg.author.id == self._discord_client.user.id:
            return

        # Parse to ChatMessage
        chat_msg = self.parse_message(discord_msg)

        # Invoke callback
        if self.on_message:
            await self.on_message(chat_msg)

    def parse_message(self, discord_msg: Any) -> ChatMessage:
        """
        Parse Discord message to ChatMessage.

        Args:
            discord_msg: Discord message object

        Returns:
            Normalized ChatMessage
        """
        # Extract author info
        author = MessageAuthor(
            id=str(discord_msg.author.id),
            username=discord_msg.author.name,
            display_name=getattr(discord_msg.author, "display_name", None),
            avatar_url=discord_msg.author.avatar.url if discord_msg.author.avatar else None,
            is_bot=discord_msg.author.bot,
        )

        # Extract attachments
        attachments = []
        for att in discord_msg.attachments:
            attachments.append({
                "id": str(att.id),
                "filename": att.filename,
                "url": att.url,
                "content_type": getattr(att, "content_type", None),
                "size": getattr(att, "size", None),
            })

        # Determine if DM
        is_dm = getattr(discord_msg, "guild", None) is None

        # Determine thread ID
        thread_id = None
        channel_type = getattr(discord_msg.channel, "type", None)
        if channel_type:
            type_name = getattr(channel_type, "name", str(channel_type))
            if "thread" in type_name.lower():
                thread_id = str(discord_msg.channel.id)

        # Handle reply reference
        reply_to_id = None
        if discord_msg.reference and discord_msg.reference.message_id:
            reply_to_id = str(discord_msg.reference.message_id)

        # Build metadata
        metadata = {}

        # Extract mentions
        if hasattr(discord_msg, "mentions") and discord_msg.mentions:
            metadata["mentions"] = [m.name for m in discord_msg.mentions]

        # Extract role mentions
        if hasattr(discord_msg, "role_mentions") and discord_msg.role_mentions:
            metadata["role_mentions"] = [
                {"id": str(r.id), "name": r.name}
                for r in discord_msg.role_mentions
            ]

        return ChatMessage(
            id=str(discord_msg.id),
            content=discord_msg.content,
            author=author,
            channel_id=str(discord_msg.channel.id),
            timestamp=discord_msg.created_at,
            platform="discord",
            thread_id=thread_id,
            reply_to_id=reply_to_id,
            is_direct_message=is_dm,
            attachments=attachments,
            metadata=metadata,
        )

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
    ) -> ChatMessage:
        """
        Send a message to a Discord channel.

        Args:
            channel_id: Channel ID to send to
            content: Message content
            reply_to: Optional message ID to reply to

        Returns:
            The sent ChatMessage

        Raises:
            Exception: If not connected or send fails
        """
        if self._connection_state != ConnectionState.CONNECTED:
            raise Exception("Not connected to Discord")

        channel = await self._get_channel(channel_id)

        # Split long messages
        messages = self._split_message(content)
        sent_msg = None

        for i, msg_content in enumerate(messages):
            kwargs = {"content": msg_content}

            # Add reference for first message if replying
            if i == 0 and reply_to:
                try:
                    ref_msg = await channel.fetch_message(int(reply_to))
                    kwargs["reference"] = ref_msg
                except Exception:
                    pass  # Skip reference if fetch fails

            sent_msg = await channel.send(**kwargs)

        # Return last message as ChatMessage
        return ChatMessage(
            id=str(sent_msg.id),
            content=content,
            author=MessageAuthor(
                id=self.bot_user_id or "",
                username="bot",
            ),
            channel_id=channel_id,
            timestamp=datetime.now(),
            platform="discord",
        )

    def _split_message(self, content: str, max_length: int = 2000) -> List[str]:
        """Split message into chunks for Discord's limit."""
        if len(content) <= max_length:
            return [content]

        chunks = []
        while content:
            if len(content) <= max_length:
                chunks.append(content)
                break

            # Find a good split point
            split_at = max_length
            for sep in ["\n", ". ", " "]:
                idx = content.rfind(sep, 0, max_length)
                if idx > 0:
                    split_at = idx + len(sep)
                    break

            chunks.append(content[:split_at])
            content = content[split_at:]

        return chunks

    async def _get_channel(self, channel_id: str) -> Any:
        """Get Discord channel by ID."""
        return await self._discord_client.fetch_channel(int(channel_id))

    # =========================================================================
    # Slash Command Support
    # =========================================================================

    async def register_commands(self, commands: List[DiscordSlashCommand]) -> None:
        """
        Register slash commands with Discord.

        Args:
            commands: List of commands to register
        """
        self._commands = commands

        if not self._discord_client:
            return

        for cmd in commands:
            # Add to command tree
            if hasattr(self._discord_client, "tree"):
                self._discord_client.tree.add_command(cmd)
            else:
                # Mock path
                self._discord_client.tree = type("Tree", (), {
                    "add_command": lambda x: None,
                    "sync": lambda: None,
                })()
                self._discord_client.tree.add_command(cmd)

        # Sync commands
        if hasattr(self._discord_client.tree, "sync"):
            await self._discord_client.tree.sync()

    def parse_interaction(self, interaction: Any) -> DiscordInteraction:
        """
        Parse Discord interaction to DiscordInteraction.

        Args:
            interaction: Discord interaction object

        Returns:
            Parsed DiscordInteraction
        """
        options = {}
        if interaction.data and "options" in interaction.data:
            for opt in interaction.data["options"]:
                options[opt["name"]] = opt["value"]

        return DiscordInteraction(
            command_name=interaction.data.get("name", ""),
            options=options,
            user_id=str(interaction.user.id),
            username=interaction.user.name,
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id) if hasattr(interaction, "guild_id") and interaction.guild_id else None,
        )

    async def respond_to_interaction(
        self,
        interaction: Any,
        content: str,
        ephemeral: bool = False,
    ) -> None:
        """
        Respond to a slash command interaction.

        Args:
            interaction: Discord interaction object
            content: Response content
            ephemeral: Whether response is only visible to invoker
        """
        if not interaction.response.is_done():
            await interaction.response.send_message(
                content=content,
                ephemeral=ephemeral,
            )
        else:
            await interaction.followup.send(
                content=content,
                ephemeral=ephemeral,
            )

    async def defer_response(self, interaction: Any, ephemeral: bool = False) -> None:
        """
        Defer response for long-running operations.

        Args:
            interaction: Discord interaction object
            ephemeral: Whether final response is ephemeral
        """
        await interaction.response.defer(ephemeral=ephemeral)

    async def send_followup(
        self,
        interaction: Any,
        content: str,
        ephemeral: bool = False,
    ) -> None:
        """
        Send followup message after deferring.

        Args:
            interaction: Discord interaction object
            content: Followup content
            ephemeral: Whether message is ephemeral
        """
        await interaction.followup.send(content=content, ephemeral=ephemeral)

    # =========================================================================
    # Gateway Integration
    # =========================================================================

    def create_gateway_request(self, discord_msg: Any) -> GatewayRequest:
        """
        Create GatewayRequest from Discord message.

        Args:
            discord_msg: Discord message object

        Returns:
            GatewayRequest for ChatbotGateway
        """
        chat_msg = self.parse_message(discord_msg)

        workspace_id = None
        if hasattr(discord_msg, "guild") and discord_msg.guild:
            workspace_id = str(discord_msg.guild.id)

        return GatewayRequest(
            message=chat_msg,
            platform="discord",
            thread_id=chat_msg.thread_id,
            workspace_id=workspace_id,
        )


# =============================================================================
# Mock Client for Testing
# =============================================================================


class _MockDiscordClient:
    """Mock Discord client for testing without discord.py."""

    def __init__(self):
        self.user = None
        self.tree = type("Tree", (), {
            "add_command": lambda self, x: None,
            "sync": lambda self: None,
            "command": lambda self: lambda f: f,
        })()

    async def start(self, token: str) -> None:
        """Mock start."""
        self.user = type("User", (), {"id": 123456789, "name": "MockBot"})()

    async def wait_until_ready(self) -> None:
        """Mock wait."""
        pass

    async def close(self) -> None:
        """Mock close."""
        self.user = None

    async def fetch_channel(self, channel_id: int) -> Any:
        """Mock fetch channel."""
        return type("Channel", (), {
            "id": channel_id,
            "send": lambda **kwargs: type("Message", (), {"id": 999})(),
            "fetch_message": lambda msg_id: type("Message", (), {"id": msg_id})(),
        })()
