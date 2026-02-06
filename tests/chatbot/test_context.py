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
TDD: RED Phase - Tests for thread context manager.

These tests define the expected behavior for the context manager before
implementation. They should FAIL until the manager is implemented.

Related GitHub Issues:
- #30: Test thread context manager (10 msg limit)
- #31: Implement ThreadContextManager
- #32: Test 24h TTL context expiration

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import Optional

# Import the context manager - this will fail until implemented (RED phase)
from luminescent_cluster.chatbot.context import (
    ThreadContextManager,
    ContextConfig,
    ThreadContext,
    ContextMessage,
)


class TestContextConfig:
    """TDD: Tests for ContextConfig data model."""

    def test_config_with_defaults(self):
        """ContextConfig should have ADR-006 specified defaults."""
        config = ContextConfig()

        assert config.max_messages == 10
        assert config.max_tokens == 2000
        assert config.ttl_hours == 24

    def test_config_custom_values(self):
        """ContextConfig should accept custom values."""
        config = ContextConfig(
            max_messages=20,
            max_tokens=4000,
            ttl_hours=48,
        )

        assert config.max_messages == 20
        assert config.max_tokens == 4000
        assert config.ttl_hours == 48


class TestContextMessage:
    """TDD: Tests for ContextMessage data model."""

    def test_message_has_required_fields(self):
        """ContextMessage should have required fields."""
        msg = ContextMessage(
            role="user",
            content="Hello, how are you?",
            timestamp=datetime.now(),
        )

        assert msg.role == "user"
        assert msg.content == "Hello, how are you?"
        assert msg.timestamp is not None

    def test_message_optional_fields(self):
        """ContextMessage should support optional fields."""
        msg = ContextMessage(
            role="assistant",
            content="I'm doing well!",
            timestamp=datetime.now(),
            message_id="msg-123",
            token_count=15,
            metadata={"model": "gpt-4"},
        )

        assert msg.message_id == "msg-123"
        assert msg.token_count == 15
        assert msg.metadata["model"] == "gpt-4"


class TestThreadContext:
    """TDD: Tests for ThreadContext data model."""

    def test_context_has_required_fields(self):
        """ThreadContext should have required fields."""
        ctx = ThreadContext(
            thread_id="thread-123",
            channel_id="channel-456",
            created_at=datetime.now(),
        )

        assert ctx.thread_id == "thread-123"
        assert ctx.channel_id == "channel-456"
        assert ctx.messages == []

    def test_context_with_messages(self):
        """ThreadContext should hold messages."""
        ctx = ThreadContext(
            thread_id="thread-123",
            channel_id="channel-456",
            created_at=datetime.now(),
            messages=[
                ContextMessage(role="user", content="Hi", timestamp=datetime.now()),
                ContextMessage(role="assistant", content="Hello!", timestamp=datetime.now()),
            ],
        )

        assert len(ctx.messages) == 2


class TestThreadContextManagerBasics:
    """TDD: Tests for basic context manager operations."""

    def test_create_manager(self):
        """Should create context manager with config."""
        config = ContextConfig(max_messages=10)
        manager = ThreadContextManager(config)

        assert manager.config.max_messages == 10

    def test_get_or_create_context(self):
        """Should get or create context for thread."""
        manager = ThreadContextManager()

        ctx = manager.get_or_create("thread-123", "channel-456")

        assert ctx.thread_id == "thread-123"
        assert ctx.channel_id == "channel-456"
        assert len(ctx.messages) == 0

    def test_get_existing_context(self):
        """Should return existing context for thread."""
        manager = ThreadContextManager()

        # Create context
        ctx1 = manager.get_or_create("thread-123", "channel-456")
        manager.add_message("thread-123", "user", "Hello")

        # Get same context
        ctx2 = manager.get_or_create("thread-123", "channel-456")

        assert ctx1.thread_id == ctx2.thread_id
        assert len(ctx2.messages) == 1


