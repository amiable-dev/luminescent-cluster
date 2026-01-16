# Building Multi-Platform Chatbots: One Codebase, Four Platforms

**Discord, Slack, Telegram, and WhatsApp all have different APIs. Here's how we built a unified architecture that lets you deploy to all four from a single codebase.**

---

"Can we add a Slack bot?" "What about Discord?" "Our team uses Telegram." "The support team is on WhatsApp."

Every platform has its own API, authentication model, message format, and quirks. Building a chatbot for one platform is straightforward. Building for four platforms without creating four separate codebases? That's an architecture problem.

We solved it with **thin adapters** and a **central gateway**. Each platform adapter handles only platform-specific concerns (authentication, message parsing, sending). Everything else—access control, rate limiting, LLM orchestration, memory retrieval—lives in a shared gateway.

## The Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Platform Adapters                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ Discord  │  │  Slack   │  │ Telegram │  │ WhatsApp │                 │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │ Adapter  │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                 │
│       │             │             │             │                        │
│       └─────────────┴──────┬──────┴─────────────┘                        │
│                            │                                              │
│                            ▼                                              │
│               ┌────────────────────────────┐                             │
│               │     Central Gateway        │                             │
│               │  • Message normalization   │                             │
│               │  • Access control          │                             │
│               │  • Rate limiting           │                             │
│               │  • LLM orchestration       │                             │
│               │  • Context management      │                             │
│               └────────────┬───────────────┘                             │
│                            │                                              │
│               ┌────────────┴───────────────┐                             │
│               ▼                            ▼                             │
│  ┌─────────────────────┐    ┌─────────────────────────┐                 │
│  │  Session Memory     │    │  Pixeltable Memory      │                 │
│  │  MCP Server         │    │  MCP Server             │                 │
│  └─────────────────────┘    └─────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key principle:** Adapters are thin. They convert platform-specific messages to a common format and send responses back. All business logic lives in the gateway.

## Message Normalization

Every platform represents messages differently. Discord has guild IDs and role mentions. Slack has workspace IDs and Block Kit. Telegram has chat types and bot commands. WhatsApp has 24-hour windows and template messages.

We normalize everything to a common `ChatMessage` format:

```python
@dataclass
class ChatMessage:
    id: str                           # Platform message ID
    content: str                      # Normalized text content
    author: MessageAuthor             # Sender info (id, name, is_bot)
    channel_id: str                   # Conversation/channel ID
    timestamp: datetime               # When sent
    platform: str                     # "discord", "slack", "telegram", "whatsapp"
    thread_id: Optional[str]          # Thread context (if threaded)
    reply_to_id: Optional[str]        # Parent message (if reply)
    is_direct_message: bool           # DM vs channel message
    attachments: list[Attachment]     # Files, images, documents
    metadata: dict                    # Platform-specific extras
```

Platform-specific details go in `metadata`:
- **Discord**: `mentions`, `role_mentions`, guild info
- **Slack**: `blocks`, `channel_mentions`, broadcast flags
- **Telegram**: `is_command`, `command_args`, `hashtags`
- **WhatsApp**: `window_open`, `interactive_reply`, `location`

This lets the gateway work with a single message format while preserving platform-specific features when needed.

## Platform Adapters

Each adapter implements a common protocol:

```python
@runtime_checkable
class PlatformAdapter(Protocol):
    @property
    def platform(self) -> str: ...

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def send_message(
        self, channel_id: str, content: str, reply_to: Optional[str] = None
    ) -> ChatMessage: ...
```

Let's look at what each adapter handles.

### Discord Adapter

**Connection:** WebSocket via Discord Gateway (real-time events)

```python
from discord import Client, Intents

class DiscordAdapter:
    def __init__(self, config: DiscordConfig):
        intents = Intents.default()
        intents.message_content = True  # Required for reading messages
        self.client = Client(intents=intents)
        self.config = config

    async def connect(self):
        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return  # Ignore own messages
            chat_msg = self.parse_message(message)
            await self.gateway.process(chat_msg)

        await self.client.start(self.config.token)
```

