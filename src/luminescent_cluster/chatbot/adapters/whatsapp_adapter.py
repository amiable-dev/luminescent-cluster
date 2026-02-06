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
WhatsApp platform adapter for Luminescent Cluster chatbot.

This module implements the WhatsApp integration using the Cloud API,
with support for webhooks, interactive messages, templates, and
24-hour customer service windows.

Design (from ADR-006):
- Thin adapter routing to ChatbotGateway
- Cloud API for messaging via webhooks
- 24-hour window tracking for message types
- Interactive messages (buttons, lists)
- Template messages for marketing

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Callable, Awaitable, Any, Dict, Union
import asyncio
import logging
import hmac
import hashlib

from luminescent_cluster.chatbot.adapters.base import (
    ConnectionState,
    ChatMessage,
    MessageAuthor,
)
from luminescent_cluster.chatbot.gateway import GatewayRequest

logger = logging.getLogger(__name__)


# Window duration for customer service messaging (24 hours)
CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)


# =============================================================================
# WhatsApp Configuration
# =============================================================================


@dataclass
class WhatsAppConfig:
    """
    Configuration for WhatsApp adapter.

    Attributes:
        access_token: Meta access token for API calls
        phone_number_id: WhatsApp Business phone number ID
        webhook_verify_token: Token for webhook verification
        app_secret: App secret for signature verification
        business_account_id: WhatsApp Business Account ID
        api_version: Graph API version (default v18.0)
    """

    access_token: str
    phone_number_id: str
    webhook_verify_token: Optional[str] = None
    app_secret: Optional[str] = None
    business_account_id: Optional[str] = None
    api_version: str = "v18.0"


# =============================================================================
# Interactive Message Models
# =============================================================================


@dataclass
class Button:
    """
    WhatsApp reply button.

    Attributes:
        id: Button identifier (returned on click)
        title: Button text (max 20 chars)
    """

    id: str
    title: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        return {
            "type": "reply",
            "reply": {
                "id": self.id,
                "title": self.title,
            },
        }


@dataclass
class ButtonMessage:
    """
    WhatsApp button message (max 3 buttons).

    Attributes:
        body: Message body text
        buttons: List of reply buttons (max 3)
        header: Optional header text
        footer: Optional footer text
    """

    body: str
    buttons: List[Button]
    header: Optional[str] = None
    footer: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result: Dict[str, Any] = {
            "type": "button",
            "body": {"text": self.body},
            "action": {
                "buttons": [btn.to_dict() for btn in self.buttons],
            },
        }

        if self.header:
            result["header"] = {"type": "text", "text": self.header}
        if self.footer:
            result["footer"] = {"text": self.footer}

        return result


