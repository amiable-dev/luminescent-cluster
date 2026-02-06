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
TDD Tests for WhatsApp platform adapter.

These tests follow the RED-GREEN-REFACTOR cycle per ADR-006 Phase 4.
Test coverage for:
- Connection lifecycle (Issue #56)
- Message parsing (Issue #57)
- WhatsAppAdapter implementation (Issue #58)
- Interactive messages (Issues #59-60)

Version: 1.0.0
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import hmac
import hashlib

from luminescent_cluster.chatbot.adapters.base import (
    BasePlatformAdapter,
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)
from luminescent_cluster.chatbot.gateway import GatewayRequest


# =============================================================================
# Configuration Tests
# =============================================================================


class TestWhatsAppConfig:
    """TDD: Tests for WhatsAppConfig dataclass."""

    def test_config_has_required_fields(self):
        """WhatsAppConfig should require access_token and phone_number_id."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )

        assert config.access_token == "EAAxxxxxxx"
        assert config.phone_number_id == "123456789"

    def test_config_has_webhook_verify_token(self):
        """WhatsAppConfig should support webhook verification token."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
            webhook_verify_token="my_verify_token",
        )

        assert config.webhook_verify_token == "my_verify_token"

    def test_config_has_app_secret(self):
        """WhatsAppConfig should support app secret for signature verification."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
            app_secret="app_secret_123",
        )

        assert config.app_secret == "app_secret_123"

    def test_config_has_business_account_id(self):
        """WhatsAppConfig should support business account ID."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
            business_account_id="987654321",
        )

        assert config.business_account_id == "987654321"


# =============================================================================
# Connection Lifecycle Tests (Issue #56)
# =============================================================================


class TestWhatsAppAdapterConnection:
    """TDD: Tests for WhatsAppAdapter connection lifecycle."""

    @pytest.fixture
    def config(self):
        """Create test WhatsApp config."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig

        return WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
            webhook_verify_token="verify_token",
            app_secret="app_secret",
        )

    def test_adapter_implements_protocol(self, config):
        """WhatsAppAdapter should implement BasePlatformAdapter protocol."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        assert isinstance(adapter, BasePlatformAdapter)

    def test_adapter_has_platform_name(self, config):
        """WhatsAppAdapter should report 'whatsapp' as platform."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        assert adapter.platform == "whatsapp"

    def test_adapter_starts_disconnected(self, config):
        """WhatsAppAdapter should start in DISCONNECTED state."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_connects_via_cloud_api(self, config):
        """WhatsAppAdapter should connect via Cloud API."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        # Mock the API verification
        with patch.object(adapter, "_verify_api_access", new_callable=AsyncMock):
            await adapter.connect()

        assert adapter.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_adapter_verifies_api_access(self, config):
        """WhatsAppAdapter should verify API access on connect."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        # Mock the API verification
        with patch.object(adapter, "_verify_api_access", new_callable=AsyncMock):
            await adapter.connect()

        # Should have phone number from config
        assert adapter.phone_number_id == "123456789"

    @pytest.mark.asyncio
    async def test_adapter_disconnects_successfully(self, config):
        """WhatsAppAdapter should disconnect cleanly."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        # Mock the API verification
        with patch.object(adapter, "_verify_api_access", new_callable=AsyncMock):
            await adapter.connect()

        await adapter.disconnect()

        assert adapter.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_adapter_handles_connection_error(self, config):
        """WhatsAppAdapter should handle connection errors."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        with patch.object(
            adapter, "_verify_api_access", side_effect=Exception("API error")
        ):
            with pytest.raises(Exception):
                await adapter.connect()

            assert adapter.get_connection_state() == ConnectionState.ERROR

    def test_adapter_exposes_phone_number_id(self, config):
        """WhatsAppAdapter should expose phone number ID."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter(config)

        assert adapter.phone_number_id == "123456789"


# =============================================================================
# Webhook Verification Tests
# =============================================================================


class TestWhatsAppWebhookVerification:
    """TDD: Tests for WhatsApp webhook verification."""

    @pytest.fixture
    def adapter(self):
        """Create test WhatsApp adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
            webhook_verify_token="my_verify_token",
            app_secret="my_app_secret",
        )
        return WhatsAppAdapter(config)

    def test_verify_webhook_challenge(self, adapter):
        """Should verify webhook subscription challenge."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "my_verify_token",
            "hub.challenge": "challenge_code_123",
        }

        result = adapter.verify_webhook(params)

        assert result == "challenge_code_123"

    def test_reject_invalid_verify_token(self, adapter):
        """Should reject invalid verify token."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_code_123",
        }

        result = adapter.verify_webhook(params)

        assert result is None

    def test_verify_webhook_signature(self, adapter):
        """Should verify webhook payload signature."""
        payload = b'{"entry": []}'
        secret = "my_app_secret"

        # Generate valid signature
        signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        is_valid = adapter.verify_signature(payload, f"sha256={signature}")

        assert is_valid is True

    def test_reject_invalid_signature(self, adapter):
        """Should reject invalid webhook signature."""
        payload = b'{"entry": []}'

        is_valid = adapter.verify_signature(payload, "sha256=invalid_signature")

        assert is_valid is False