**Key features:**
- Intent-based filtering (what events to receive)
- Thread support via channel type detection
- Slash command registration
- Message splitting for 2000-char limit

**Configuration:**
```python
@dataclass
class DiscordConfig:
    token: str                    # Bot token from Discord Developer Portal
    application_id: str           # For slash commands
    guild_id: Optional[str]       # Guild-specific commands (faster registration)
```

### Slack Adapter

**Connection:** Socket Mode WebSocket (recommended) or Web API

```python
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

class SlackAdapter:
    def __init__(self, config: SlackConfig):
        self.app = AsyncApp(token=config.bot_token)
        self.handler = AsyncSocketModeHandler(self.app, config.app_token)

    async def connect(self):
        @self.app.message()
        async def handle_message(message, say):
            chat_msg = self.parse_message(message)
            response = await self.gateway.process(chat_msg)
            if response:
                await say(response.content, thread_ts=message.get("thread_ts"))

        await self.handler.start_async()
```

**Key features:**
- Socket Mode (no public webhook needed)
- Thread timestamp tracking (`thread_ts`)
- Ephemeral messages (visible only to one user)
- Block Kit for rich formatting

**Configuration:**
```python
@dataclass
class SlackConfig:
    bot_token: str              # xoxb-... token
    app_token: str              # xapp-... token (for Socket Mode)
    signing_secret: str         # Webhook verification
```

### Telegram Adapter

**Connection:** Long polling (default) or Webhook

```python
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

class TelegramAdapter:
    def __init__(self, config: TelegramConfig):
        self.app = Application.builder().token(config.bot_token).build()

    async def connect(self):
        async def handle_message(update: Update, context):
            chat_msg = self.parse_message(update.message)
            response = await self.gateway.process(chat_msg)
            if response:
                await update.message.reply_text(response.content)

        self.app.add_handler(MessageHandler(filters.TEXT, handle_message))

        if self.config.use_webhook:
            await self.app.run_webhook(url=self.config.webhook_url)
        else:
            await self.app.run_polling()
```

**Key features:**
- Bot command parsing (`/command args`)
- Inline queries (typeahead search)
- Inline keyboards with callback buttons
- Entity extraction (mentions, URLs, hashtags)

**Configuration:**
```python
@dataclass
class TelegramConfig:
    bot_token: str              # Token from @BotFather
    webhook_url: Optional[str]  # For webhook mode
    use_webhook: bool = False   # True = webhook, False = polling
```

### WhatsApp Adapter

**Connection:** Cloud API via webhooks (no persistent connection)

```python
import httpx

class WhatsAppAdapter:
    def __init__(self, config: WhatsAppConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        self._conversation_windows: dict[str, datetime] = {}

    async def send_message(self, to: str, content: str) -> ChatMessage:
        # Check 24-hour window
        if not self.is_window_open(to):
            raise WindowClosedError("Must use template message outside 24h window")

        response = await self.client.post(
            f"https://graph.facebook.com/{self.config.api_version}/"
            f"{self.config.phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self.config.access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": content},
            },
        )
        return self._parse_response(response.json())
```

**Key features:**
- 24-hour customer service window tracking
- Template messages (for marketing/notifications)
- Interactive messages (buttons, lists)
- Webhook signature verification (HMAC-SHA256)

**Configuration:**
```python
@dataclass
class WhatsAppConfig:
    access_token: str           # Meta Graph API token
    phone_number_id: str        # WhatsApp Business phone ID
    app_secret: str             # For webhook signature verification
    api_version: str = "v18.0"
```

**The 24-hour window:** WhatsApp restricts when businesses can message users. You can only send free-form messages within 24 hours of the user's last message. Outside that window, you must use pre-approved template messages.

```python
def is_window_open(self, user_id: str) -> bool:
    """Check if we can send free-form messages to this user."""
    last_msg = self._conversation_windows.get(user_id)
    if not last_msg:
        return False
    return (datetime.utcnow() - last_msg) < timedelta(hours=24)
```

## The Central Gateway