class TestMessageLimit:
    """TDD: Tests for 10 message limit (Issue #30)."""

    def test_respects_max_messages(self):
        """Context should respect max message limit."""
        config = ContextConfig(max_messages=10)
        manager = ThreadContextManager(config)

        # Add 12 messages
        for i in range(12):
            manager.add_message("thread-123", "user", f"Message {i}")

        ctx = manager.get_or_create("thread-123", "channel-456")
        assert len(ctx.messages) == 10

    def test_evicts_oldest_messages(self):
        """Should evict oldest messages when limit reached."""
        config = ContextConfig(max_messages=5)
        manager = ThreadContextManager(config)

        # Add messages 0-6
        for i in range(7):
            manager.add_message("thread-123", "user", f"Message {i}")

        ctx = manager.get_or_create("thread-123", "channel-456")

        # Should have messages 2-6 (oldest 0,1 evicted)
        assert len(ctx.messages) == 5
        assert "Message 2" in ctx.messages[0].content
        assert "Message 6" in ctx.messages[-1].content

    def test_sliding_window_behavior(self):
        """Message limit should act as sliding window."""
        config = ContextConfig(max_messages=3)
        manager = ThreadContextManager(config)

        manager.add_message("thread-123", "user", "A")
        manager.add_message("thread-123", "assistant", "B")
        manager.add_message("thread-123", "user", "C")

        ctx = manager.get_or_create("thread-123", "channel-456")
        assert len(ctx.messages) == 3

        # Add one more
        manager.add_message("thread-123", "assistant", "D")

        ctx = manager.get_or_create("thread-123", "channel-456")
        assert len(ctx.messages) == 3
        assert ctx.messages[0].content == "B"  # A was evicted
        assert ctx.messages[-1].content == "D"


class TestTokenLimit:
    """TDD: Tests for 2000 token limit."""

    def test_respects_max_tokens(self):
        """Context should respect max token limit."""
        config = ContextConfig(max_messages=100, max_tokens=100)
        manager = ThreadContextManager(config)

        # Add messages with known token counts
        manager.add_message("thread-123", "user", "Hello", token_count=10)
        manager.add_message("thread-123", "assistant", "Hi there!", token_count=15)
        manager.add_message("thread-123", "user", "How are you?", token_count=20)

        ctx = manager.get_or_create("thread-123", "channel-456")
        total_tokens = sum(m.token_count or 0 for m in ctx.messages)
        assert total_tokens <= 100

    def test_evicts_when_tokens_exceeded(self):
        """Should evict oldest messages when token limit exceeded."""
        config = ContextConfig(max_messages=100, max_tokens=50)
        manager = ThreadContextManager(config)

        manager.add_message("thread-123", "user", "First", token_count=20)
        manager.add_message("thread-123", "assistant", "Second", token_count=20)
        manager.add_message("thread-123", "user", "Third", token_count=20)

        ctx = manager.get_or_create("thread-123", "channel-456")

        # Should have evicted first message to stay under 50 tokens
        total_tokens = sum(m.token_count or 0 for m in ctx.messages)
        assert total_tokens <= 50


