# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for MemoryProvider Protocol.

These tests define the expected behavior for the MemoryProvider protocol
following the ADR-007 extension pattern.

Related GitHub Issues:
- #80: Define MemoryProvider Protocol (ADR-007 Pattern)

ADR Reference: ADR-003 Memory Architecture, Phase 0 (Foundations)
ADR Reference: ADR-007 Cross-ADR Integration Guide
"""

import pytest
from typing import Optional


class TestMemoryProviderVersionConstant:
    """TDD: Tests for MEMORY_PROVIDER_VERSION constant."""

    def test_memory_provider_version_exists(self):
        """MEMORY_PROVIDER_VERSION constant should be defined.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Protocol Versioning)
        """
        from luminescent_cluster.extensions.protocols import MEMORY_PROVIDER_VERSION

        assert MEMORY_PROVIDER_VERSION is not None

    def test_memory_provider_version_is_semver(self):
        """MEMORY_PROVIDER_VERSION should follow SemVer format.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Protocol Versioning)
        """
        import re

        from luminescent_cluster.extensions.protocols import MEMORY_PROVIDER_VERSION

        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, MEMORY_PROVIDER_VERSION), (
            f"Version {MEMORY_PROVIDER_VERSION} does not match SemVer pattern"
        )

    def test_memory_provider_version_is_1_0_0(self):
        """MEMORY_PROVIDER_VERSION should be 1.0.0 (initial release).

        GitHub Issue: #80
        ADR Reference: ADR-007 (Protocol Versioning)
        """
        from luminescent_cluster.extensions.protocols import MEMORY_PROVIDER_VERSION

        assert MEMORY_PROVIDER_VERSION == "1.0.0"


class TestMemoryProviderProtocolDefinition:
    """TDD: Tests for MemoryProvider protocol structure."""

    def test_memory_provider_is_runtime_checkable(self):
        """MemoryProvider should be a runtime-checkable Protocol.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Patterns)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider

        # Test runtime checkability by verifying isinstance() works
        # This only succeeds if @runtime_checkable decorator is applied
        class MinimalProvider:
            async def store(self, memory, context): pass
            async def retrieve(self, query, user_id, limit=5): pass
            async def get_by_id(self, memory_id): pass
            async def delete(self, memory_id): pass
            async def search(self, user_id, filters, limit=10): pass

        # isinstance() with Protocol raises TypeError if not @runtime_checkable
        assert isinstance(MinimalProvider(), MemoryProvider)

    def test_memory_provider_has_store_method(self):
        """MemoryProvider should define store method.

        GitHub Issue: #80
        ADR Reference: ADR-003 Phase 0 (MemoryProvider Protocol)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider

        assert hasattr(MemoryProvider, "store")

    def test_memory_provider_has_retrieve_method(self):
        """MemoryProvider should define retrieve method.

        GitHub Issue: #80
        ADR Reference: ADR-003 Phase 0 (MemoryProvider Protocol)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider

        assert hasattr(MemoryProvider, "retrieve")

    def test_memory_provider_has_get_by_id_method(self):
        """MemoryProvider should define get_by_id method.

        GitHub Issue: #80
        ADR Reference: ADR-003 Phase 0 (MemoryProvider Protocol)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider

        assert hasattr(MemoryProvider, "get_by_id")

    def test_memory_provider_has_delete_method(self):
        """MemoryProvider should define delete method.

        GitHub Issue: #80
        ADR Reference: ADR-003 Phase 0 (MemoryProvider Protocol)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider

        assert hasattr(MemoryProvider, "delete")

    def test_memory_provider_has_search_method(self):
        """MemoryProvider should define search method.

        GitHub Issue: #80
        ADR Reference: ADR-003 Phase 0 (MemoryProvider Protocol)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider

        assert hasattr(MemoryProvider, "search")


class TestMemoryProviderBehavior:
    """TDD: Tests for MemoryProvider behavior with mock implementation."""

    def test_mock_implementation_satisfies_protocol(self):
        """A properly implemented class should satisfy MemoryProvider protocol.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Patterns)
        """
        from luminescent_cluster.extensions.protocols import MemoryProvider
        from luminescent_cluster.memory.schemas.memory_types import Memory

        class MockMemoryProvider:
            """Mock implementation for testing."""

            async def store(self, memory: Memory, context: dict) -> str:
                return "memory-123"

            async def retrieve(
                self, query: str, user_id: str, limit: int = 5
            ) -> list[Memory]:
                return []

            async def get_by_id(self, memory_id: str) -> Optional[Memory]:
                return None

            async def delete(self, memory_id: str) -> bool:
                return True

            async def search(
                self, user_id: str, filters: dict, limit: int = 10
            ) -> list[Memory]:
                return []

        provider = MockMemoryProvider()
        assert isinstance(provider, MemoryProvider)


class TestMemoryProviderInRegistry:
    """TDD: Tests for MemoryProvider in ExtensionRegistry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_registry_has_memory_provider_field(self):
        """ExtensionRegistry should have memory_provider field.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Registry Pattern)
        """
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        assert hasattr(registry, "memory_provider")

    def test_memory_provider_defaults_to_none(self):
        """memory_provider should default to None (OSS mode).

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Registry Pattern)
        """
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        assert registry.memory_provider is None

    def test_registry_has_memory_enabled_helper(self):
        """ExtensionRegistry should have has_memory_provider method.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Registry Pattern)
        """
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        assert hasattr(registry, "has_memory_provider")

    def test_has_memory_provider_returns_false_by_default(self):
        """has_memory_provider should return False in OSS mode.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Registry Pattern)
        """
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        assert registry.has_memory_provider() is False

    def test_get_status_includes_memory_provider(self):
        """get_status should include memory_provider field.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Extension Registry Pattern)
        """
        from luminescent_cluster.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        status = registry.get_status()
        assert "memory_provider" in status