The gateway handles everything that's platform-agnostic:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Gateway Processing Flow                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Incoming Message                                               │
│         │                                                        │
│         ▼                                                        │
│   ┌─────────────┐   No    ┌───────────┐                         │
│   │ Should      ├────────►│ Ignore    │                         │
│   │ Respond?    │         └───────────┘                         │
│   └──────┬──────┘                                               │
│          │ Yes                                                   │
│          ▼                                                        │
│   ┌─────────────┐   No    ┌───────────┐                         │
│   │ Access      ├────────►│ Silent    │                         │
│   │ Allowed?    │         │ Deny      │                         │
│   └──────┬──────┘         └───────────┘                         │
│          │ Yes                                                   │
│          ▼                                                        │
│   ┌─────────────┐   No    ┌───────────┐                         │
│   │ Rate Limit  ├────────►│ Return    │                         │
│   │ OK?         │         │ 429       │                         │
│   └──────┬──────┘         └───────────┘                         │
│          │ Yes                                                   │
│          ▼                                                        │
│   ┌─────────────┐                                               │
│   │ Get Thread  │                                               │
│   │ Context     │◄─────── Session Memory MCP                    │
│   └──────┬──────┘                                               │
│          │                                                       │
│          ▼                                                        │
│   ┌─────────────┐                                               │
│   │ LLM Call    │◄─────── Pixeltable Memory MCP (tools)         │
│   │ + MCP Tools │                                               │
│   └──────┬──────┘                                               │
│          │                                                       │
│          ▼                                                        │
│   ┌─────────────┐                                               │
│   │ Save        │                                               │
│   │ Context     │                                               │
│   └──────┬──────┘                                               │
│          │                                                       │
│          ▼                                                        │
│   Response to Adapter                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

```python
class ChatbotGateway:
    def __init__(
        self,
        llm_provider: LLMProvider,
        context_manager: ContextManager,
        rate_limiter: RateLimiter,
        access_controller: Optional[AccessController] = None,
    ):
        self.llm = llm_provider
        self.context = context_manager
        self.rate_limiter = rate_limiter
        self.access_controller = access_controller

    async def process(self, message: ChatMessage) -> Optional[GatewayResponse]:
        # 1. Should we respond?
        if not self.invocation_policy.should_respond(message):
            return None

        # 2. Access control (fail-closed)
        if self.access_controller:
            allowed, reason = self.access_controller.check_access(
                user_id=message.author.id,
                channel_id=message.channel_id,
            )
            if not allowed:
                return None  # Silent denial

        # 3. Rate limiting
        rate_result = self.rate_limiter.check(
            user_id=message.author.id,
            channel_id=message.channel_id,
        )
        if not rate_result.allowed:
            return GatewayResponse(
                content=f"Rate limit exceeded. Try again in {rate_result.retry_after}s.",
                error="rate_limited",
            )

        # 4. Get thread context
        context = await self.context.get_thread_context(message.thread_id)

        # 5. Call LLM with MCP tools
        response = await self.llm.complete(
            messages=context + [{"role": "user", "content": message.content}],
            tools=self.mcp_tools,
        )

        # 6. Save context
        await self.context.append(message.thread_id, message, response)

        return GatewayResponse(content=response.content)
```

### Invocation Policy

When should the bot respond? Not every message.

```python
@dataclass
class InvocationPolicy:
    """Determines when bot should respond."""
    enabled_triggers: list[InvocationType] = field(default_factory=lambda: [
        InvocationType.MENTION,        # @bot
        InvocationType.DIRECT_MESSAGE, # DMs
    ])
    bot_user_id: Optional[str] = None
    command_prefix: Optional[str] = None  # e.g., "!ask"
    ignore_bots: bool = True

    def should_respond(self, message: ChatMessage) -> bool:
        if self.ignore_bots and message.author.is_bot:
            return False

        if message.is_direct_message:
            return InvocationType.DIRECT_MESSAGE in self.enabled_triggers

        if InvocationType.MENTION in self.enabled_triggers:
            if self.bot_user_id and f"<@{self.bot_user_id}>" in message.content:
                return True

        if self.command_prefix and message.content.startswith(self.command_prefix):
            return True

        return False
```

