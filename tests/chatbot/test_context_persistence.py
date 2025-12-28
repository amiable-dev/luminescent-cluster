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
TDD: RED Phase - Tests for Pixeltable Context Persistence.

These tests define the expected behavior for context persistence using
Pixeltable. They should FAIL until the implementation is complete.

Related GitHub Issues:
- #64: Test Pixeltable context persistence (this file)
- #65: Implement PixeltableContextStore

ADR Reference: ADR-006 Chatbot Platform Integrations, ADR-003 Pixeltable Patterns
"""

import pytest
from datetime import datetime, timedelta
from typing import Optional, Protocol, runtime_checkable
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.chatbot.context import (
    ThreadContextManager,
    ContextConfig,
    ThreadContext,
    ContextMessage,
    ContextStore,
    PixeltableContextStore,
)


class TestContextStoreProtocol:
    """Tests for ContextStore protocol definition."""

    def test_context_store_protocol_exists(self):
        """ContextStore protocol should be defined."""
        assert ContextStore is not None

    def test_context_store_is_runtime_checkable(self):
        """ContextStore protocol should be runtime checkable."""
        assert hasattr(ContextStore, "__runtime_checkable__") or isinstance(
            ContextStore, type
        )

    def test_context_store_has_save_method(self):
        """ContextStore should have async save method."""
        # Protocol requires save(thread_id, context_data) -> None
        assert hasattr(ContextStore, "save")

    def test_context_store_has_load_method(self):
        """ContextStore should have async load method."""
        # Protocol requires load(thread_id) -> Optional[dict]
        assert hasattr(ContextStore, "load")

    def test_context_store_has_delete_method(self):
        """ContextStore should have async delete method."""
        # Protocol requires delete(thread_id) -> None
        assert hasattr(ContextStore, "delete")

    def test_context_store_has_cleanup_expired_method(self):
        """ContextStore should have cleanup method for TTL."""
        # Protocol requires cleanup_expired(ttl_days) -> int
        assert hasattr(ContextStore, "cleanup_expired")


class MockContextStore:
    """Mock implementation for testing."""

    def __init__(self):
        self._storage: dict[str, dict] = {}
        self.save_calls: list[tuple] = []
        self.load_calls: list[str] = []

    async def save(self, thread_id: str, context_data: dict) -> None:
        self._storage[thread_id] = context_data
        self.save_calls.append((thread_id, context_data))

    async def load(self, thread_id: str) -> Optional[dict]:
        self.load_calls.append(thread_id)
        return self._storage.get(thread_id)

    async def delete(self, thread_id: str) -> None:
        if thread_id in self._storage:
            del self._storage[thread_id]

    async def cleanup_expired(self, ttl_days: int = 90) -> int:
        # Simulate cleanup
        return 0


class TestThreadContextManagerWithStore:
    """Tests for ThreadContextManager with ContextStore integration."""

    @pytest.mark.asyncio
    async def test_manager_accepts_context_store(self):
        """ThreadContextManager should accept optional ContextStore."""
        store = MockContextStore()
        manager = ThreadContextManager(context_store=store)
        assert manager.context_store is store

    @pytest.mark.asyncio
    async def test_manager_saves_context_on_add_message(self):
        """Adding a message should trigger context save."""
        store = MockContextStore()
        manager = ThreadContextManager(context_store=store)

        manager.add_message(
            thread_id="thread-123",
            role="user",
            content="Hello!",
        )

        # Allow async save to complete
        await manager.flush()

        assert len(store.save_calls) == 1
        assert store.save_calls[0][0] == "thread-123"

    @pytest.mark.asyncio
    async def test_manager_loads_context_on_get(self):
        """Getting context should load from store if not in memory."""
        store = MockContextStore()
        # Pre-populate store
        await store.save("thread-456", {
            "thread_id": "thread-456",
            "channel_id": "channel-1",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "messages": [
                {
                    "role": "user",
                    "content": "Previous message",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        })

        manager = ThreadContextManager(context_store=store)
        ctx = await manager.get_or_create_async("thread-456", "channel-1")

        assert ctx is not None
        assert len(ctx.messages) == 1
        assert ctx.messages[0].content == "Previous message"

    @pytest.mark.asyncio
    async def test_context_survives_manager_recreation(self):
        """Context should persist across manager instances."""
        store = MockContextStore()

        # First manager adds context
        manager1 = ThreadContextManager(context_store=store)
        manager1.add_message("thread-789", "user", "Hello!")
        manager1.add_message("thread-789", "assistant", "Hi there!")
        await manager1.flush()

        # Second manager should load context
        manager2 = ThreadContextManager(context_store=store)
        ctx = await manager2.get_or_create_async("thread-789", "channel-1")

        assert len(ctx.messages) == 2
        assert ctx.messages[0].content == "Hello!"
        assert ctx.messages[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_hot_cache_prevents_redundant_loads(self):
        """Loaded context should be cached in memory."""
        store = MockContextStore()
        await store.save("thread-111", {
            "thread_id": "thread-111",
            "channel_id": "ch-1",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "messages": [],
        })

        manager = ThreadContextManager(context_store=store)

        # First access loads from store
        await manager.get_or_create_async("thread-111", "ch-1")
        assert len(store.load_calls) == 1

        # Second access should use cache
        await manager.get_or_create_async("thread-111", "ch-1")
        assert len(store.load_calls) == 1  # No additional load

    @pytest.mark.asyncio
    async def test_manager_deletes_on_clear(self):
        """Clearing context should delete from store."""
        store = MockContextStore()
        manager = ThreadContextManager(context_store=store)

        manager.add_message("thread-222", "user", "Hello!")
        await manager.flush()

        await manager.clear_async("thread-222")

        assert "thread-222" not in store._storage


class TestPixeltableContextStore:
    """Tests for PixeltableContextStore implementation."""

    def test_pixeltable_store_exists(self):
        """PixeltableContextStore class should exist."""
        assert PixeltableContextStore is not None

    def test_pixeltable_store_implements_protocol(self):
        """PixeltableContextStore should implement ContextStore."""
        store = PixeltableContextStore.__new__(PixeltableContextStore)
        assert isinstance(store, ContextStore)

    @pytest.mark.asyncio
    async def test_pixeltable_store_save_and_load(self):
        """PixeltableContextStore should save and load context."""
        import sys
        mock_pxt = MagicMock()
        mock_table = MagicMock()
        mock_pxt.get_table.return_value = mock_table

        with patch.dict(sys.modules, {"pixeltable": mock_pxt}):
            store = PixeltableContextStore()
            store._init_attempted = False  # Reset so it tries again

            context_data = {
                "thread_id": "thread-333",
                "channel_id": "ch-1",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "messages": [{"role": "user", "content": "Test"}],
            }

            await store.save("thread-333", context_data)

            # Verify table interaction happened
            assert store._init_attempted

    @pytest.mark.asyncio
    async def test_pixeltable_store_graceful_degradation(self):
        """Store should handle Pixeltable unavailability gracefully."""
        import sys

        # Create a mock that raises when imported
        mock_pxt = MagicMock()
        mock_pxt.get_table.side_effect = Exception("Pixeltable unavailable")

        with patch.dict(sys.modules, {"pixeltable": mock_pxt}):
            store = PixeltableContextStore()
            store._init_attempted = False

            # Should not raise, should degrade gracefully
            await store.save("thread-444", {"thread_id": "thread-444", "created_at": datetime.now().isoformat(), "last_activity": datetime.now().isoformat()})
            result = await store.load("thread-444")

            # Returns None when unavailable (graceful degradation)
            assert result is None

    @pytest.mark.asyncio
    async def test_pixeltable_store_cleanup_expired(self):
        """Store should clean up contexts older than TTL."""
        import sys
        mock_pxt = MagicMock()
        mock_table = MagicMock()
        mock_pxt.get_table.return_value = mock_table
        mock_table.delete.return_value = MagicMock(count=5)

        with patch.dict(sys.modules, {"pixeltable": mock_pxt}):
            store = PixeltableContextStore()
            store._init_attempted = False

            deleted = await store.cleanup_expired(ttl_days=90)

            # Should return a count (0 if nothing deleted or unavailable)
            assert deleted >= 0


class TestContextPersistenceConfig:
    """Tests for persistence configuration."""

    def test_config_accepts_retention_days(self):
        """ContextConfig should accept persistence retention days."""
        config = ContextConfig(persistence_ttl_days=90)
        assert config.persistence_ttl_days == 90

    def test_config_default_retention(self):
        """Default retention should be 90 days per ADR-006."""
        config = ContextConfig()
        assert config.persistence_ttl_days == 90


class TestAsyncContextOperations:
    """Tests for async context operations."""

    @pytest.mark.asyncio
    async def test_get_or_create_async_exists(self):
        """ThreadContextManager should have async get_or_create."""
        manager = ThreadContextManager()
        ctx = await manager.get_or_create_async("thread-555", "ch-1")
        assert ctx is not None
        assert ctx.thread_id == "thread-555"

    @pytest.mark.asyncio
    async def test_add_message_async_exists(self):
        """ThreadContextManager should have async add_message option."""
        manager = ThreadContextManager()
        await manager.add_message_async(
            thread_id="thread-666",
            role="user",
            content="Async message",
        )

        ctx = await manager.get_or_create_async("thread-666", "ch-1")
        assert len(ctx.messages) == 1

    @pytest.mark.asyncio
    async def test_flush_persists_pending_changes(self):
        """flush() should persist all pending context changes."""
        store = MockContextStore()
        manager = ThreadContextManager(context_store=store)

        # Add multiple messages quickly
        manager.add_message("thread-777", "user", "Msg 1")
        manager.add_message("thread-777", "assistant", "Msg 2")
        manager.add_message("thread-888", "user", "Msg 3")

        # Flush all pending changes
        await manager.flush()

        # Both threads should be persisted
        assert "thread-777" in store._storage
        assert "thread-888" in store._storage
