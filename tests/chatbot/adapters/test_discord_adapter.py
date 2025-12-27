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
TDD: RED Phase - Tests for Discord adapter.

These tests define the expected behavior for the Discord platform adapter
before implementation. They should FAIL until the adapter is implemented.

Related GitHub Issues:
- #38: Test DiscordAdapter connection lifecycle
- #39: Test Discord message parsing
- #40: Implement DiscordAdapter
- #41: Test Discord thread context
- #42: Test Discord slash commands
- #43: Implement Discord slash commands

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from datetime import datetime
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, patch

# Import the adapter - this will fail until implemented (RED phase)
from src.chatbot.adapters.discord_adapter import (
    DiscordAdapter,
    DiscordConfig,
    DiscordMessage,
    DiscordSlashCommand,
    DiscordCommandOption,
    DiscordInteraction,
)

from src.chatbot.adapters.base import (
    BasePlatformAdapter,
    ConnectionState,
    ChatMessage,
    MessageAuthor,
    AdapterConfig,
)


# =============================================================================
# Discord Configuration Tests
# =============================================================================


class TestDiscordConfig:
    """TDD: Tests for Discord configuration."""

    def test_config_has_required_fields(self):
        """DiscordConfig should have required fields."""
        config = DiscordConfig(
            token="discord-bot-token",
            application_id="123456789",
        )

        assert config.token == "discord-bot-token"
        assert config.application_id == "123456789"

    def test_config_has_optional_fields(self):
        """DiscordConfig should support optional fields."""
        config = DiscordConfig(
            token="discord-bot-token",
            application_id="123456789",
            guild_id="987654321",
            intents=["guilds", "messages", "message_content"],
            command_prefix="!",
        )

        assert config.guild_id == "987654321"
        assert "message_content" in config.intents

    def test_config_default_intents(self):
        """DiscordConfig should have sensible default intents."""
        config = DiscordConfig(
            token="token",
            application_id="app_id",
        )

        # Should have basic intents for chatbot functionality
        assert config.intents is not None
        assert len(config.intents) > 0


# =============================================================================
# Connection Lifecycle Tests (Issue #38)
# =============================================================================


class TestDiscordAdapterConnection:
    """TDD: Tests for Discord adapter connection lifecycle."""

    @pytest.fixture
    def config(self):
        """Create test Discord config."""
        return DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )

    def test_adapter_implements_protocol(self, config):
        """DiscordAdapter should implement BasePlatformAdapter."""
        adapter = DiscordAdapter(config)
        assert isinstance(adapter, BasePlatformAdapter)

    def test_adapter_has_platform_name(self, config):
        """DiscordAdapter should identify as 'discord' platform."""
        adapter = DiscordAdapter(config)
        assert adapter.platform == "discord"

    def test_adapter_starts_disconnected(self, config):
        """DiscordAdapter should start in DISCONNECTED state."""
        adapter = DiscordAdapter(config)
        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_connects_successfully(self, config):
        """DiscordAdapter should transition to CONNECTED on connect."""
        adapter = DiscordAdapter(config)

        with patch.object(adapter, "_discord_client") as mock_client:
            mock_client.start = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()

            await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_adapter_disconnects_successfully(self, config):
        """DiscordAdapter should transition to DISCONNECTED on disconnect."""
        adapter = DiscordAdapter(config)

        with patch.object(adapter, "_discord_client") as mock_client:
            mock_client.start = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()
            mock_client.close = AsyncMock()

            await adapter.connect()
            await adapter.disconnect()

            assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_handles_connection_error(self, config):
        """DiscordAdapter should handle connection errors gracefully."""
        adapter = DiscordAdapter(config)

        with patch.object(adapter, "_discord_client") as mock_client:
            mock_client.start = AsyncMock(side_effect=Exception("Connection failed"))

            with pytest.raises(Exception):
                await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_adapter_reconnects_on_disconnect(self, config):
        """DiscordAdapter should support reconnection after disconnect."""
        adapter = DiscordAdapter(config)

        with patch.object(adapter, "_discord_client") as mock_client:
            mock_client.start = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()
            mock_client.close = AsyncMock()

            # Connect, disconnect, reconnect
            await adapter.connect()
            await adapter.disconnect()
            await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.CONNECTED

    def test_adapter_exposes_bot_user_id(self, config):
        """DiscordAdapter should expose bot user ID when connected."""
        adapter = DiscordAdapter(config)

        with patch.object(adapter, "_discord_client") as mock_client:
            mock_client.user = MagicMock()
            mock_client.user.id = 123456789

            assert adapter.bot_user_id == "123456789"