**Why explicit invocation?** Passive listening (responding to every message) causes problems:
- Ingests sarcasm and jokes as facts
- Responds when not wanted (annoying)
- Burns through rate limits
- Creates trust issues ("is it always watching?")

### Rate Limiting

Three-level token bucket: per-user, per-channel, per-workspace.

```python
class RateLimiter:
    def __init__(self, config: RateLimitConfig):
        self.user_buckets: dict[str, TokenBucket] = {}
        self.channel_buckets: dict[str, TokenBucket] = {}
        self.workspace_buckets: dict[str, TokenBucket] = {}
        self.config = config

    def check(
        self, user_id: str, channel_id: str, workspace_id: Optional[str] = None
    ) -> RateLimitResult:
        # All three must allow
        user_ok = self._check_bucket(self.user_buckets, user_id, self.config.user_rpm)
        channel_ok = self._check_bucket(self.channel_buckets, channel_id, self.config.channel_rpm)
        workspace_ok = True
        if workspace_id:
            workspace_ok = self._check_bucket(
                self.workspace_buckets, workspace_id, self.config.workspace_rpm
            )

        allowed = user_ok and channel_ok and workspace_ok
        return RateLimitResult(allowed=allowed, ...)
```

**Default limits:**

| Level | Limit | Rationale |
|-------|-------|-----------|
| Per user | 5/min | Prevent individual abuse |
| Per channel | 20/min | Prevent channel flooding |
| Per workspace | 100/min | Prevent workspace DoS |

### Access Control

Three policies for different deployment modes:

```python
# 1. OSS default: Allow everything
class DefaultAccessControlPolicy:
    def check_access(self, user_id, channel_id, workspace_id):
        return True, None

# 2. Self-hosted: Configurable allow/block lists
class ConfigurableAccessControlPolicy:
    def __init__(self, allowed_channels=None, blocked_channels=None):
        self.allowed = set(allowed_channels or [])
        self.blocked = set(blocked_channels or [])

    def check_access(self, user_id, channel_id, workspace_id):
        if channel_id in self.blocked:
            return False, "Channel blocked"
        if self.allowed and channel_id not in self.allowed:
            return False, "Channel not in allowlist"
        return True, None

# 3. Response filtering: Redact secrets in public channels
class ResponseFilterPolicy:
    PATTERNS = [
        r"password[\"']?\s*[:=]\s*[\"'][^\"']+",
        r"api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']+",
        r"bearer\s+[a-zA-Z0-9\-_.]+",
    ]

    def filter_response(self, response: str, channel: ChannelContext) -> str:
        if not channel.is_public:
            return response
        for pattern in self.PATTERNS:
            if re.search(pattern, response, re.I):
                return "I found relevant information but it may contain sensitive data. Please ask in a private channel."
        return response
```

### Context Management

Thread context is bounded to prevent token overflow:

```python
@dataclass
class ContextConfig:
    max_messages: int = 10      # Sliding window
    max_tokens: int = 2000      # Token budget
    ttl_hours: int = 24         # Context expires

class ContextManager:
    async def get_thread_context(self, thread_id: str) -> list[dict]:
        context = await self.store.get(thread_id)
        if not context:
            return []

        # Apply TTL
        if context.last_activity < datetime.utcnow() - timedelta(hours=self.config.ttl_hours):
            await self.store.delete(thread_id)
            return []

        # Truncate to limits
        messages = context.messages[-self.config.max_messages:]
        return self._truncate_to_token_limit(messages)
```

**Context window budget (4K model):**
```
System prompt:     ~200 tokens
Thread context:    ~1000 tokens (bounded)
Retrieved memory:  ~2000 tokens (from MCP)
User query:        ~200 tokens
Response buffer:   ~600 tokens
                   ────────────
                   4000 tokens
```

## Rendering Strategy

Platforms format messages differently. Discord understands Markdown. Slack wants Block Kit. Telegram supports a subset of HTML. WhatsApp handles basic formatting.

**The problem:** Your LLM generates Markdown. Now what?