class TestMemoryProviderExports:
    """TDD: Tests for protocol exports."""

    def test_memory_provider_in_protocols_all(self):
        """MemoryProvider should be in protocols.__all__.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Module Exports)
        """
        from luminescent_cluster.extensions import protocols

        assert "MemoryProvider" in protocols.__all__

    def test_memory_provider_version_in_protocols_all(self):
        """MEMORY_PROVIDER_VERSION should be in protocols.__all__.

        GitHub Issue: #80
        ADR Reference: ADR-007 (Module Exports)
        """
        from luminescent_cluster.extensions import protocols

        assert "MEMORY_PROVIDER_VERSION" in protocols.__all__


class TestMemoryProviderModuleExports:
    """TDD: Tests for module-level exports from luminescent_cluster.extensions (ADR-005 dual-repo)."""

    def test_memory_provider_importable_from_extensions(self):
        """MemoryProvider should be importable from luminescent_cluster.extensions module.

        This is required for the dual-repo pattern (ADR-005) so that
        luminescent-cloud can import from the public extensions API.

        GitHub Issue: #114
        ADR Reference: ADR-005 (Dual-Repo Pattern)
        """
        from luminescent_cluster.extensions import MemoryProvider

        assert MemoryProvider is not None

    def test_memory_provider_version_importable_from_extensions(self):
        """MEMORY_PROVIDER_VERSION should be importable from luminescent_cluster.extensions module.

        GitHub Issue: #114
        ADR Reference: ADR-005 (Dual-Repo Pattern)
        """
        from luminescent_cluster.extensions import MEMORY_PROVIDER_VERSION

        assert MEMORY_PROVIDER_VERSION == "1.0.0"

    def test_response_filter_importable_from_extensions(self):
        """ResponseFilter should be importable from luminescent_cluster.extensions module.

        GitHub Issue: #114
        ADR Reference: ADR-005 (Dual-Repo Pattern)
        """
        from luminescent_cluster.extensions import ResponseFilter

        assert ResponseFilter is not None

    def test_memory_provider_in_extensions_all(self):
        """MemoryProvider should be in extensions.__all__.

        GitHub Issue: #114
        ADR Reference: ADR-005 (Module Exports)
        """
        import luminescent_cluster.extensions as extensions

        assert "MemoryProvider" in extensions.__all__

    def test_response_filter_in_extensions_all(self):
        """ResponseFilter should be in extensions.__all__.

        GitHub Issue: #114
        ADR Reference: ADR-005 (Module Exports)
        """
        import luminescent_cluster.extensions as extensions

        assert "ResponseFilter" in extensions.__all__

    def test_memory_provider_version_in_extensions_all(self):
        """MEMORY_PROVIDER_VERSION should be in extensions.__all__.

        GitHub Issue: #114
        ADR Reference: ADR-005 (Module Exports)
        """
        import luminescent_cluster.extensions as extensions

        assert "MEMORY_PROVIDER_VERSION" in extensions.__all__