class TestTTLExpiration:
    """TDD: Tests for 24h TTL context expiration (Issue #32)."""

    def test_fresh_context_is_valid(self):
        """Fresh context should not be expired."""
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello")
        ctx = manager.get_or_create("thread-123", "channel-456")

        assert manager.is_expired("thread-123") is False

    def test_old_context_expires(self):
        """Context older than TTL should expire."""
        config = ContextConfig(ttl_hours=24)
        manager = ThreadContextManager(config)

        manager.add_message("thread-123", "user", "Hello")

        # Simulate time passing (25 hours)
        manager._advance_time(hours=25)

        assert manager.is_expired("thread-123") is True

    def test_expired_context_returns_empty(self):
        """Getting expired context should return fresh context."""
        config = ContextConfig(ttl_hours=1)
        manager = ThreadContextManager(config)

        manager.add_message("thread-123", "user", "Old message")

        # Simulate 2 hours passing
        manager._advance_time(hours=2)

        # Get context - should be fresh
        ctx = manager.get_or_create("thread-123", "channel-456")
        assert len(ctx.messages) == 0

    def test_activity_resets_ttl(self):
        """New messages should reset the TTL timer."""
        config = ContextConfig(ttl_hours=24)
        manager = ThreadContextManager(config)

        manager.add_message("thread-123", "user", "First")

        # Advance 20 hours
        manager._advance_time(hours=20)

        # Add new message
        manager.add_message("thread-123", "user", "Second")

        # Advance 20 more hours (40 total from first, 20 from second)
        manager._advance_time(hours=20)

        # Should NOT be expired (only 20h since last activity)
        assert manager.is_expired("thread-123") is False

    def test_cleanup_removes_expired(self):
        """Cleanup should remove expired contexts."""
        config = ContextConfig(ttl_hours=1)
        manager = ThreadContextManager(config)

        manager.add_message("thread-1", "user", "Hello")
        manager.add_message("thread-2", "user", "Hi")
        manager.add_message("thread-3", "user", "Hey")

        # Advance 2 hours
        manager._advance_time(hours=2)

        # Add fresh message to thread-3
        manager.add_message("thread-3", "user", "Still here")

        # Cleanup
        removed = manager.cleanup_expired()

        assert removed == 2  # thread-1 and thread-2
        assert manager.get_or_create("thread-3", "ch").messages[-1].content == "Still here"


class TestContextFormatting:
    """TDD: Tests for formatting context for LLM."""

    def test_format_for_llm(self):
        """Should format context as LLM message list."""
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello")
        manager.add_message("thread-123", "assistant", "Hi there!")
        manager.add_message("thread-123", "user", "How are you?")

        messages = manager.format_for_llm("thread-123")

        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    def test_format_with_system_message(self):
        """Should optionally prepend system message."""
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello")

        messages = manager.format_for_llm(
            "thread-123",
            system_message="You are a helpful assistant."
        )

        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert messages[1] == {"role": "user", "content": "Hello"}

    def test_format_empty_context(self):
        """Should handle empty context."""
        manager = ThreadContextManager()

        messages = manager.format_for_llm("nonexistent-thread")

        assert messages == []


class TestContextIsolation:
    """TDD: Tests for context isolation between threads/channels."""

    def test_threads_are_isolated(self):
        """Different threads should have isolated contexts."""
        manager = ThreadContextManager()

        manager.add_message("thread-A", "user", "Message A")
        manager.add_message("thread-B", "user", "Message B")

        ctx_a = manager.get_or_create("thread-A", "channel-1")
        ctx_b = manager.get_or_create("thread-B", "channel-1")

        assert len(ctx_a.messages) == 1
        assert ctx_a.messages[0].content == "Message A"
        assert len(ctx_b.messages) == 1
        assert ctx_b.messages[0].content == "Message B"

    def test_clear_context(self):
        """Should be able to clear a specific context."""
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello")
        manager.add_message("thread-123", "assistant", "Hi!")

        manager.clear("thread-123")

        ctx = manager.get_or_create("thread-123", "channel-456")
        assert len(ctx.messages) == 0


class TestContextPersistence:
    """TDD: Tests for context that could be persisted (future feature)."""

    def test_context_serializable(self):
        """Context should be serializable to dict."""
        manager = ThreadContextManager()

        manager.add_message("thread-123", "user", "Hello")
        manager.add_message("thread-123", "assistant", "Hi!")

        data = manager.to_dict("thread-123")

        assert "thread_id" in data
        assert "messages" in data
        assert len(data["messages"]) == 2

    def test_context_deserializable(self):
        """Context should be deserializable from dict."""
        manager = ThreadContextManager()

        data = {
            "thread_id": "thread-123",
            "channel_id": "channel-456",
            "created_at": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": datetime.now().isoformat()},
                {"role": "assistant", "content": "Hi!", "timestamp": datetime.now().isoformat()},
            ],
        }

        manager.from_dict(data)

        ctx = manager.get_or_create("thread-123", "channel-456")
        assert len(ctx.messages) == 2
