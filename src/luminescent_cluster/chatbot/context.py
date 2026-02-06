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
from typing import Optional, Dict, List, Any, Protocol, runtime_checkable
import threading
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContextConfig:
    """
    Configuration for thread context manager.

    Attributes:
        max_messages: Maximum messages per context (default 10)
        max_tokens: Maximum tokens per context (default 2000)
        ttl_hours: Hours before context expires (default 24)
        persistence_ttl_days: Days to retain persisted contexts (default 90)
    """

    max_messages: int = 10
    max_tokens: int = 2000
    ttl_hours: int = 24
    persistence_ttl_days: int = 90


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


# =============================================================================
# Context Store Protocol and Implementations
# =============================================================================


@runtime_checkable
class ContextStore(Protocol):
    """
    Protocol for context persistence storage.

    Implementations can use different backends (Pixeltable, Redis, etc.)
    to persist conversation context for recovery and long-term storage.

    Version: 1.0.0
    Related: ADR-006 Chatbot Platform Integrations, ADR-003 Pixeltable Patterns
    """

    async def save(self, thread_id: str, context_data: Dict[str, Any]) -> None:
        """
        Save context data to persistent storage.

        Args:
            thread_id: Unique thread identifier
            context_data: Serialized context data (from to_dict)
        """
        ...

    async def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Load context data from persistent storage.

        Args:
            thread_id: Unique thread identifier

        Returns:
            Context data dict if found, None otherwise
        """
        ...

    async def delete(self, thread_id: str) -> None:
        """
        Delete context from persistent storage.

        Args:
            thread_id: Unique thread identifier
        """
        ...

    async def cleanup_expired(self, ttl_days: int = 90) -> int:
        """
        Remove contexts older than TTL.

        Args:
            ttl_days: Days after which contexts expire

        Returns:
            Number of contexts deleted
        """
        ...


class PixeltableContextStore:
    """
    Pixeltable-based context persistence.

    Uses Pixeltable for durable storage of conversation contexts.
    Implements hot cache pattern: in-memory for fast reads, Pixeltable
    for persistence and recovery.

    Schema:
        conversation_context table with columns:
        - thread_id: Primary key
        - channel_id: Channel identifier
        - created_at: Creation timestamp
        - last_activity: Last activity timestamp
        - messages: JSON array of messages
        - metadata: Additional metadata JSON

    Version: 1.0.0
    Related: ADR-003 Pixeltable Patterns
    """

    TABLE_NAME = "conversation_context"

    def __init__(self):
        """Initialize Pixeltable context store."""
        self._available = True
        self._table = None
        self._init_attempted = False

    def _ensure_table(self) -> bool:
        """Ensure Pixeltable table exists. Returns True if available."""
        if self._init_attempted:
            return self._available

        self._init_attempted = True
        try:
            import pixeltable as pxt

            # Try to get or create the table
            try:
                self._table = pxt.get_table(self.TABLE_NAME)
            except Exception:
                # Table doesn't exist, create it
                self._table = pxt.create_table(
                    self.TABLE_NAME,
                    {
                        "thread_id": pxt.String,
                        "channel_id": pxt.String,
                        "created_at": pxt.Timestamp,
                        "last_activity": pxt.Timestamp,
                        "messages": pxt.Json,
                        "metadata": pxt.Json,
                    },
                    primary_key="thread_id",
                )
            self._available = True
        except Exception as e:
            logger.warning(f"Pixeltable unavailable, context persistence disabled: {e}")
            self._available = False

        return self._available

    async def save(self, thread_id: str, context_data: Dict[str, Any]) -> None:
        """Save context to Pixeltable."""
        if not self._ensure_table():
            return

        try:
            import pixeltable as pxt

            # Convert ISO strings to datetime for Pixeltable
            created_at = datetime.fromisoformat(context_data.get("created_at", datetime.now().isoformat()))
            last_activity = datetime.fromisoformat(context_data.get("last_activity", datetime.now().isoformat()))

            row = {
                "thread_id": thread_id,
                "channel_id": context_data.get("channel_id", ""),
                "created_at": created_at,
                "last_activity": last_activity,
                "messages": context_data.get("messages", []),
                "metadata": context_data.get("metadata", {}),
            }

            # Use upsert for idempotent saves
            self._table.upsert([row])
            logger.debug(f"Saved context for thread {thread_id}")
        except Exception as e:
            logger.warning(f"Failed to save context for {thread_id}: {e}")

    async def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Load context from Pixeltable."""
        if not self._ensure_table():
            return None

        try:
            import pixeltable as pxt

            # Query for the thread
            result = self._table.where(self._table.thread_id == thread_id).collect()

            if len(result) == 0:
                return None

            row = result.iloc[0]
            return {
                "thread_id": row["thread_id"],
                "channel_id": row["channel_id"],
                "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                "last_activity": row["last_activity"].isoformat() if hasattr(row["last_activity"], "isoformat") else str(row["last_activity"]),
                "messages": row["messages"],
                "metadata": row.get("metadata", {}),
            }
        except Exception as e:
            logger.warning(f"Failed to load context for {thread_id}: {e}")
            return None

    async def delete(self, thread_id: str) -> None:
        """Delete context from Pixeltable."""
        if not self._ensure_table():
            return

        try:
            self._table.delete(self._table.thread_id == thread_id)
            logger.debug(f"Deleted context for thread {thread_id}")
        except Exception as e:
            logger.warning(f"Failed to delete context for {thread_id}: {e}")

    async def cleanup_expired(self, ttl_days: int = 90) -> int:
        """Remove contexts older than TTL."""
        if not self._ensure_table():
            return 0

        try:
            cutoff = datetime.now() - timedelta(days=ttl_days)
            result = self._table.delete(self._table.last_activity < cutoff)
            count = getattr(result, "count", 0)
            logger.info(f"Cleaned up {count} expired contexts")
            return count
        except Exception as e:
            logger.warning(f"Failed to cleanup expired contexts: {e}")
            return 0


