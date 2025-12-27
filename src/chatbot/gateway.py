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
ChatbotGateway - Central message routing for Luminescent Cluster chatbot.

This module provides the main gateway for processing chat messages across
platforms, integrating with LLM providers, context management, rate limiting,
and MCP servers.

Design (from ADR-006):
- Platform-agnostic message processing
- Configurable invocation policies (mention, DM, prefix)
- Context-aware conversations
- Rate limiting per user/channel/workspace
- MCP integration for knowledge retrieval

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Any
import re
import logging

from src.chatbot.adapters.base import ChatMessage
from src.chatbot.context import ThreadContextManager, ContextConfig
from src.chatbot.rate_limiter import TokenBucketRateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Invocation Policy
# =============================================================================


class InvocationType(Enum):
    """Types of message invocation that trigger bot response."""

    MENTION = auto()  # Bot is mentioned (@bot)
    DIRECT_MESSAGE = auto()  # Direct/private message to bot
    PREFIX = auto()  # Message starts with prefix (!ask)
    ALWAYS = auto()  # Always respond (for dedicated channels)


@dataclass
class InvocationPolicy:
    """
    Policy for when the bot should respond to messages.

    Attributes:
        enabled_types: List of invocation types to respond to
        bot_user_id: Bot's user ID for mention detection
        prefix: Prefix for prefix-based invocation
        mention_patterns: Custom patterns to detect mentions
        ignore_bots: Whether to ignore messages from other bots
    """

    enabled_types: List[InvocationType] = field(
        default_factory=lambda: [InvocationType.MENTION, InvocationType.DIRECT_MESSAGE]
    )
    bot_user_id: Optional[str] = None
    prefix: Optional[str] = None
    mention_patterns: List[str] = field(default_factory=list)
    ignore_bots: bool = True

    def should_respond(self, message: ChatMessage) -> bool:
        """
        Check if bot should respond to this message.

        Args:
            message: The incoming chat message

        Returns:
            True if bot should respond
        """
        # Ignore bot messages if configured
        if self.ignore_bots and message.author.is_bot:
            return False

        # Check each enabled invocation type
        for inv_type in self.enabled_types:
            if inv_type == InvocationType.ALWAYS:
                return True

            if inv_type == InvocationType.DIRECT_MESSAGE:
                if message.is_direct_message:
                    return True

            if inv_type == InvocationType.MENTION:
                if self._is_mentioned(message):
                    return True

            if inv_type == InvocationType.PREFIX:
                if self._has_prefix(message):
                    return True

        return False

    def _is_mentioned(self, message: ChatMessage) -> bool:
        """Check if bot is mentioned in message."""
        content = message.content

        # Check bot user ID mention
        if self.bot_user_id:
            # Discord format: <@BOT_ID> or <@!BOT_ID>
            if f"<@{self.bot_user_id}>" in content:
                return True
            if f"<@!{self.bot_user_id}>" in content:
                return True

        # Check custom mention patterns
        for pattern in self.mention_patterns:
            if pattern in content:
                return True

        return False

    def _has_prefix(self, message: ChatMessage) -> bool:
        """Check if message starts with prefix."""
        if not self.prefix:
            return False
        return message.content.strip().startswith(self.prefix)

    def extract_content(self, message: ChatMessage) -> str:
        """
        Extract the actual content from message, removing invocation trigger.

        Args:
            message: The incoming chat message

        Returns:
            Cleaned message content
        """
        content = message.content.strip()

        # Remove mention
        if self.bot_user_id:
            # Remove Discord-style mentions
            content = re.sub(rf"<@!?{re.escape(self.bot_user_id)}>\s*", "", content)

        # Remove custom mention patterns
        for pattern in self.mention_patterns:
            content = content.replace(pattern, "").strip()

        # Remove prefix
        if self.prefix and content.startswith(self.prefix):
            content = content[len(self.prefix):].strip()

        return content.strip()


# =============================================================================
# Gateway Configuration and Models
# =============================================================================


@dataclass
class GatewayConfig:
    """
    Configuration for ChatbotGateway.

    Attributes:
        default_model: Default LLM model to use
        max_response_tokens: Maximum tokens in response
        system_prompt: Default system prompt for LLM
        enable_context: Enable conversation context
        enable_rate_limiting: Enable rate limiting
        enable_mcp: Enable MCP integration
    """

    default_model: str = "gpt-4o-mini"
    max_response_tokens: int = 2048
    system_prompt: str = "You are a helpful assistant."
    enable_context: bool = True
    enable_rate_limiting: bool = True
    enable_mcp: bool = False


@dataclass
class GatewayRequest:
    """
    Request to the ChatbotGateway.

    Attributes:
        message: The incoming chat message
        platform: Platform name (discord, slack, etc.)
        thread_id: Optional thread/conversation ID
        workspace_id: Optional workspace/guild ID
        tenant_id: Optional tenant ID for multi-tenancy
        system_prompt: Optional override for system prompt
        use_mcp: Whether to use MCP for this request
    """

    message: ChatMessage
    platform: str
    thread_id: Optional[str] = None
    workspace_id: Optional[str] = None
    tenant_id: Optional[str] = None
    system_prompt: Optional[str] = None
    use_mcp: bool = False


@dataclass
class GatewayResponse:
    """
    Response from the ChatbotGateway.

    Attributes:
        content: Response text content
        tokens_used: Total tokens used
        model: Model that generated response
        latency_ms: Processing latency in milliseconds
        metadata: Additional metadata
        error: Error message if processing failed
    """

    content: str
    tokens_used: int
    model: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# =============================================================================
# ChatbotGateway Implementation
# =============================================================================


