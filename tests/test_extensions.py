"""
Tests for the extension system (ADR-005).

These tests verify that the extension system:
1. Provides thread-safe singleton registry
2. Allows extension injection at startup
3. Works gracefully without extensions (OSS mode)
4. Supports all defined protocols
5. Enables testing with mock implementations
"""

import os
import sys
import threading
from datetime import datetime
from typing import Optional
from unittest.mock import MagicMock, patch
import pytest

from src.extensions import (
    ExtensionRegistry,
    TenantProvider,
    UsageTracker,
    AuditLogger,
)


class TestExtensionRegistry:
    """Test suite for ExtensionRegistry singleton."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    # ========================================
    # Test: Singleton Pattern
    # ========================================
    def test_get_returns_singleton_instance(self):
        """ExtensionRegistry.get() should return the same instance."""
        registry1 = ExtensionRegistry.get()
        registry2 = ExtensionRegistry.get()

        assert registry1 is registry2, "Should return same singleton instance"

    def test_reset_clears_singleton(self):
        """ExtensionRegistry.reset() should clear the singleton."""
        registry1 = ExtensionRegistry.get()
        ExtensionRegistry.reset()
        registry2 = ExtensionRegistry.get()

        assert registry1 is not registry2, "Reset should create new instance"

    def test_singleton_is_thread_safe(self):
        """Singleton initialization should be thread-safe."""
        results = []
        errors = []

        def get_registry():
            try:
                registry = ExtensionRegistry.get()
                results.append(id(registry))
            except Exception as e:
                errors.append(e)

        # Create multiple threads that all try to get the registry
        threads = [threading.Thread(target=get_registry) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"No errors should occur: {errors}"
        assert len(set(results)) == 1, "All threads should get the same instance"

    # ========================================
    # Test: Default State (OSS Mode)
    # ========================================
    def test_default_extensions_are_none(self):
        """All extensions should default to None (OSS mode)."""
        registry = ExtensionRegistry.get()

        assert registry.tenant_provider is None
        assert registry.usage_tracker is None
        assert registry.audit_logger is None

    def test_default_mode_is_oss(self):
        """Default mode should be 'oss' when no extensions registered."""
        registry = ExtensionRegistry.get()
        status = registry.get_status()

        assert status["mode"] == "oss"
        assert status["tenant_provider"] is False
        assert status["usage_tracker"] is False
        assert status["audit_logger"] is False

    def test_is_multi_tenant_false_by_default(self):
        """is_multi_tenant() should be False when no provider registered."""
        registry = ExtensionRegistry.get()
        assert registry.is_multi_tenant() is False

    def test_is_metered_false_by_default(self):
        """is_metered() should be False when no tracker registered."""
        registry = ExtensionRegistry.get()
        assert registry.is_metered() is False

    def test_is_audited_false_by_default(self):
        """is_audited() should be False when no logger registered."""
        registry = ExtensionRegistry.get()
        assert registry.is_audited() is False

    # ========================================
    # Test: Extension Registration
    # ========================================
    def test_register_tenant_provider(self):
        """Should allow registering a TenantProvider."""
        registry = ExtensionRegistry.get()
        mock_provider = MagicMock(spec=TenantProvider)

        registry.tenant_provider = mock_provider

        assert registry.tenant_provider is mock_provider
        assert registry.is_multi_tenant() is True
        assert registry.get_status()["tenant_provider"] is True

    def test_register_usage_tracker(self):
        """Should allow registering a UsageTracker."""
        registry = ExtensionRegistry.get()
        mock_tracker = MagicMock(spec=UsageTracker)

        registry.usage_tracker = mock_tracker

        assert registry.usage_tracker is mock_tracker
        assert registry.is_metered() is True
        assert registry.get_status()["usage_tracker"] is True

    def test_register_audit_logger(self):
        """Should allow registering an AuditLogger."""
        registry = ExtensionRegistry.get()
        mock_logger = MagicMock(spec=AuditLogger)

        registry.audit_logger = mock_logger

        assert registry.audit_logger is mock_logger
        assert registry.is_audited() is True
        assert registry.get_status()["audit_logger"] is True

    def test_mode_becomes_cloud_with_any_extension(self):
        """Mode should be 'cloud' when any extension is registered."""
        registry = ExtensionRegistry.get()

        # Register just one extension
        registry.tenant_provider = MagicMock(spec=TenantProvider)

        assert registry.get_status()["mode"] == "cloud"

    def test_register_multiple_extensions(self):
        """Should allow registering multiple extensions."""
        registry = ExtensionRegistry.get()

        registry.tenant_provider = MagicMock(spec=TenantProvider)
        registry.usage_tracker = MagicMock(spec=UsageTracker)
        registry.audit_logger = MagicMock(spec=AuditLogger)

        status = registry.get_status()
        assert status["tenant_provider"] is True
        assert status["usage_tracker"] is True
        assert status["audit_logger"] is True
        assert status["mode"] == "cloud"


class TestTenantProviderProtocol:
    """Test suite for TenantProvider protocol usage."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    @pytest.fixture
    def mock_tenant_provider(self):
        """Create a mock TenantProvider."""
        provider = MagicMock()
        provider.get_tenant_id.return_value = "tenant-123"
        provider.get_tenant_filter.return_value = {"tenant_id": {"$eq": "tenant-123"}}
        provider.validate_tenant_access.return_value = True
        return provider

    # ========================================
    # Test: TenantProvider Interface
    # ========================================
    def test_get_tenant_id_from_context(self, mock_tenant_provider):
        """TenantProvider should extract tenant ID from request context."""
        registry = ExtensionRegistry.get()
        registry.tenant_provider = mock_tenant_provider

        context = {"x-tenant-id": "tenant-123", "user_id": "user-456"}
        tenant_id = registry.tenant_provider.get_tenant_id(context)

        assert tenant_id == "tenant-123"
        mock_tenant_provider.get_tenant_id.assert_called_once_with(context)

    def test_get_tenant_filter(self, mock_tenant_provider):
        """TenantProvider should return Pixeltable-compatible filter."""
        registry = ExtensionRegistry.get()
        registry.tenant_provider = mock_tenant_provider

        filter_clause = registry.tenant_provider.get_tenant_filter("tenant-123")

        assert filter_clause == {"tenant_id": {"$eq": "tenant-123"}}
        mock_tenant_provider.get_tenant_filter.assert_called_once_with("tenant-123")

    def test_validate_tenant_access(self, mock_tenant_provider):
        """TenantProvider should validate user access to resources."""
        registry = ExtensionRegistry.get()
        registry.tenant_provider = mock_tenant_provider

        allowed = registry.tenant_provider.validate_tenant_access(
            "tenant-123", "user-456", "knowledge_base"
        )

        assert allowed is True
        mock_tenant_provider.validate_tenant_access.assert_called_once_with(
            "tenant-123", "user-456", "knowledge_base"
        )

    def test_graceful_handling_without_provider(self):
        """Code should handle missing TenantProvider gracefully."""
        registry = ExtensionRegistry.get()

        # Simulate OSS usage pattern
        tenant_filter = {}
        if registry.tenant_provider:
            tenant_id = registry.tenant_provider.get_tenant_id({})
            tenant_filter = registry.tenant_provider.get_tenant_filter(tenant_id)

        # Should not crash, filter should be empty
        assert tenant_filter == {}