```
┌─────────────────────────────────────────────────────────────────┐
│                     Rendering Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   LLM Response (Markdown)                                        │
│         │                                                        │
│         ▼                                                        │
│   ┌─────────────────┐                                           │
│   │ Response Renderer│                                           │
│   └────────┬────────┘                                           │
│            │                                                     │
│   ┌────────┼────────┬──────────────┬──────────────┐             │
│   ▼        ▼        ▼              ▼              ▼             │
│ Discord  Slack   Telegram      WhatsApp      Fallback          │
│ (pass-   (Block  (HTML         (Bold/        (Plain            │
│ through) Kit)    subset)       Italic)       text)             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

```python
class ResponseRenderer:
    """Transform LLM Markdown output for each platform."""

    def render(self, content: str, platform: str) -> str | dict:
        match platform:
            case "discord":
                # Discord natively supports Markdown
                return content

            case "slack":
                # Convert to Block Kit for rich formatting
                return self._to_slack_blocks(content)

            case "telegram":
                # Convert to Telegram's HTML subset
                return self._to_telegram_html(content)

            case "whatsapp":
                # WhatsApp supports *bold* and _italic_ only
                return self._to_whatsapp_format(content)

            case _:
                # Fallback: strip all formatting
                return self._strip_formatting(content)

    def _to_slack_blocks(self, markdown: str) -> dict:
        """Convert Markdown to Slack Block Kit."""
        blocks = []

        for block in self._parse_markdown_blocks(markdown):
            if block.type == "code":
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{block.content}```"}
                })
            elif block.type == "heading":
                blocks.append({
                    "type": "header",
                    "text": {"type": "plain_text", "text": block.content}
                })
            else:
                # Slack mrkdwn: *bold*, _italic_, ~strike~
                text = block.content.replace("**", "*").replace("~~", "~")
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text}
                })

        return {"blocks": blocks}

    def _to_telegram_html(self, markdown: str) -> str:
        """Convert Markdown to Telegram HTML."""
        html = markdown
        # Bold: **text** -> <b>text</b>
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        # Italic: *text* -> <i>text</i>
        html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)
        # Code: `text` -> <code>text</code>
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
        # Code block: ```text``` -> <pre>text</pre>
        html = re.sub(r'```(.+?)```', r'<pre>\1</pre>', html, flags=re.DOTALL)
        return html
```

**Rendering gotcha:** Slack's Block Kit has a 3000-character limit per text block. Long LLM responses need splitting:

```python
def _split_for_slack(self, text: str, max_len: int = 2900) -> list[str]:
    """Split text at sentence boundaries for Block Kit limits."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if len(current) + len(sentence) > max_len:
            chunks.append(current.strip())
            current = sentence
        else:
            current += " " + sentence
    if current:
        chunks.append(current.strip())
    return chunks
```

## Persistence Layer

Thread context needs storage. The choice depends on your deployment:

| Storage | Use Case | Tradeoffs |
|---------|----------|-----------|
| In-memory dict | Development, single instance | Lost on restart, no scaling |
| Redis | Production, multi-instance | Requires Redis, adds latency |
| SQLite | Single-server production | Simple, persistent, no scaling |

```python
from abc import ABC, abstractmethod

class ContextStore(ABC):
    @abstractmethod
    async def get(self, thread_id: str) -> Optional[ThreadContext]: ...

    @abstractmethod
    async def set(self, thread_id: str, context: ThreadContext) -> None: ...

    @abstractmethod
    async def delete(self, thread_id: str) -> None: ...


class InMemoryContextStore(ContextStore):
    """Development only. Context lost on restart."""

    def __init__(self):
        self._store: dict[str, ThreadContext] = {}

    async def get(self, thread_id: str) -> Optional[ThreadContext]:
        return self._store.get(thread_id)

    async def set(self, thread_id: str, context: ThreadContext) -> None:
        self._store[thread_id] = context

    async def delete(self, thread_id: str) -> None:
        self._store.pop(thread_id, None)


class RedisContextStore(ContextStore):
    """Production. Scales horizontally, survives restarts."""

    def __init__(self, redis_url: str, ttl_seconds: int = 86400):
        self.redis = redis.from_url(redis_url)
        self.ttl = ttl_seconds

    async def get(self, thread_id: str) -> Optional[ThreadContext]:
        data = await self.redis.get(f"ctx:{thread_id}")
        if not data:
            return None
        return ThreadContext.from_json(data)

    async def set(self, thread_id: str, context: ThreadContext) -> None:
        await self.redis.setex(
            f"ctx:{thread_id}",
            self.ttl,
            context.to_json()
        )

    async def delete(self, thread_id: str) -> None:
        await self.redis.delete(f"ctx:{thread_id}")
```