class ChatbotGateway:
    """
    Central gateway for processing chat messages.

    The gateway handles:
    - Message routing based on invocation policy
    - Context management for conversations
    - Rate limiting per user/channel/workspace
    - LLM provider integration
    - MCP server integration (optional)

    Example:
        config = GatewayConfig(system_prompt="You are a coding assistant.")
        gateway = ChatbotGateway(config)

        request = GatewayRequest(
            message=message,
            platform="discord",
            thread_id="thread-123",
        )
        response = await gateway.process(request)
        print(response.content)
    """

    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        invocation_policy: Optional[InvocationPolicy] = None,
    ):
        """
        Initialize the ChatbotGateway.

        Args:
            config: Gateway configuration
            invocation_policy: Message invocation policy
        """
        self.config = config or GatewayConfig()
        self.invocation_policy = invocation_policy or InvocationPolicy()

        # Components (can be injected)
        self.llm_provider = None
        self.context_manager: Optional[ThreadContextManager] = None
        self.rate_limiter: Optional[TokenBucketRateLimiter] = None
        self.mcp_client = None
        self.mcp_enabled = self.config.enable_mcp

        # Initialize context manager if enabled
        if self.config.enable_context:
            self.context_manager = ThreadContextManager()

        # Initialize rate limiter if enabled
        if self.config.enable_rate_limiting:
            self.rate_limiter = TokenBucketRateLimiter()

    async def process(self, request: GatewayRequest) -> Optional[GatewayResponse]:
        """
        Process an incoming chat message.

        Args:
            request: The gateway request

        Returns:
            GatewayResponse if bot should respond, None otherwise
        """
        import time
        start_time = time.time()

        message = request.message

        # Check if we should respond
        if not self.invocation_policy.should_respond(message):
            return None

        # Check rate limits
        if self.rate_limiter:
            rate_result = self.rate_limiter.check(
                user_id=message.author.id,
                channel_id=message.channel_id,
                workspace_id=request.workspace_id,
            )
            if not rate_result.allowed:
                return GatewayResponse(
                    content=f"Rate limit exceeded. Please try again later. {rate_result.reason}",
                    tokens_used=0,
                    error="rate_limit_exceeded",
                )

        # Extract actual content
        content = self.invocation_policy.extract_content(message)

        # Get thread ID for context
        thread_id = request.thread_id or message.thread_id or message.id

        # Build message list for LLM
        messages = self._build_messages(
            content=content,
            thread_id=thread_id,
            channel_id=message.channel_id,
            system_prompt=request.system_prompt,
        )

        # Query MCP if enabled and requested
        if self.mcp_enabled and request.use_mcp and self.mcp_client:
            try:
                mcp_results = await self.mcp_client.query(content)
                if mcp_results and mcp_results.get("results"):
                    # Add MCP context to messages
                    mcp_context = self._format_mcp_context(mcp_results)
                    messages = self._inject_mcp_context(messages, mcp_context)
            except Exception as e:
                logger.warning(f"MCP query failed: {e}")

        # Call LLM
        try:
            llm_response = await self.llm_provider.chat(
                messages=messages,
                max_tokens=self.config.max_response_tokens,
            )

            # Record usage
            if self.rate_limiter:
                self.rate_limiter.record(
                    user_id=message.author.id,
                    tokens_used=llm_response.tokens_used,
                    channel_id=message.channel_id,
                    workspace_id=request.workspace_id,
                )

            # Update context with both user message and response
            if self.context_manager and self.config.enable_context:
                self.context_manager.add_message(
                    thread_id=thread_id,
                    role="user",
                    content=content,
                    message_id=message.id,
                )
                self.context_manager.add_message(
                    thread_id=thread_id,
                    role="assistant",
                    content=llm_response.content,
                )

            latency_ms = (time.time() - start_time) * 1000

            return GatewayResponse(
                content=llm_response.content,
                tokens_used=llm_response.tokens_used,
                model=llm_response.model,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return GatewayResponse(
                content="I'm sorry, I encountered an error processing your request.",
                tokens_used=0,
                error=str(e),
            )

    def _build_messages(
        self,
        content: str,
        thread_id: str,
        channel_id: str,
        system_prompt: Optional[str] = None,
    ) -> List[dict[str, str]]:
        """
        Build message list for LLM call.

        Args:
            content: User message content
            thread_id: Thread ID for context
            channel_id: Channel ID
            system_prompt: Optional system prompt override

        Returns:
            List of message dicts for LLM
        """
        messages = []

        # Add system prompt
        prompt = system_prompt or self.config.system_prompt
        if prompt:
            messages.append({"role": "system", "content": prompt})

        # Add conversation context if available
        if self.context_manager and self.config.enable_context:
            context_messages = self.context_manager.format_for_llm(thread_id)
            messages.extend(context_messages)

        # Add current user message
        messages.append({"role": "user", "content": content})

        return messages

    def _format_mcp_context(self, mcp_results: dict) -> str:
        """Format MCP results for inclusion in prompt."""
        results = mcp_results.get("results", [])
        if not results:
            return ""

        context_parts = ["Relevant context from knowledge base:"]
        for result in results[:5]:  # Limit to 5 results
            content = result.get("content", "")
            if content:
                context_parts.append(f"- {content}")

        return "\n".join(context_parts)

    def _inject_mcp_context(
        self,
        messages: List[dict[str, str]],
        mcp_context: str,
    ) -> List[dict[str, str]]:
        """Inject MCP context into message list."""
        if not mcp_context:
            return messages

        # Find system message and append context
        for i, msg in enumerate(messages):
            if msg["role"] == "system":
                messages[i] = {
                    "role": "system",
                    "content": f"{msg['content']}\n\n{mcp_context}",
                }
                return messages

        # If no system message, add one with context
        messages.insert(0, {"role": "system", "content": mcp_context})
        return messages