class TestUsageTrackerProtocol:
    """Test suite for UsageTracker protocol usage."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    @pytest.fixture
    def mock_usage_tracker(self):
        """Create a mock UsageTracker."""
        tracker = MagicMock()
        tracker.check_quota.return_value = (True, None)
        tracker.get_usage_summary.return_value = {
            "total_tokens": 1000,
            "total_queries": 50,
            "quota_remaining": 9000,
        }
        return tracker

    # ========================================
    # Test: UsageTracker Interface
    # ========================================
    def test_track_usage_event(self, mock_usage_tracker):
        """UsageTracker should record usage events."""
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        registry.usage_tracker.track(
            operation="semantic_search",
            tokens=150,
            metadata={"tenant_id": "tenant-123", "latency_ms": 45},
        )

        mock_usage_tracker.track.assert_called_once_with(
            operation="semantic_search",
            tokens=150,
            metadata={"tenant_id": "tenant-123", "latency_ms": 45},
        )

    def test_check_quota_allowed(self, mock_usage_tracker):
        """UsageTracker should check quota and return allowed status."""
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        allowed, reason = registry.usage_tracker.check_quota("tenant-123", "query")

        assert allowed is True
        assert reason is None

    def test_check_quota_exceeded(self, mock_usage_tracker):
        """UsageTracker should return reason when quota exceeded."""
        mock_usage_tracker.check_quota.return_value = (
            False,
            "Monthly token limit exceeded",
        )
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        allowed, reason = registry.usage_tracker.check_quota("tenant-123", "query")

        assert allowed is False
        assert reason == "Monthly token limit exceeded"

    def test_get_usage_summary(self, mock_usage_tracker):
        """UsageTracker should return usage summary."""
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        summary = registry.usage_tracker.get_usage_summary("tenant-123")

        assert summary["total_tokens"] == 1000
        assert summary["total_queries"] == 50
        assert summary["quota_remaining"] == 9000

    def test_graceful_handling_without_tracker(self):
        """Code should handle missing UsageTracker gracefully."""
        registry = ExtensionRegistry.get()

        # Simulate OSS usage pattern - no tracking in OSS mode
        if registry.usage_tracker:
            registry.usage_tracker.track("query", 100, {})

        # Should not crash
        assert True


class TestAuditLoggerProtocol:
    """Test suite for AuditLogger protocol usage."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    @pytest.fixture
    def mock_audit_logger(self):
        """Create a mock AuditLogger."""
        return MagicMock()

    # ========================================
    # Test: AuditLogger Interface
    # ========================================
    def test_log_event(self, mock_audit_logger):
        """AuditLogger should log auditable events."""
        registry = ExtensionRegistry.get()
        registry.audit_logger = mock_audit_logger

        registry.audit_logger.log_event(
            event_type="data_access",
            actor="user-123",
            resource="knowledge_base:acme-corp",
            action="search",
            outcome="success",
            details={"query": "authentication flow", "results_count": 5},
        )

        mock_audit_logger.log_event.assert_called_once_with(
            event_type="data_access",
            actor="user-123",
            resource="knowledge_base:acme-corp",
            action="search",
            outcome="success",
            details={"query": "authentication flow", "results_count": 5},
        )

    def test_log_security_event(self, mock_audit_logger):
        """AuditLogger should log security events."""
        registry = ExtensionRegistry.get()
        registry.audit_logger = mock_audit_logger

        registry.audit_logger.log_security_event(
            event_type="auth_failure",
            severity="warning",
            message="Multiple failed login attempts",
            details={"user_id": "user-123", "attempts": 5},
        )

        mock_audit_logger.log_security_event.assert_called_once_with(
            event_type="auth_failure",
            severity="warning",
            message="Multiple failed login attempts",
            details={"user_id": "user-123", "attempts": 5},
        )

    def test_graceful_handling_without_logger(self):
        """Code should handle missing AuditLogger gracefully."""
        registry = ExtensionRegistry.get()

        # Simulate OSS usage pattern - no auditing in OSS mode
        if registry.audit_logger:
            registry.audit_logger.log_event(
                event_type="test",
                actor="user",
                resource="resource",
                action="action",
                outcome="success",
            )

        # Should not crash
        assert True