**Key decision:** Set appropriate TTLs. Stale context wastes memory; short TTLs lose continuity.

| Context Type | Recommended TTL |
|--------------|-----------------|
| Thread context | 24 hours |
| WhatsApp window | 24 hours (mandated) |
| User preferences | 7 days |
| Rate limit buckets | 1 minute |

## Security & Idempotency

Webhooks from platforms are unauthenticated HTTP requests. Verify them.

### Webhook Signature Verification

```python
import hmac
import hashlib

class WebhookVerifier:
    """Verify webhook signatures from platforms."""

    @staticmethod
    def verify_slack(
        body: bytes,
        timestamp: str,
        signature: str,
        signing_secret: str
    ) -> bool:
        """Verify Slack request signature (v0 scheme)."""
        base = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac.new(
            signing_secret.encode(),
            base.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_whatsapp(
        body: bytes,
        signature: str,
        app_secret: str
    ) -> bool:
        """Verify WhatsApp webhook signature (HMAC-SHA256)."""
        expected = hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        # WhatsApp sends signature as "sha256=..."
        received = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, received)

    @staticmethod
    def verify_telegram(update: dict, bot_token: str) -> bool:
        """Telegram doesn't sign webhooks. Use secret_token instead."""
        # Set secret_token when configuring webhook
        # Telegram will include it in X-Telegram-Bot-Api-Secret-Token header
        return True  # Verify via header in middleware
```

### Idempotency: Prevent Duplicate Processing

Webhooks can be retried. Message events can arrive twice. Handle it.

```python
class IdempotencyGuard:
    """Prevent duplicate message processing."""

    def __init__(self, store: redis.Redis, ttl_seconds: int = 300):
        self.store = store
        self.ttl = ttl_seconds

    async def is_duplicate(self, message_id: str, platform: str) -> bool:
        """Check if we've already processed this message."""
        key = f"idem:{platform}:{message_id}"
        # SETNX returns True if key was set (first time), False if exists
        is_new = await self.store.setnx(key, "1")
        if is_new:
            await self.store.expire(key, self.ttl)
        return not is_new

# Usage in gateway
async def process(self, message: ChatMessage) -> Optional[GatewayResponse]:
    # Check idempotency first
    if await self.idempotency.is_duplicate(message.id, message.platform):
        logger.debug(f"Duplicate message {message.id}, skipping")
        return None

    # ... rest of processing
```

**Why 5 minutes TTL?** Long enough to catch retries, short enough not to bloat Redis. Platform retry policies:
- Slack: Retries for up to 30 minutes
- WhatsApp: Retries for 24 hours (but with backoff)
- Telegram: Single delivery, no retries

## Quick Start

### Discord

```python
from src.chatbot import DiscordAdapter, DiscordConfig, ChatbotGateway

# Configure
config = DiscordConfig(
    token="your-bot-token",
    application_id="your-app-id",
)

# Create adapter and gateway
adapter = DiscordAdapter(config)
gateway = ChatbotGateway(llm_provider=my_llm, ...)
adapter.set_gateway(gateway)

# Run
await adapter.connect()
```

### Slack

```python
from src.chatbot import SlackAdapter, SlackConfig

config = SlackConfig(
    bot_token="xoxb-...",
    app_token="xapp-...",  # For Socket Mode
    signing_secret="...",
)

adapter = SlackAdapter(config)
adapter.set_gateway(gateway)
await adapter.connect()
```

### Telegram

