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
Thread context manager for Luminescent Cluster chatbot.

Manages conversation context for chat threads with:
- 10 message sliding window (configurable)
- 2000 token limit (configurable)
- 24 hour TTL expiration (configurable)

Design (from ADR-006):
- Bounded context to control LLM costs
- TTL-based expiration for stale conversations
- Thread-isolated contexts

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import threading


@dataclass
class ContextConfig:
    """
    Configuration for thread context manager.

    Attributes:
        max_messages: Maximum messages per context (default 10)
        max_tokens: Maximum tokens per context (default 2000)
        ttl_hours: Hours before context expires (default 24)
    """

    max_messages: int = 10
    max_tokens: int = 2000
    ttl_hours: int = 24


@dataclass
class ContextMessage:
    """
    A message in the conversation context.

    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: When the message was sent
        message_id: Optional message ID
        token_count: Optional token count for this message
        metadata: Optional additional metadata
    """

    role: str
    content: str
    timestamp: datetime
    message_id: Optional[str] = None
    token_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreadContext:
    """
    Context for a conversation thread.

    Attributes:
        thread_id: Unique thread identifier
        channel_id: Channel where thread exists
        created_at: When context was created
        last_activity: Last activity timestamp
        messages: List of context messages
    """

    thread_id: str
    channel_id: str
    created_at: datetime
    last_activity: datetime = field(default_factory=datetime.now)
    messages: List[ContextMessage] = field(default_factory=list)


class ThreadContextManager:
    """
    Manages conversation context for chat threads.

    Features:
    - Sliding window message limit (default 10)
    - Token-based limit (default 2000)
    - TTL-based expiration (default 24h)
    - Thread-safe operations

    Example:
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello!")
        manager.add_message("thread-123", "assistant", "Hi there!")

        messages = manager.format_for_llm("thread-123")
        # [{"role": "user", "content": "Hello!"}, ...]
    """

    def __init__(self, config: Optional[ContextConfig] = None):
        """Initialize context manager with configuration."""
        self.config = config or ContextConfig()
        self._lock = threading.RLock()
        self._contexts: Dict[str, ThreadContext] = {}

        # Time offset for testing
        self._time_offset_hours: float = 0.0

    def _current_time(self) -> datetime:
        """Get current time with test offset."""
        return datetime.now() + timedelta(hours=self._time_offset_hours)

    def _advance_time(self, hours: float) -> None:
        """Advance time for testing purposes."""
        self._time_offset_hours += hours

    def get_or_create(self, thread_id: str, channel_id: str) -> ThreadContext:
        """
        Get existing context or create new one.

        Args:
            thread_id: Thread identifier
            channel_id: Channel identifier

        Returns:
            ThreadContext for the thread
        """
        with self._lock:
            # Check if context exists and is not expired
            if thread_id in self._contexts:
                if self.is_expired(thread_id):
                    # Remove expired context
                    del self._contexts[thread_id]
                else:
                    return self._contexts[thread_id]

            # Create new context
            ctx = ThreadContext(
                thread_id=thread_id,
                channel_id=channel_id,
                created_at=self._current_time(),
                last_activity=self._current_time(),
            )
            self._contexts[thread_id] = ctx
            return ctx

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        token_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a message to thread context.

        Args:
            thread_id: Thread identifier
            role: Message role (user, assistant, system)
            content: Message content
            message_id: Optional message ID
            token_count: Optional token count
            metadata: Optional metadata
        """
        with self._lock:
            # Get or create context (use empty channel_id, will be set on first get_or_create)
            if thread_id not in self._contexts:
                self._contexts[thread_id] = ThreadContext(
                    thread_id=thread_id,
                    channel_id="",
                    created_at=self._current_time(),
                    last_activity=self._current_time(),
                )

            ctx = self._contexts[thread_id]

            # Create message
            msg = ContextMessage(
                role=role,
                content=content,
                timestamp=self._current_time(),
                message_id=message_id,
                token_count=token_count,
                metadata=metadata or {},
            )

            # Add message
            ctx.messages.append(msg)
            ctx.last_activity = self._current_time()

            # Enforce limits
            self._enforce_limits(ctx)

    def _enforce_limits(self, ctx: ThreadContext) -> None:
        """Enforce message and token limits on context."""
        # Enforce message limit
        while len(ctx.messages) > self.config.max_messages:
            ctx.messages.pop(0)

        # Enforce token limit
        total_tokens = sum(m.token_count or 0 for m in ctx.messages)
        while total_tokens > self.config.max_tokens and len(ctx.messages) > 0:
            removed = ctx.messages.pop(0)
            total_tokens -= removed.token_count or 0

    def is_expired(self, thread_id: str) -> bool:
        """
        Check if a context has expired.

        Args:
            thread_id: Thread identifier

        Returns:
            True if context has expired
        """
        with self._lock:
            if thread_id not in self._contexts:
                return True

            ctx = self._contexts[thread_id]
            expiry_time = ctx.last_activity + timedelta(hours=self.config.ttl_hours)
            return self._current_time() > expiry_time

    def cleanup_expired(self) -> int:
        """
        Remove all expired contexts.

        Returns:
            Number of contexts removed
        """
        with self._lock:
            expired = [
                tid for tid in self._contexts.keys()
                if self.is_expired(tid)
            ]
            for tid in expired:
                del self._contexts[tid]
            return len(expired)

    def clear(self, thread_id: str) -> None:
        """
        Clear context for a thread.

        Args:
            thread_id: Thread identifier
        """
        with self._lock:
            if thread_id in self._contexts:
                del self._contexts[thread_id]

    def format_for_llm(
        self,
        thread_id: str,
        system_message: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Format context as LLM message list.

        Args:
            thread_id: Thread identifier
            system_message: Optional system message to prepend

        Returns:
            List of message dicts for LLM
        """
        with self._lock:
            messages = []

            if system_message:
                messages.append({"role": "system", "content": system_message})

            if thread_id in self._contexts:
                ctx = self._contexts[thread_id]
                for msg in ctx.messages:
                    messages.append({"role": msg.role, "content": msg.content})

            return messages

    def to_dict(self, thread_id: str) -> Dict[str, Any]:
        """
        Serialize context to dictionary.

        Args:
            thread_id: Thread identifier

        Returns:
            Dict representation of context
        """
        with self._lock:
            if thread_id not in self._contexts:
                return {}

            ctx = self._contexts[thread_id]
            return {
                "thread_id": ctx.thread_id,
                "channel_id": ctx.channel_id,
                "created_at": ctx.created_at.isoformat(),
                "last_activity": ctx.last_activity.isoformat(),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat(),
                        "message_id": m.message_id,
                        "token_count": m.token_count,
                        "metadata": m.metadata,
                    }
                    for m in ctx.messages
                ],
            }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Deserialize context from dictionary.

        Args:
            data: Dict representation of context
        """
        with self._lock:
            thread_id = data["thread_id"]
            ctx = ThreadContext(
                thread_id=thread_id,
                channel_id=data["channel_id"],
                created_at=datetime.fromisoformat(data["created_at"]),
                last_activity=datetime.fromisoformat(data.get("last_activity", data["created_at"])),
                messages=[
                    ContextMessage(
                        role=m["role"],
                        content=m["content"],
                        timestamp=datetime.fromisoformat(m["timestamp"]),
                        message_id=m.get("message_id"),
                        token_count=m.get("token_count"),
                        metadata=m.get("metadata", {}),
                    )
                    for m in data.get("messages", [])
                ],
            )
            self._contexts[thread_id] = ctx
