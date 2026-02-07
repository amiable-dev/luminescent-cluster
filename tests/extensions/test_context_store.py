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
TDD: RED Phase - Tests for ContextStore consolidation in ExtensionRegistry.

Part of Issue #72: Consolidate ContextStore into ExtensionRegistry.

ADR Reference: ADR-007 Cross-ADR Integration Guide
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestContextStoreProtocolInProtocols:
    """Tests that ContextStore protocol is exported from protocols module."""

    def test_context_store_protocol_exists_in_protocols(self):
        """ContextStore protocol is defined in protocols module."""
        from luminescent_cluster.extensions.protocols import ContextStore

        assert ContextStore is not None

    def test_context_store_version_constant_exists(self):
        """CONTEXT_STORE_VERSION constant exists."""
        from luminescent_cluster.extensions.protocols import CONTEXT_STORE_VERSION

        assert CONTEXT_STORE_VERSION is not None

    def test_context_store_version_is_1_0_0(self):
        """CONTEXT_STORE_VERSION is 1.0.0."""
        from luminescent_cluster.extensions.protocols import CONTEXT_STORE_VERSION

        assert CONTEXT_STORE_VERSION == "1.0.0"

    def test_context_store_is_runtime_checkable(self):
        """ContextStore should be a runtime-checkable Protocol."""
        from luminescent_cluster.extensions.protocols import ContextStore

        # Can use isinstance() check
        assert hasattr(ContextStore, "__protocol_attrs__") or isinstance(ContextStore, type)


class TestContextStoreProtocolMethods:
    """Tests that ContextStore protocol has required methods."""

    def test_context_store_has_save_method(self):
        """ContextStore protocol defines save method."""
        from luminescent_cluster.extensions.protocols import ContextStore

        assert hasattr(ContextStore, "save")

    def test_context_store_has_load_method(self):
        """ContextStore protocol defines load method."""
        from luminescent_cluster.extensions.protocols import ContextStore

        assert hasattr(ContextStore, "load")

    def test_context_store_has_delete_method(self):
        """ContextStore protocol defines delete method."""
        from luminescent_cluster.extensions.protocols import ContextStore

        assert hasattr(ContextStore, "delete")

    def test_context_store_has_cleanup_expired_method(self):
        """ContextStore protocol defines cleanup_expired method."""
        from luminescent_cluster.extensions.protocols import ContextStore

        assert hasattr(ContextStore, "cleanup_expired")


class TestContextStoreInRegistry:
    """Tests that ExtensionRegistry has context_store slot."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_registry_has_context_store_attribute(self):
        """ExtensionRegistry has context_store attribute."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        assert hasattr(registry, "context_store")

    def test_context_store_defaults_to_none(self):
        """context_store defaults to None in OSS mode."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        assert registry.context_store is None

    def test_can_register_context_store(self):
        """Can register a ContextStore implementation."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        mock_store.load = AsyncMock(return_value=None)
        mock_store.delete = AsyncMock()
        mock_store.cleanup_expired = AsyncMock(return_value=0)

        registry.context_store = mock_store

        assert registry.context_store is mock_store

    def test_context_store_in_status(self):
        """get_status() includes context_store status."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        status = registry.get_status()

        assert "context_store" in status
        assert status["context_store"] is False

    def test_context_store_status_true_when_registered(self):
        """get_status() shows context_store=True when registered."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        registry.context_store = MagicMock()

        status = registry.get_status()
        assert status["context_store"] is True


class TestContextStoreExports:
    """Tests that ContextStore is properly exported."""

    def test_context_store_in_protocols_all(self):
        """ContextStore is in protocols.__all__."""
        from luminescent_cluster.extensions import protocols

        assert "ContextStore" in protocols.__all__

    def test_context_store_version_in_protocols_all(self):
        """CONTEXT_STORE_VERSION is in protocols.__all__."""
        from luminescent_cluster.extensions import protocols

        assert "CONTEXT_STORE_VERSION" in protocols.__all__

    def test_context_store_in_extensions_all(self):
        """ContextStore is in extensions.__all__."""
        from luminescent_cluster import extensions

        assert "ContextStore" in extensions.__all__

    def test_context_store_version_in_extensions_all(self):
        """CONTEXT_STORE_VERSION is in extensions.__all__."""
        from luminescent_cluster import extensions

        assert "CONTEXT_STORE_VERSION" in extensions.__all__


class TestContextStoreImplementationSatisfiesProtocol:
    """Tests that implementations satisfy the ContextStore protocol."""

    def test_mock_implementation_satisfies_protocol(self):
        """A properly implemented class should satisfy ContextStore protocol."""
        from luminescent_cluster.extensions.protocols import ContextStore
        from typing import Optional, Dict, Any

        class MockContextStore:
            async def save(self, thread_id: str, context_data: Dict[str, Any]) -> None:
                pass

            async def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
                return None

            async def delete(self, thread_id: str) -> None:
                pass

            async def cleanup_expired(self, ttl_days: int = 90) -> int:
                return 0

        store = MockContextStore()
        assert isinstance(store, ContextStore)