```python
from src.chatbot import TelegramAdapter, TelegramConfig

config = TelegramConfig(
    bot_token="123456:ABC-DEF...",  # From @BotFather
    use_webhook=False,  # Use polling for development
)

adapter = TelegramAdapter(config)
adapter.set_gateway(gateway)
await adapter.connect()
```

### WhatsApp

```python
from src.chatbot import WhatsAppAdapter, WhatsAppConfig

config = WhatsAppConfig(
    access_token="your-graph-api-token",
    phone_number_id="your-phone-number-id",
    app_secret="your-app-secret",  # For webhook verification
)

adapter = WhatsAppAdapter(config)
adapter.set_gateway(gateway)
# WhatsApp uses webhooks - set up your endpoint to call adapter.handle_webhook()
```

## Running Multiple Platforms

**The concurrency challenge:** Discord and Telegram use persistent WebSocket connections. Slack Socket Mode does too. But WhatsApp uses webhooks (inbound HTTP requests). Mixing these in one process requires care.

```python
import asyncio
from aiohttp import web

async def main():
    # Shared gateway
    gateway = ChatbotGateway(
        llm_provider=OpenAIProvider(api_key="..."),
        context_manager=ContextManager(store=RedisContextStore(redis_url)),
        rate_limiter=RateLimiter(RateLimitConfig()),
    )

    # WebSocket-based adapters
    discord = DiscordAdapter(discord_config)
    slack = SlackAdapter(slack_config)
    telegram = TelegramAdapter(telegram_config)

    discord.set_gateway(gateway)
    slack.set_gateway(gateway)
    telegram.set_gateway(gateway)

    # Webhook-based adapters need an HTTP server
    whatsapp = WhatsAppAdapter(whatsapp_config)
    whatsapp.set_gateway(gateway)

    # Create webhook server
    app = web.Application()
    app.router.add_post("/webhook/whatsapp", whatsapp.handle_webhook)

    # Run everything
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)

    await asyncio.gather(
        discord.connect(),      # WebSocket
        slack.connect(),        # WebSocket (Socket Mode)
        telegram.connect(),     # Long polling or webhook
        site.start(),           # HTTP server for WhatsApp webhooks
    )

asyncio.run(main())
```

**Architecture options:**

| Approach | Pros | Cons |
|----------|------|------|
| Single process (above) | Simple, shared state | WebSocket reconnects block webhooks |
| Separate processes | Isolated failures | Need message queue for coordination |
| Kubernetes pods | Production-ready | Operational complexity |

**Recommendation:** Start with single process for development. Split when you need:
- Independent scaling (Slack usage >> Discord)
- Fault isolation (WhatsApp outage shouldn't affect Discord)
- Different deployment regions
```

## Platform Comparison

| Feature | Discord | Slack | Telegram | WhatsApp |
|---------|---------|-------|----------|----------|
| Connection | WebSocket | Socket Mode / API | Polling / Webhook | Webhook only |
| Threading | Native threads | `thread_ts` | Reply chains | None |
| Rich formatting | Embeds | Block Kit | Markdown | Limited |
| Buttons | Components | Block Kit | Inline keyboards | Interactive (3 max) |
| File sharing | Attachments | Files API | Documents | Media messages |
| Message limit | 2000 chars | 40000 chars | 4096 chars | 4096 chars |
| Rate limits | 50/sec | Varies by tier | 30/sec | Varies |
| Special constraints | None | App review | None | 24h window |

## Platform Gotchas

Each platform has unique constraints that can bite you in production.

### Slack: The 3-Second Rule

Slack expects webhook acknowledgment within 3 seconds. If your LLM takes longer (it will), Slack retries the request. Result: duplicate responses.

**Solution:** Acknowledge immediately, process asynchronously.

```python
@self.app.message()
async def handle_message(message, say, ack):
    # Acknowledge IMMEDIATELY (within 3 seconds)
    await ack()

    # Process in background
    asyncio.create_task(self._process_async(message, say))

async def _process_async(self, message, say):
    # LLM processing can take 5-30 seconds
    chat_msg = self.parse_message(message)
    response = await self.gateway.process(chat_msg)
    if response:
        await say(response.content, thread_ts=message.get("thread_ts"))
```

### WhatsApp: Template Messages

Outside the 24-hour customer service window, you can only send pre-approved template messages. Templates have:
- Fixed structure with variable placeholders
- Business approval process (takes days)
- Per-message costs

```python
async def send_template_message(
    self, to: str, template_name: str, variables: list[str]
) -> ChatMessage:
    """Send a pre-approved template message."""
    response = await self.client.post(
        f"https://graph.facebook.com/{self.config.api_version}/"
        f"{self.config.phone_number_id}/messages",
        headers={"Authorization": f"Bearer {self.config.access_token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"},
                "components": [{
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": v} for v in variables
                    ]
                }]
            }
        },
    )
    return self._parse_response(response.json())