class TestExtensionIntegration:
    """Integration tests for extension system."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    # ========================================
    # Test: Realistic Usage Patterns
    # ========================================
    def test_oss_query_pattern(self):
        """Simulate OSS query handling without extensions."""
        registry = ExtensionRegistry.get()

        # OSS query handler pattern
        def handle_query(query: str, context: dict) -> dict:
            tenant_filter = {}
            if registry.tenant_provider:
                tenant_id = registry.tenant_provider.get_tenant_id(context)
                tenant_filter = registry.tenant_provider.get_tenant_filter(tenant_id)

            # Simulate query execution
            result = {"query": query, "filter": tenant_filter, "results": []}

            if registry.usage_tracker:
                registry.usage_tracker.track("query", len(query), context)

            return result

        # Execute in OSS mode
        result = handle_query("test query", {})

        assert result["filter"] == {}
        assert result["query"] == "test query"

    def test_cloud_query_pattern(self):
        """Simulate cloud query handling with all extensions."""
        registry = ExtensionRegistry.get()

        # Register extensions
        mock_tenant = MagicMock()
        mock_tenant.get_tenant_id.return_value = "acme-corp"
        mock_tenant.get_tenant_filter.return_value = {"tenant_id": {"$eq": "acme-corp"}}

        mock_tracker = MagicMock()
        mock_tracker.check_quota.return_value = (True, None)

        mock_audit = MagicMock()

        registry.tenant_provider = mock_tenant
        registry.usage_tracker = mock_tracker
        registry.audit_logger = mock_audit

        # Cloud query handler pattern
        def handle_query(query: str, context: dict) -> dict:
            # Check quota first
            if registry.usage_tracker:
                allowed, reason = registry.usage_tracker.check_quota(
                    context.get("tenant_id", "unknown"), "query"
                )
                if not allowed:
                    raise PermissionError(reason)

            # Apply tenant isolation
            tenant_filter = {}
            if registry.tenant_provider:
                tenant_id = registry.tenant_provider.get_tenant_id(context)
                tenant_filter = registry.tenant_provider.get_tenant_filter(tenant_id)

            # Simulate query execution
            result = {"query": query, "filter": tenant_filter, "results": []}

            # Track usage
            if registry.usage_tracker:
                registry.usage_tracker.track("query", len(query), context)

            # Audit log
            if registry.audit_logger:
                registry.audit_logger.log_event(
                    event_type="data_access",
                    actor=context.get("user_id", "unknown"),
                    resource="knowledge_base",
                    action="search",
                    outcome="success",
                    details={"query": query},
                )

            return result

        # Execute in cloud mode
        context = {"x-tenant-id": "acme-corp", "user_id": "user-123", "tenant_id": "acme-corp"}
        result = handle_query("test query", context)

        # Verify tenant isolation applied
        assert result["filter"] == {"tenant_id": {"$eq": "acme-corp"}}

        # Verify usage tracked
        mock_tracker.track.assert_called_once()

        # Verify audit logged
        mock_audit.log_event.assert_called_once()

    def test_quota_exceeded_raises_error(self):
        """Cloud mode should raise error when quota exceeded."""
        registry = ExtensionRegistry.get()

        mock_tracker = MagicMock()
        mock_tracker.check_quota.return_value = (False, "Token limit exceeded")
        registry.usage_tracker = mock_tracker

        def handle_query(query: str, context: dict) -> dict:
            if registry.usage_tracker:
                allowed, reason = registry.usage_tracker.check_quota(
                    context.get("tenant_id"), "query"
                )
                if not allowed:
                    raise PermissionError(reason)
            return {"results": []}

        with pytest.raises(PermissionError) as exc_info:
            handle_query("test", {"tenant_id": "acme-corp"})

        assert "Token limit exceeded" in str(exc_info.value)


class TestConcreteImplementations:
    """Test concrete implementation examples for documentation."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_simple_tenant_provider_implementation(self):
        """Demonstrate a simple TenantProvider implementation."""

        class SimpleTenantProvider:
            """Example TenantProvider for testing/documentation."""

            def get_tenant_id(self, request_context: dict) -> Optional[str]:
                return request_context.get("x-tenant-id")

            def get_tenant_filter(self, tenant_id: str) -> dict:
                return {"tenant_id": {"$eq": tenant_id}}

            def validate_tenant_access(
                self, tenant_id: str, user_id: str, resource: str
            ) -> bool:
                return True  # Allow all in test

        registry = ExtensionRegistry.get()
        registry.tenant_provider = SimpleTenantProvider()

        # Test the implementation
        ctx = {"x-tenant-id": "test-tenant"}
        tenant_id = registry.tenant_provider.get_tenant_id(ctx)
        filter_clause = registry.tenant_provider.get_tenant_filter(tenant_id)

        assert tenant_id == "test-tenant"
        assert filter_clause == {"tenant_id": {"$eq": "test-tenant"}}

    def test_simple_usage_tracker_implementation(self):
        """Demonstrate a simple UsageTracker implementation."""

        class SimpleUsageTracker:
            """Example UsageTracker for testing/documentation."""

            def __init__(self):
                self.events = []
                self.quotas = {}  # tenant_id -> remaining tokens

            def track(self, operation: str, tokens: int, metadata: dict) -> None:
                self.events.append({
                    "operation": operation,
                    "tokens": tokens,
                    "metadata": metadata,
                })

            def check_quota(self, tenant_id: str, operation: str) -> tuple[bool, Optional[str]]:
                remaining = self.quotas.get(tenant_id, 1000000)  # Default 1M
                if remaining <= 0:
                    return (False, "Quota exceeded")
                return (True, None)

            def get_usage_summary(
                self,
                tenant_id: str,
                start_date: Optional[datetime] = None,
                end_date: Optional[datetime] = None,
            ) -> dict:
                tenant_events = [e for e in self.events if e["metadata"].get("tenant_id") == tenant_id]
                return {
                    "total_tokens": sum(e["tokens"] for e in tenant_events),
                    "total_queries": len(tenant_events),
                }

        registry = ExtensionRegistry.get()
        tracker = SimpleUsageTracker()
        tracker.quotas["test-tenant"] = 1000
        registry.usage_tracker = tracker

        # Test the implementation
        registry.usage_tracker.track(
            "query", 100, {"tenant_id": "test-tenant"}
        )
        registry.usage_tracker.track(
            "query", 50, {"tenant_id": "test-tenant"}
        )

        summary = registry.usage_tracker.get_usage_summary("test-tenant")
        assert summary["total_tokens"] == 150
        assert summary["total_queries"] == 2

        allowed, _ = registry.usage_tracker.check_quota("test-tenant", "query")
        assert allowed is True