# =============================================================================
# Message Parsing Tests (Issue #57)
# =============================================================================


class TestWhatsAppMessageParsing:
    """TDD: Tests for WhatsApp message parsing and normalization."""

    @pytest.fixture
    def adapter(self):
        """Create test WhatsApp adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        return WhatsAppAdapter(config)

    def test_parse_text_message(self, adapter):
        """Should parse text message to ChatMessage."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "1234567890",
                            "phone_number_id": "123456789",
                        },
                        "contacts": [{
                            "profile": {"name": "John Doe"},
                            "wa_id": "15551234567",
                        }],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.xxx",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello, world!"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.content == "Hello, world!"
        assert msg.id == "wamid.xxx"
        assert msg.author.id == "15551234567"
        assert msg.author.display_name == "John Doe"
        assert msg.platform == "whatsapp"

    def test_parse_image_message(self, adapter):
        """Should parse image message."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.img",
                            "timestamp": "1234567890",
                            "type": "image",
                            "image": {
                                "id": "media_id_123",
                                "mime_type": "image/jpeg",
                                "sha256": "abc123",
                                "caption": "Check this out!",
                            },
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.content == "Check this out!"
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["type"] == "image"
        assert msg.attachments[0]["media_id"] == "media_id_123"

    def test_parse_document_message(self, adapter):
        """Should parse document message."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.doc",
                            "timestamp": "1234567890",
                            "type": "document",
                            "document": {
                                "id": "doc_media_id",
                                "mime_type": "application/pdf",
                                "filename": "report.pdf",
                            },
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["type"] == "document"
        assert msg.attachments[0]["filename"] == "report.pdf"

    def test_parse_location_message(self, adapter):
        """Should parse location message."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.loc",
                            "timestamp": "1234567890",
                            "type": "location",
                            "location": {
                                "latitude": 37.7749,
                                "longitude": -122.4194,
                                "name": "San Francisco",
                                "address": "San Francisco, CA",
                            },
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.metadata.get("location") is not None
        assert msg.metadata["location"]["latitude"] == 37.7749

    def test_parse_contact_message(self, adapter):
        """Should parse contact message."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.contact",
                            "timestamp": "1234567890",
                            "type": "contacts",
                            "contacts": [{
                                "name": {"formatted_name": "Jane Smith"},
                                "phones": [{"phone": "+15559876543", "type": "CELL"}],
                            }],
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.metadata.get("shared_contacts") is not None

    def test_parse_interactive_reply(self, adapter):
        """Should parse interactive message reply."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.interactive",
                            "timestamp": "1234567890",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": "btn_yes",
                                    "title": "Yes",
                                },
                            },
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.metadata.get("interactive_reply") is not None
        assert msg.metadata["interactive_reply"]["type"] == "button_reply"
        assert msg.metadata["interactive_reply"]["id"] == "btn_yes"

    def test_parse_list_reply(self, adapter):
        """Should parse list selection reply."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.list",
                            "timestamp": "1234567890",
                            "type": "interactive",
                            "interactive": {
                                "type": "list_reply",
                                "list_reply": {
                                    "id": "item_1",
                                    "title": "Option 1",
                                    "description": "First option",
                                },
                            },
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.metadata["interactive_reply"]["type"] == "list_reply"
        assert msg.metadata["interactive_reply"]["id"] == "item_1"

    def test_parse_message_status(self, adapter):
        """Should parse message status updates."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "statuses": [{
                            "id": "wamid.xxx",
                            "status": "delivered",
                            "timestamp": "1234567890",
                            "recipient_id": "15551234567",
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        statuses = adapter.parse_status_updates(webhook_payload)

        assert len(statuses) == 1
        assert statuses[0]["message_id"] == "wamid.xxx"
        assert statuses[0]["status"] == "delivered"


# =============================================================================
# 24-Hour Window Tests
# =============================================================================


class TestWhatsApp24HourWindow:
    """TDD: Tests for WhatsApp 24-hour customer service window."""

    @pytest.fixture
    def adapter(self):
        """Create test WhatsApp adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        return adapter

    def test_track_last_message_time(self, adapter):
        """Should track last message time from user."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.xxx",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        adapter.parse_webhook(webhook_payload)

        assert "15551234567" in adapter._conversation_windows

    def test_check_window_open(self, adapter):
        """Should correctly identify open messaging window."""
        # Set last message to now
        adapter._conversation_windows["15551234567"] = datetime.now()

        is_open = adapter.is_window_open("15551234567")

        assert is_open is True

    def test_check_window_closed(self, adapter):
        """Should correctly identify closed messaging window."""
        # Set last message to 25 hours ago
        adapter._conversation_windows["15551234567"] = datetime.now() - timedelta(hours=25)

        is_open = adapter.is_window_open("15551234567")

        assert is_open is False

    def test_no_window_for_new_user(self, adapter):
        """Should return False for users with no message history."""
        is_open = adapter.is_window_open("unknown_user")

        assert is_open is False


# =============================================================================
# Message Sending Tests
# =============================================================================


class TestWhatsAppMessageSending:
    """TDD: Tests for sending messages via WhatsApp."""

    @pytest.fixture
    def adapter(self):
        """Create connected test adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._api_client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_send_text_message(self, adapter):
        """Should send text message."""
        adapter._api_client.send_message = AsyncMock(
            return_value={
                "messaging_product": "whatsapp",
                "contacts": [{"wa_id": "15551234567"}],
                "messages": [{"id": "wamid.sent"}],
            }
        )

        result = await adapter.send_message(
            channel_id="15551234567",
            content="Hello!",
        )

        assert result.id == "wamid.sent"
        adapter._api_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_requires_connection(self):
        """Should require connection to send message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)

        with pytest.raises(Exception, match="Not connected"):
            await adapter.send_message(channel_id="15551234567", content="Hello!")

    @pytest.mark.asyncio
    async def test_send_message_with_preview_url(self, adapter):
        """Should support URL preview in messages."""
        adapter._api_client.send_message = AsyncMock(
            return_value={"messages": [{"id": "wamid.url"}]}
        )

        await adapter.send_message(
            channel_id="15551234567",
            content="Check out https://example.com",
            preview_url=True,
        )

        call_kwargs = adapter._api_client.send_message.call_args.kwargs
        assert call_kwargs.get("preview_url") is True


# =============================================================================
# Interactive Messages Tests (Issues #59-60)
# =============================================================================


class TestWhatsAppInteractiveMessages:
    """TDD: Tests for WhatsApp interactive messages."""

    @pytest.fixture
    def adapter(self):
        """Create connected test adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._api_client = MagicMock()
        return adapter

    def test_create_button_message(self, adapter):
        """Should create button message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import ButtonMessage, Button

        message = ButtonMessage(
            body="Please select an option:",
            buttons=[
                Button(id="btn_yes", title="Yes"),
                Button(id="btn_no", title="No"),
            ],
        )

        payload = message.to_dict()

        assert payload["type"] == "button"
        assert payload["body"]["text"] == "Please select an option:"
        assert len(payload["action"]["buttons"]) == 2

    def test_create_list_message(self, adapter):
        """Should create list message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import (
            ListMessage,
            ListSection,
            ListRow,
        )

        message = ListMessage(
            body="Select from the menu:",
            button_text="View Options",
            sections=[
                ListSection(
                    title="Category 1",
                    rows=[
                        ListRow(id="item_1", title="Item 1", description="First item"),
                        ListRow(id="item_2", title="Item 2", description="Second item"),
                    ],
                ),
            ],
        )

        payload = message.to_dict()

        assert payload["type"] == "list"
        assert payload["body"]["text"] == "Select from the menu:"
        assert payload["action"]["button"] == "View Options"
        assert len(payload["action"]["sections"]) == 1

    @pytest.mark.asyncio
    async def test_send_button_message(self, adapter):
        """Should send button message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import ButtonMessage, Button

        adapter._api_client.send_interactive = AsyncMock(
            return_value={"messages": [{"id": "wamid.btn"}]}
        )

        message = ButtonMessage(
            body="Choose:",
            buttons=[Button(id="yes", title="Yes")],
        )

        await adapter.send_interactive(
            recipient="15551234567",
            message=message,
        )

        adapter._api_client.send_interactive.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_list_message(self, adapter):
        """Should send list message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import (
            ListMessage,
            ListSection,
            ListRow,
        )

        adapter._api_client.send_interactive = AsyncMock(
            return_value={"messages": [{"id": "wamid.list"}]}
        )

        message = ListMessage(
            body="Menu:",
            button_text="See Options",
            sections=[
                ListSection(
                    title="Options",
                    rows=[ListRow(id="1", title="Option 1")],
                ),
            ],
        )

        await adapter.send_interactive(
            recipient="15551234567",
            message=message,
        )

        adapter._api_client.send_interactive.assert_called_once()