# Usage: Re-engage after window closes
if not self.is_window_open(user_id):
    await self.send_template_message(
        to=user_id,
        template_name="conversation_followup",
        variables=["We have an update on your question!"]
    )
```

### Discord: Intent Requirements

Discord requires explicit intents for certain data. Missing intents = silent failures.

| Intent | Required For |
|--------|--------------|
| `message_content` | Reading message text |
| `guild_members` | User info beyond basic |
| `presences` | Online/offline status |

**Gotcha:** `message_content` requires verification for bots in 100+ servers.

```python
intents = Intents.default()
intents.message_content = True  # Won't work without verification at scale
```

### Telegram: Command Conflicts

Telegram bot commands (`/start`, `/help`) are global. If your bot uses common names, users get confused.

**Solution:** Register commands via BotFather with descriptions:

```python
await self.app.bot.set_my_commands([
    BotCommand("ask", "Ask the AI a question"),
    BotCommand("context", "Show current conversation context"),
    BotCommand("clear", "Clear conversation history"),
])
```

### Rate Limit Differences

Each platform has different rate limits and behaviors:

| Platform | Global Limit | Per-User | Behavior When Exceeded |
|----------|--------------|----------|------------------------|
| Discord | 50 req/sec | None | HTTP 429 + retry-after |
| Slack | Varies by tier | None | HTTP 429 + retry-after |
| Telegram | 30 msg/sec | 1 msg/sec to same chat | HTTP 429, may ban bot |
| WhatsApp | 80 msg/sec | Conversation-based | HTTP 429 + backoff |

**Telegram is strict:** Exceeding limits can get your bot temporarily banned. Always implement backoff.

```python
async def send_with_backoff(self, chat_id: str, text: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await self.app.bot.send_message(chat_id=chat_id, text=text)
        except RetryAfter as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(e.retry_after)
            else:
                raise
```

## What We Learned

**1. Thin adapters win.** When Telegram changed their bot API, we updated one file. The gateway didn't change.

**2. Normalize early.** Converting to `ChatMessage` at the adapter boundary keeps the gateway simple. Platform quirks stay contained.

**3. Explicit invocation is essential.** Passive listening sounded cool until we realized the bot was responding to sarcastic comments and storing jokes as facts.

**4. Rate limiting needs three levels.** Per-user alone isn't enough—one power user in a popular channel can DoS the whole workspace.

**5. WhatsApp is different.** The 24-hour window rule fundamentally changes how you design conversations. Plan for it early.

**6. Context windows fill fast.** Thread context + retrieved memory + system prompt leaves surprisingly little room for the actual response.

**7. Rendering is platform-specific.** Your LLM outputs Markdown. Slack wants Block Kit. Plan for transformation.

**8. Persistence matters early.** In-memory context works for demos. Production needs Redis (or similar) for restarts and scaling.

**9. Idempotency prevents duplicates.** Webhooks retry. Socket connections reconnect. Without deduplication, users get double responses.

**10. Acknowledge fast, process slow.** Slack's 3-second timeout taught us: acknowledge receipt immediately, then process asynchronously.

---

*Multi-platform chatbots are part of ADR-006. See the [full ADR](../adrs/ADR-006-chatbot-platform-integrations.md) for architecture decisions and compliance considerations.*