@dataclass
class ListRow:
    """
    Row in a list section.

    Attributes:
        id: Row identifier (returned on selection)
        title: Row title (max 24 chars)
        description: Optional description (max 72 chars)
    """

    id: str
    title: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result = {"id": self.id, "title": self.title}
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class ListSection:
    """
    Section in a list message.

    Attributes:
        title: Section title
        rows: List of rows in section (max 10)
    """

    title: str
    rows: List[ListRow]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        return {
            "title": self.title,
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass
class ListMessage:
    """
    WhatsApp list message.

    Attributes:
        body: Message body text
        button_text: Button text to open list
        sections: List sections (max 10 sections, 10 rows each)
        header: Optional header text
        footer: Optional footer text
    """

    body: str
    button_text: str
    sections: List[ListSection]
    header: Optional[str] = None
    footer: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result: Dict[str, Any] = {
            "type": "list",
            "body": {"text": self.body},
            "action": {
                "button": self.button_text,
                "sections": [section.to_dict() for section in self.sections],
            },
        }

        if self.header:
            result["header"] = {"type": "text", "text": self.header}
        if self.footer:
            result["footer"] = {"text": self.footer}

        return result


# =============================================================================
# Template Message Models
# =============================================================================


@dataclass
class TemplateComponent:
    """
    Component for template message.

    Attributes:
        type: Component type (header, body, button)
        parameters: List of parameter values
    """

    type: str
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    sub_type: Optional[str] = None
    index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result: Dict[str, Any] = {
            "type": self.type,
            "parameters": self.parameters,
        }
        if self.sub_type:
            result["sub_type"] = self.sub_type
        if self.index is not None:
            result["index"] = self.index
        return result


@dataclass
class TemplateMessage:
    """
    WhatsApp template message.

    Attributes:
        name: Template name
        language_code: Language code (e.g., en_US)
        components: Template components with parameters
    """

    name: str
    language_code: str
    components: List[TemplateComponent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result: Dict[str, Any] = {
            "name": self.name,
            "language": {"code": self.language_code},
        }

        if self.components:
            result["components"] = [comp.to_dict() for comp in self.components]

        return result


# =============================================================================
# WhatsApp Adapter Implementation
# =============================================================================


class WhatsAppAdapter:
    """
    WhatsApp platform adapter implementing BasePlatformAdapter protocol.

    Provides integration with WhatsApp for:
    - Cloud API messaging via webhooks
    - 24-hour customer service window tracking
    - Interactive messages (buttons, lists)
    - Template messages
    - Media handling

    Example:
        config = WhatsAppConfig(
            access_token="EAAxxxx",
            phone_number_id="123456789",
        )
        adapter = WhatsAppAdapter(config)

        @adapter.on_message
        async def handle_message(msg: ChatMessage):
            print(f"Received: {msg.content}")

        await adapter.connect()
    """

    def __init__(self, config: WhatsAppConfig):
        """
        Initialize WhatsApp adapter.

        Args:
            config: WhatsApp configuration
        """
        self.config = config
        self._connection_state = ConnectionState.DISCONNECTED
        self._api_client = None

        # Track 24-hour windows per user
        self._conversation_windows: Dict[str, datetime] = {}

        # Event callbacks
        self.on_message: Optional[Callable[[ChatMessage], Awaitable[None]]] = None
        self.on_status_update: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None

    @property
    def platform(self) -> str:
        """Return platform identifier."""
        return "whatsapp"

    @property
    def phone_number_id(self) -> str:
        """Return phone number ID."""
        return self.config.phone_number_id

    def get_connection_state(self) -> ConnectionState:
        """Return current connection state."""
        return self._connection_state

    async def connect(self) -> None:
        """
        Connect to WhatsApp Cloud API.

        Raises:
            Exception: If connection fails
        """
        self._connection_state = ConnectionState.CONNECTING

        try:
            await self._verify_api_access()
            self._connection_state = ConnectionState.CONNECTED
            logger.info("Connected to WhatsApp Cloud API")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            logger.error(f"Failed to connect to WhatsApp: {e}")
            raise

    async def _verify_api_access(self) -> None:
        """Verify API access by fetching phone number info."""
        try:
            import aiohttp

            url = f"https://graph.facebook.com/{self.config.api_version}/{self.config.phone_number_id}"
            headers = {"Authorization": f"Bearer {self.config.access_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"API verification failed: {response.status}")

                    data = await response.json()
                    logger.info(f"Verified phone number: {data.get('display_phone_number')}")

            self._api_client = _WhatsAppAPIClient(self.config)

        except ImportError:
            logger.warning("aiohttp not installed, using mock client")
            self._api_client = _MockWhatsAppClient()

    async def disconnect(self) -> None:
        """Disconnect from WhatsApp."""
        self._connection_state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from WhatsApp")

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook(self, params: Dict[str, str]) -> Optional[str]:
        """
        Verify webhook subscription challenge.

        Args:
            params: Query parameters from webhook verification request

        Returns:
            Challenge string if valid, None otherwise
        """
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if mode == "subscribe" and token == self.config.webhook_verify_token:
            return challenge

        return None

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook payload signature.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not self.config.app_secret:
            return True  # No secret configured

        if not signature.startswith("sha256="):
            return False

        expected_sig = hmac.new(
            self.config.app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature[7:], expected_sig)

    # =========================================================================
    # Message Parsing
    # =========================================================================

    def parse_webhook(self, payload: Dict[str, Any]) -> List[ChatMessage]:
        """
        Parse webhook payload to list of ChatMessages.

        Args:
            payload: Webhook payload

        Returns:
            List of parsed ChatMessages
        """
        messages = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Get contact info
                contacts = {
                    c["wa_id"]: c.get("profile", {}).get("name", "")
                    for c in value.get("contacts", [])
                }

                # Parse messages
                for msg_data in value.get("messages", []):
                    from_id = msg_data.get("from", "")
                    display_name = contacts.get(from_id, "")

                    # Update conversation window
                    self._conversation_windows[from_id] = datetime.now()

                    chat_msg = self._parse_message(msg_data, from_id, display_name)
                    messages.append(chat_msg)

        return messages

    def _parse_message(
        self,
        msg_data: Dict[str, Any],
        from_id: str,
        display_name: str,
    ) -> ChatMessage:
        """Parse a single message from webhook data."""
        msg_type = msg_data.get("type", "text")
        msg_id = msg_data.get("id", "")
        timestamp = int(msg_data.get("timestamp", "0"))

        # Extract content based on type
        content = ""
        attachments = []
        metadata: Dict[str, Any] = {}

        if msg_type == "text":
            content = msg_data.get("text", {}).get("body", "")

        elif msg_type == "image":
            image_data = msg_data.get("image", {})
            content = image_data.get("caption", "")
            attachments.append({
                "type": "image",
                "media_id": image_data.get("id"),
                "mime_type": image_data.get("mime_type"),
            })

        elif msg_type == "document":
            doc_data = msg_data.get("document", {})
            content = doc_data.get("caption", "")
            attachments.append({
                "type": "document",
                "media_id": doc_data.get("id"),
                "mime_type": doc_data.get("mime_type"),
                "filename": doc_data.get("filename"),
            })

        elif msg_type == "audio":
            audio_data = msg_data.get("audio", {})
            attachments.append({
                "type": "audio",
                "media_id": audio_data.get("id"),
                "mime_type": audio_data.get("mime_type"),
            })

        elif msg_type == "video":
            video_data = msg_data.get("video", {})
            content = video_data.get("caption", "")
            attachments.append({
                "type": "video",
                "media_id": video_data.get("id"),
                "mime_type": video_data.get("mime_type"),
            })

        elif msg_type == "location":
            location_data = msg_data.get("location", {})
            metadata["location"] = {
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
                "name": location_data.get("name"),
                "address": location_data.get("address"),
            }

        elif msg_type == "contacts":
            metadata["shared_contacts"] = msg_data.get("contacts", [])

        elif msg_type == "interactive":
            interactive_data = msg_data.get("interactive", {})
            interactive_type = interactive_data.get("type")

            if interactive_type == "button_reply":
                reply = interactive_data.get("button_reply", {})
                metadata["interactive_reply"] = {
                    "type": "button_reply",
                    "id": reply.get("id"),
                    "title": reply.get("title"),
                }
                content = reply.get("title", "")

            elif interactive_type == "list_reply":
                reply = interactive_data.get("list_reply", {})
                metadata["interactive_reply"] = {
                    "type": "list_reply",
                    "id": reply.get("id"),
                    "title": reply.get("title"),
                    "description": reply.get("description"),
                }
                content = reply.get("title", "")

        # Check window status
        metadata["window_open"] = self.is_window_open(from_id)

        # Convert timestamp
        try:
            dt = datetime.fromtimestamp(timestamp)
        except (ValueError, TypeError):
            dt = datetime.now()

        return ChatMessage(
            id=msg_id,
            content=content,
            author=MessageAuthor(
                id=from_id,
                username=from_id,
                display_name=display_name,
                is_bot=False,
            ),
            channel_id=from_id,  # In WhatsApp, channel_id is the user's phone
            timestamp=dt,
            platform="whatsapp",
            is_direct_message=True,  # WhatsApp is always DM-like
            attachments=attachments,
            metadata=metadata,
        )

    def parse_status_updates(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse status updates from webhook.

        Args:
            payload: Webhook payload

        Returns:
            List of status update dictionaries
        """
        statuses = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                for status in value.get("statuses", []):
                    statuses.append({
                        "message_id": status.get("id"),
                        "status": status.get("status"),
                        "timestamp": status.get("timestamp"),
                        "recipient_id": status.get("recipient_id"),
                    })

        return statuses

    # =========================================================================
    # 24-Hour Window Management
    # =========================================================================

    def is_window_open(self, user_id: str) -> bool:
        """
        Check if 24-hour messaging window is open for user.

        Args:
            user_id: User's phone number

        Returns:
            True if within 24 hours of last message
        """
        last_message = self._conversation_windows.get(user_id)
        if not last_message:
            return False

        return datetime.now() - last_message < CUSTOMER_SERVICE_WINDOW

    def requires_template(self, user_id: str) -> bool:
        """
        Check if user requires template message (window closed).

        Args:
            user_id: User's phone number

        Returns:
            True if template message is required
        """
        return not self.is_window_open(user_id)

    # =========================================================================
    # Message Sending
    # =========================================================================

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
        preview_url: bool = False,
    ) -> ChatMessage:
        """
        Send a text message.

        Args:
            channel_id: Recipient phone number
            content: Message text
            reply_to: Optional message ID to reply to
            preview_url: Whether to show URL preview

        Returns:
            The sent ChatMessage

        Raises:
            Exception: If not connected or send fails
        """
        if self._connection_state != ConnectionState.CONNECTED:
            raise Exception("Not connected to WhatsApp")

        response = await self._api_client.send_message(
            to=channel_id,
            text=content,
            preview_url=preview_url,
        )

        msg_id = response.get("messages", [{}])[0].get("id", "")

        return ChatMessage(
            id=msg_id,
            content=content,
            author=MessageAuthor(
                id=self.phone_number_id,
                username="bot",
            ),
            channel_id=channel_id,
            timestamp=datetime.now(),
            platform="whatsapp",
        )

    async def send_interactive(
        self,
        recipient: str,
        message: Union[ButtonMessage, ListMessage],
    ) -> Dict[str, Any]:
        """
        Send an interactive message.

        Args:
            recipient: Recipient phone number
            message: Button or list message

        Returns:
            API response
        """
        return await self._api_client.send_interactive(
            to=recipient,
            interactive=message.to_dict(),
        )

    async def send_template(
        self,
        recipient: str,
        template: TemplateMessage,
    ) -> Dict[str, Any]:
        """
        Send a template message.

        Args:
            recipient: Recipient phone number
            template: Template message

        Returns:
            API response
        """
        return await self._api_client.send_template(
            to=recipient,
            template=template.to_dict(),
        )

    async def send_media(
        self,
        recipient: str,
        media_type: str,
        media_url: Optional[str] = None,
        media_id: Optional[str] = None,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a media message.

        Args:
            recipient: Recipient phone number
            media_type: Type (image, document, audio, video)
            media_url: URL of media (or use media_id)
            media_id: Previously uploaded media ID
            caption: Optional caption
            filename: Optional filename (for documents)

        Returns:
            API response
        """
        return await self._api_client.send_media(
            to=recipient,
            media_type=media_type,
            media_url=media_url,
            media_id=media_id,
            caption=caption,
            filename=filename,
        )

    async def get_media_url(self, media_id: str) -> str:
        """
        Get download URL for media.

        Args:
            media_id: Media ID from message

        Returns:
            Download URL
        """
        return await self._api_client.get_media_url(media_id)

    # =========================================================================
    # Event Handling
    # =========================================================================

    async def handle_webhook(self, payload: Dict[str, Any]) -> None:
        """
        Handle incoming webhook payload.

        Args:
            payload: Webhook payload
        """
        # Handle messages
        messages = self.parse_webhook(payload)
        for msg in messages:
            if self.on_message:
                await self.on_message(msg)

        # Handle status updates
        statuses = self.parse_status_updates(payload)
        for status in statuses:
            if self.on_status_update:
                await self.on_status_update(status)

    # =========================================================================
    # Gateway Integration
    # =========================================================================

    def create_gateway_request(self, message: ChatMessage) -> GatewayRequest:
        """
        Create GatewayRequest from ChatMessage.

        Args:
            message: Parsed ChatMessage

        Returns:
            GatewayRequest for ChatbotGateway
        """
        return GatewayRequest(
            message=message,
            platform="whatsapp",
            thread_id=None,  # WhatsApp doesn't have threads
            workspace_id=self.config.business_account_id,
        )


# =============================================================================
# API Client
# =============================================================================


class _WhatsAppAPIClient:
    """WhatsApp Cloud API client."""

    def __init__(self, config: WhatsAppConfig):
        self.config = config
        self.base_url = f"https://graph.facebook.com/{config.api_version}"

    async def send_message(
        self,
        to: str,
        text: str,
        preview_url: bool = False,
    ) -> Dict[str, Any]:
        """Send text message."""
        import aiohttp

        url = f"{self.base_url}/{self.config.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json()

    async def send_interactive(
        self,
        to: str,
        interactive: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send interactive message."""
        import aiohttp

        url = f"{self.base_url}/{self.config.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json()

    async def send_template(
        self,
        to: str,
        template: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send template message."""
        import aiohttp

        url = f"{self.base_url}/{self.config.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json()

    async def send_media(
        self,
        to: str,
        media_type: str,
        media_url: Optional[str] = None,
        media_id: Optional[str] = None,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send media message."""
        import aiohttp

        url = f"{self.base_url}/{self.config.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }

        media_content: Dict[str, Any] = {}
        if media_url:
            media_content["link"] = media_url
        elif media_id:
            media_content["id"] = media_id

        if caption:
            media_content["caption"] = caption
        if filename:
            media_content["filename"] = filename

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
            media_type: media_content,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json()

    async def get_media_url(self, media_id: str) -> str:
        """Get media download URL."""
        import aiohttp

        url = f"{self.base_url}/{media_id}"
        headers = {"Authorization": f"Bearer {self.config.access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                return data.get("url", "")


# =============================================================================
# Mock Client for Testing
# =============================================================================


class _MockWhatsAppClient:
    """Mock WhatsApp client for testing without aiohttp."""

    async def send_message(self, **kwargs) -> Dict[str, Any]:
        return {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": kwargs.get("to")}],
            "messages": [{"id": "wamid.mock"}],
        }

    async def send_interactive(self, **kwargs) -> Dict[str, Any]:
        return {"messages": [{"id": "wamid.interactive"}]}

    async def send_template(self, **kwargs) -> Dict[str, Any]:
        return {"messages": [{"id": "wamid.template"}]}

    async def send_media(self, **kwargs) -> Dict[str, Any]:
        return {"messages": [{"id": "wamid.media"}]}

    async def get_media_url(self, media_id: str) -> str:
        return f"https://lookaside.fbsbx.com/whatsapp/{media_id}"