# =============================================================================
# Template Messages Tests
# =============================================================================


class TestWhatsAppTemplateMessages:
    """TDD: Tests for WhatsApp template messages."""

    @pytest.fixture
    def adapter(self):
        """Create connected test adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._api_client = MagicMock()
        return adapter

    def test_create_template_message(self, adapter):
        """Should create template message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import (
            TemplateMessage,
            TemplateComponent,
        )

        template = TemplateMessage(
            name="order_confirmation",
            language_code="en_US",
            components=[
                TemplateComponent(
                    type="body",
                    parameters=[
                        {"type": "text", "text": "John"},
                        {"type": "text", "text": "12345"},
                    ],
                ),
            ],
        )

        payload = template.to_dict()

        assert payload["name"] == "order_confirmation"
        assert payload["language"]["code"] == "en_US"

    @pytest.mark.asyncio
    async def test_send_template_message(self, adapter):
        """Should send template message."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import TemplateMessage

        adapter._api_client.send_template = AsyncMock(
            return_value={"messages": [{"id": "wamid.tpl"}]}
        )

        template = TemplateMessage(
            name="hello_world",
            language_code="en_US",
        )

        await adapter.send_template(
            recipient="15551234567",
            template=template,
        )

        adapter._api_client.send_template.assert_called_once()

    @pytest.mark.asyncio
    async def test_template_required_outside_window(self, adapter):
        """Should require template message when window is closed."""
        # Set window to closed
        adapter._conversation_windows["15551234567"] = datetime.now() - timedelta(hours=25)

        requires_template = adapter.requires_template("15551234567")

        assert requires_template is True


# =============================================================================
# Media Handling Tests
# =============================================================================


class TestWhatsAppMediaHandling:
    """TDD: Tests for WhatsApp media message handling."""

    @pytest.fixture
    def adapter(self):
        """Create connected test adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        adapter._api_client = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_get_media_url(self, adapter):
        """Should get media URL from media ID."""
        adapter._api_client.get_media_url = AsyncMock(
            return_value="https://lookaside.fbsbx.com/whatsapp/xxx"
        )

        url = await adapter.get_media_url("media_id_123")

        assert url.startswith("https://")
        adapter._api_client.get_media_url.assert_called_once_with("media_id_123")

    @pytest.mark.asyncio
    async def test_send_image_message(self, adapter):
        """Should send image message."""
        adapter._api_client.send_media = AsyncMock(
            return_value={"messages": [{"id": "wamid.img"}]}
        )

        await adapter.send_media(
            recipient="15551234567",
            media_type="image",
            media_url="https://example.com/image.jpg",
            caption="Check this out!",
        )

        call_kwargs = adapter._api_client.send_media.call_args.kwargs
        assert call_kwargs["media_type"] == "image"
        assert call_kwargs["caption"] == "Check this out!"

    @pytest.mark.asyncio
    async def test_send_document_message(self, adapter):
        """Should send document message."""
        adapter._api_client.send_media = AsyncMock(
            return_value={"messages": [{"id": "wamid.doc"}]}
        )

        await adapter.send_media(
            recipient="15551234567",
            media_type="document",
            media_url="https://example.com/report.pdf",
            filename="report.pdf",
        )

        call_kwargs = adapter._api_client.send_media.call_args.kwargs
        assert call_kwargs["media_type"] == "document"
        assert call_kwargs["filename"] == "report.pdf"


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestWhatsAppEventHandling:
    """TDD: Tests for WhatsApp event handling."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)
        adapter._connection_state = ConnectionState.CONNECTED
        return adapter

    @pytest.mark.asyncio
    async def test_on_message_callback(self, adapter):
        """Should invoke callback when message received."""
        messages_received = []

        async def on_message(msg: ChatMessage):
            messages_received.append(msg)

        adapter.on_message = on_message

        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.test",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Test message"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        await adapter.handle_webhook(webhook_payload)

        assert len(messages_received) == 1
        assert messages_received[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_on_status_callback(self, adapter):
        """Should invoke callback on status update."""
        statuses_received = []

        async def on_status(status):
            statuses_received.append(status)

        adapter.on_status_update = on_status

        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "statuses": [{
                            "id": "wamid.xxx",
                            "status": "read",
                            "timestamp": "1234567890",
                            "recipient_id": "15551234567",
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        await adapter.handle_webhook(webhook_payload)

        assert len(statuses_received) == 1
        assert statuses_received[0]["status"] == "read"


# =============================================================================
# Gateway Integration Tests
# =============================================================================


class TestWhatsAppGatewayIntegration:
    """TDD: Tests for WhatsApp-Gateway integration."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter."""
        from luminescent_cluster.chatbot.adapters.whatsapp_adapter import WhatsAppConfig, WhatsAppAdapter

        config = WhatsAppConfig(
            access_token="EAAxxxxxxx",
            phone_number_id="123456789",
            business_account_id="987654321",
        )
        return WhatsAppAdapter(config)

    def test_creates_gateway_request_from_message(self, adapter):
        """Should create GatewayRequest from WhatsApp message."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.gateway",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello gateway"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)
        request = adapter.create_gateway_request(messages[0])

        assert isinstance(request, GatewayRequest)
        assert request.platform == "whatsapp"
        assert request.message.content == "Hello gateway"
        assert request.workspace_id == "987654321"

    def test_gateway_request_includes_window_status(self, adapter):
        """Should include messaging window status in request."""
        adapter._conversation_windows["15551234567"] = datetime.now()

        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123456789"},
                        "contacts": [{"profile": {"name": "User"}, "wa_id": "15551234567"}],
                        "messages": [{
                            "from": "15551234567",
                            "id": "wamid.window",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Test"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        messages = adapter.parse_webhook(webhook_payload)
        request = adapter.create_gateway_request(messages[0])

        # Window status should be in metadata
        assert request.message.metadata.get("window_open") is True