class ThreadContextManager:
    """
    Manages conversation context for chat threads.

    Features:
    - Sliding window message limit (default 10)
    - Token-based limit (default 2000)
    - TTL-based expiration (default 24h)
    - Thread-safe operations
    - Optional persistent storage via ContextStore

    Example:
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello!")
        manager.add_message("thread-123", "assistant", "Hi there!")

        messages = manager.format_for_llm("thread-123")
        # [{"role": "user", "content": "Hello!"}, ...]

    With persistence:
        store = PixeltableContextStore()
        manager = ThreadContextManager(context_store=store)
        # Contexts will be persisted to Pixeltable
    """

    def __init__(
        self,
        config: Optional[ContextConfig] = None,
        context_store: Optional[ContextStore] = None,
    ):
        """Initialize context manager with configuration."""
        self.config = config or ContextConfig()
        self.context_store = context_store
        self._lock = threading.RLock()
        self._contexts: Dict[str, ThreadContext] = {}

        # Pending saves for batch flush
        self._pending_saves: set[str] = set()

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

            # Mark for pending save
            if self.context_store:
                self._pending_saves.add(thread_id)

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

    # =========================================================================
    # Async Methods for Persistence
    # =========================================================================

    async def flush(self) -> None:
        """
        Flush all pending context changes to persistent storage.

        Should be called periodically or after important operations
        to ensure context is persisted.
        """
        if not self.context_store:
            return

        with self._lock:
            pending = list(self._pending_saves)
            self._pending_saves.clear()

        for thread_id in pending:
            data = self.to_dict(thread_id)
            if data:
                await self.context_store.save(thread_id, data)

    async def get_or_create_async(
        self, thread_id: str, channel_id: str
    ) -> ThreadContext:
        """
        Async version of get_or_create that loads from persistent storage.

        Args:
            thread_id: Thread identifier
            channel_id: Channel identifier

        Returns:
            ThreadContext for the thread
        """
        with self._lock:
            # Check if already in memory
            if thread_id in self._contexts:
                if not self.is_expired(thread_id):
                    return self._contexts[thread_id]
                else:
                    del self._contexts[thread_id]

        # Try to load from persistent storage
        if self.context_store:
            data = await self.context_store.load(thread_id)
            if data:
                self.from_dict(data)
                with self._lock:
                    if thread_id in self._contexts:
                        return self._contexts[thread_id]

        # Create new context
        return self.get_or_create(thread_id, channel_id)

    async def add_message_async(
        self,
        thread_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        token_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Async version of add_message.

        Adds message and immediately flushes to persistent storage
        if a context store is configured.
        """
        self.add_message(
            thread_id=thread_id,
            role=role,
            content=content,
            message_id=message_id,
            token_count=token_count,
            metadata=metadata,
        )
        await self.flush()

    async def clear_async(self, thread_id: str) -> None:
        """
        Async version of clear that also removes from persistent storage.

        Args:
            thread_id: Thread identifier
        """
        self.clear(thread_id)
        if self.context_store:
            await self.context_store.delete(thread_id)