# =============================================================================
# Message Parsing Tests (Issue #39)
# =============================================================================


class TestDiscordMessageParsing:
    """TDD: Tests for Discord message parsing and normalization."""

    @pytest.fixture
    def adapter(self):
        """Create test Discord adapter."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        return DiscordAdapter(config)

    def test_parse_simple_message(self, adapter):
        """Should parse simple Discord message to ChatMessage."""
        discord_msg = MagicMock()
        discord_msg.id = 123456789
        discord_msg.content = "Hello, world!"
        discord_msg.author.id = 987654321
        discord_msg.author.name = "testuser"
        discord_msg.author.display_name = "Test User"
        discord_msg.author.avatar = MagicMock()
        discord_msg.author.avatar.url = "https://cdn.discord.com/avatar.png"
        discord_msg.author.bot = False
        discord_msg.channel.id = 111222333
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []

        chat_msg = adapter.parse_message(discord_msg)

        assert chat_msg.id == "123456789"
        assert chat_msg.content == "Hello, world!"
        assert chat_msg.author.username == "testuser"
        assert chat_msg.platform == "discord"

    def test_parse_message_with_mention(self, adapter):
        """Should parse message with user mention."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Hello <@987654321>!"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = "User One"
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "text"
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = MagicMock()
        discord_msg.role_mentions = []

        # Create a proper mock for mentions
        mentioned_user = MagicMock()
        mentioned_user.name = "mentioned_user"
        discord_msg.mentions = [mentioned_user]

        chat_msg = adapter.parse_message(discord_msg)

        assert "<@987654321>" in chat_msg.content
        assert "mentioned_user" in chat_msg.metadata.get("mentions", [])

    def test_parse_message_with_role_mention(self, adapter):
        """Should parse message with role mention."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Hello <@&555666777>!"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.role_mentions = [MagicMock(id=555666777, name="Moderators")]

        chat_msg = adapter.parse_message(discord_msg)

        assert "role_mentions" in chat_msg.metadata

    def test_parse_message_with_attachments(self, adapter):
        """Should parse message with attachments."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Check this out!"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None

        attachment = MagicMock()
        attachment.id = 999
        attachment.filename = "image.png"
        attachment.url = "https://cdn.discord.com/attachments/image.png"
        attachment.content_type = "image/png"
        attachment.size = 12345
        discord_msg.attachments = [attachment]

        chat_msg = adapter.parse_message(discord_msg)

        assert len(chat_msg.attachments) == 1
        assert chat_msg.attachments[0]["filename"] == "image.png"
        assert chat_msg.attachments[0]["content_type"] == "image/png"

    def test_parse_message_from_bot(self, adapter):
        """Should identify messages from bots."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "I am a bot"
        discord_msg.author.id = 111
        discord_msg.author.name = "bot_user"
        discord_msg.author.display_name = "Bot User"
        discord_msg.author.avatar = None
        discord_msg.author.bot = True
        discord_msg.channel.id = 222
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []

        chat_msg = adapter.parse_message(discord_msg)

        assert chat_msg.author.is_bot is True

    def test_parse_message_with_emoji(self, adapter):
        """Should handle custom and unicode emoji."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Hello 👋 <:custom:123456789>"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []

        chat_msg = adapter.parse_message(discord_msg)

        # Unicode emoji should be preserved
        assert "👋" in chat_msg.content
        # Custom emoji should be in content or metadata
        assert "<:custom:123456789>" in chat_msg.content or "custom_emojis" in chat_msg.metadata

    def test_parse_dm_message(self, adapter):
        """Should identify direct messages."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Private message"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "private"
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = None  # No guild = DM

        chat_msg = adapter.parse_message(discord_msg)

        assert chat_msg.is_direct_message is True


# =============================================================================
# Message Sending Tests
# =============================================================================


class TestDiscordMessageSending:
    """TDD: Tests for sending messages via Discord."""

    @pytest.fixture
    def adapter(self):
        """Create test Discord adapter in connected state."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        adapter = DiscordAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._bot_user_id = "123456789"
        return adapter

    @pytest.mark.asyncio
    async def test_send_simple_message(self, adapter):
        """Should send simple text message."""
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=MagicMock(id=999))

        with patch.object(adapter, "_get_channel", return_value=mock_channel):
            result = await adapter.send_message("channel-123", "Hello!")

            mock_channel.send.assert_called_once()
            assert result.id == "999"

    @pytest.mark.asyncio
    async def test_send_message_with_reply(self, adapter):
        """Should send message as reply to another message."""
        mock_channel = AsyncMock()
        mock_message = MagicMock(id=999)
        mock_channel.send = AsyncMock(return_value=mock_message)
        mock_channel.fetch_message = AsyncMock(return_value=MagicMock(id=888))

        with patch.object(adapter, "_get_channel", return_value=mock_channel):
            result = await adapter.send_message(
                "channel-123",
                "This is a reply",
                reply_to="888",
            )

            # Should have used reference parameter
            call_kwargs = mock_channel.send.call_args.kwargs
            assert "reference" in call_kwargs or mock_channel.fetch_message.called

    @pytest.mark.asyncio
    async def test_send_long_message_splits(self, adapter):
        """Should split long messages that exceed Discord limit."""
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=MagicMock(id=999))

        # Create message longer than Discord's 2000 char limit
        long_content = "x" * 2500

        with patch.object(adapter, "_get_channel", return_value=mock_channel):
            await adapter.send_message("channel-123", long_content)

            # Should have sent multiple messages
            assert mock_channel.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_send_message_requires_connection(self):
        """Should raise error if not connected."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        adapter = DiscordAdapter(config)
        adapter._connection_state = ConnectionState.DISCONNECTED

        with pytest.raises(Exception) as exc_info:
            await adapter.send_message("channel-123", "Hello!")

        assert "not connected" in str(exc_info.value).lower()


# =============================================================================
# Thread Context Tests (Issue #41)
# =============================================================================


class TestDiscordThreadContext:
    """TDD: Tests for Discord thread context handling."""

    @pytest.fixture
    def adapter(self):
        """Create test Discord adapter in connected state."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        adapter = DiscordAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._bot_user_id = "123456789"
        return adapter

    def test_extract_thread_id_from_thread_message(self, adapter):
        """Should extract thread ID from messages in threads."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Thread message"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 444555666  # Thread channel ID
        discord_msg.channel.type.name = "public_thread"
        discord_msg.channel.parent_id = 111222333  # Parent channel
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = MagicMock()

        chat_msg = adapter.parse_message(discord_msg)

        assert chat_msg.thread_id == "444555666"

    def test_extract_thread_id_from_reply(self, adapter):
        """Should extract thread ID from reply chain."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Reply message"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "text"
        discord_msg.created_at = datetime.now()
        discord_msg.attachments = []
        discord_msg.guild = MagicMock()

        # Has a reference to another message
        discord_msg.reference = MagicMock()
        discord_msg.reference.message_id = 999888777

        chat_msg = adapter.parse_message(discord_msg)

        # Thread ID should be the referenced message
        assert chat_msg.thread_id == "999888777" or chat_msg.reply_to_id == "999888777"

    def test_no_thread_id_for_standalone_message(self, adapter):
        """Standalone messages should not have thread ID."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Standalone message"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "text"
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = MagicMock()

        chat_msg = adapter.parse_message(discord_msg)

        # No thread ID for standalone message in regular channel
        assert chat_msg.thread_id is None

    @pytest.mark.asyncio
    async def test_send_message_to_thread(self, adapter):
        """Should send message to a specific thread."""
        mock_thread = AsyncMock()
        mock_thread.send = AsyncMock(return_value=MagicMock(id=999))

        with patch.object(adapter, "_get_channel", return_value=mock_thread):
            result = await adapter.send_message(
                "thread-444555666",
                "Thread reply",
            )

            mock_thread.send.assert_called_once()


# =============================================================================
# Slash Command Tests (Issue #42)
# =============================================================================


class TestDiscordSlashCommands:
    """TDD: Tests for Discord slash command handling."""

    @pytest.fixture
    def adapter(self):
        """Create test Discord adapter."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        return DiscordAdapter(config)

    def test_command_registration_data(self):
        """Should create valid slash command registration data."""
        command = DiscordSlashCommand(
            name="ask",
            description="Ask the AI a question",
            options=[
                DiscordCommandOption(
                    name="question",
                    description="Your question",
                    type="string",
                    required=True,
                ),
            ],
        )

        registration_data = command.to_registration_dict()

        assert registration_data["name"] == "ask"
        assert registration_data["description"] == "Ask the AI a question"
        assert len(registration_data["options"]) == 1

    def test_command_with_multiple_options(self):
        """Should support multiple command options."""
        command = DiscordSlashCommand(
            name="search",
            description="Search the knowledge base",
            options=[
                DiscordCommandOption(
                    name="query",
                    description="Search query",
                    type="string",
                    required=True,
                ),
                DiscordCommandOption(
                    name="limit",
                    description="Max results",
                    type="integer",
                    required=False,
                ),
            ],
        )

        assert len(command.options) == 2

    def test_command_option_types(self):
        """Should support various option types."""
        options = [
            DiscordCommandOption(name="text", description="Text", type="string"),
            DiscordCommandOption(name="num", description="Number", type="integer"),
            DiscordCommandOption(name="user", description="User", type="user"),
            DiscordCommandOption(name="channel", description="Channel", type="channel"),
            DiscordCommandOption(name="flag", description="Flag", type="boolean"),
        ]

        for opt in options:
            assert opt.type in ["string", "integer", "user", "channel", "boolean", "number"]

    @pytest.mark.asyncio
    async def test_register_slash_commands(self, adapter):
        """Should register slash commands with Discord API."""
        commands = [
            DiscordSlashCommand(
                name="ask",
                description="Ask a question",
            ),
            DiscordSlashCommand(
                name="help",
                description="Get help",
            ),
        ]

        with patch.object(adapter, "_discord_client") as mock_client:
            mock_client.tree = MagicMock()
            mock_client.tree.sync = AsyncMock()

            await adapter.register_commands(commands)

            # Should have added commands to tree
            assert mock_client.tree.add_command.call_count == 2 or \
                   mock_client.tree.command.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_slash_command_interaction(self, adapter):
        """Should handle incoming slash command interaction."""
        interaction = MagicMock()
        interaction.type.name = "application_command"
        interaction.data = {
            "name": "ask",
            "options": [{"name": "question", "value": "What is Python?"}],
        }
        interaction.user.id = 123
        interaction.user.name = "testuser"
        interaction.channel_id = 456

        # Mock response methods
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.defer = AsyncMock()

        parsed = adapter.parse_interaction(interaction)

        assert parsed.command_name == "ask"
        assert parsed.options.get("question") == "What is Python?"

    @pytest.mark.asyncio
    async def test_respond_to_interaction(self, adapter):
        """Should send response to slash command interaction."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)

        await adapter.respond_to_interaction(
            interaction,
            content="Here's your answer!",
        )

        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_respond_ephemeral(self, adapter):
        """Should support ephemeral (private) responses."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)

        await adapter.respond_to_interaction(
            interaction,
            content="Only you can see this",
            ephemeral=True,
        )

        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_defer_response(self, adapter):
        """Should support deferred responses for long operations."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        # Defer first
        await adapter.defer_response(interaction)
        interaction.response.defer.assert_called_once()

        # Then send followup
        await adapter.send_followup(interaction, content="Done processing!")
        interaction.followup.send.assert_called_once()


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestDiscordEventHandling:
    """TDD: Tests for Discord event handling."""

    @pytest.fixture
    def adapter(self):
        """Create test Discord adapter with mock client."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        adapter = DiscordAdapter(config)
        # Create mock client with user
        adapter._discord_client = MagicMock()
        adapter._discord_client.user = MagicMock()
        adapter._discord_client.user.id = 999999  # Bot's ID
        return adapter

    @pytest.mark.asyncio
    async def test_on_message_callback(self, adapter):
        """Should invoke callback when message received."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Test message"
        discord_msg.author.id = 111  # Different from bot
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "text"
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = MagicMock()
        discord_msg.mentions = []
        discord_msg.role_mentions = []

        await adapter._handle_message(discord_msg)

        assert len(messages_received) == 1
        assert messages_received[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_on_ready_callback(self, adapter):
        """Should invoke callback when bot is ready."""
        ready_called = []

        async def on_ready():
            ready_called.append(True)

        adapter.on_ready = on_ready

        await adapter._handle_ready()

        assert len(ready_called) == 1

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, adapter):
        """Should ignore messages from the bot itself."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        # Set bot user ID on client
        adapter._discord_client.user.id = 111

        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Bot message"
        discord_msg.author.id = 111  # Same as bot
        discord_msg.author.name = "bot"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = True
        discord_msg.channel.id = 222
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []

        await adapter._handle_message(discord_msg)

        assert len(messages_received) == 0


# =============================================================================
# Integration with Gateway Tests
# =============================================================================


class TestDiscordGatewayIntegration:
    """TDD: Tests for Discord adapter integration with ChatbotGateway."""

    @pytest.fixture
    def adapter(self):
        """Create test Discord adapter."""
        config = DiscordConfig(
            token="test-token",
            application_id="test-app-id",
        )
        return DiscordAdapter(config)

    def test_creates_gateway_request_from_message(self, adapter):
        """Should create GatewayRequest from Discord message."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Hello bot!"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = "User One"
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "text"
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = MagicMock()
        discord_msg.guild.id = 999

        gateway_request = adapter.create_gateway_request(discord_msg)

        assert gateway_request.platform == "discord"
        assert gateway_request.message.content == "Hello bot!"
        assert gateway_request.workspace_id == "999"

    def test_creates_gateway_request_from_dm(self, adapter):
        """Should create GatewayRequest from DM with no workspace."""
        discord_msg = MagicMock()
        discord_msg.id = 123
        discord_msg.content = "Private message"
        discord_msg.author.id = 111
        discord_msg.author.name = "user1"
        discord_msg.author.display_name = None
        discord_msg.author.avatar = None
        discord_msg.author.bot = False
        discord_msg.channel.id = 222
        discord_msg.channel.type.name = "private"
        discord_msg.created_at = datetime.now()
        discord_msg.reference = None
        discord_msg.attachments = []
        discord_msg.guild = None

        gateway_request = adapter.create_gateway_request(discord_msg)

        assert gateway_request.workspace_id is None
        assert gateway_request.message.is_direct_message is True
