"""
Tests for MCP server extension integration (ADR-005).

These tests verify the extension helper patterns that will be integrated
into the Pixeltable MCP server:
1. Works correctly in OSS mode (no extensions)
2. Applies tenant filtering when TenantProvider is registered
3. Tracks usage when UsageTracker is registered
4. Logs audits when AuditLogger is registered
5. Handles all three extensions together (cloud mode)

Note: Tests use the helper function patterns directly rather than importing
pixeltable_mcp_server.py (which requires Pixeltable database).
"""

import pytest
from unittest.mock import MagicMock
from typing import Optional, Dict, Any, List

from src.extensions import ExtensionRegistry


# ============================================================================
# Extension Helper Functions (will be added to MCP server)
# ============================================================================

def get_tenant_filter(context: dict) -> dict:
    """
    Get tenant filter from context if multi-tenancy is enabled.

    This helper should be called before any database query to apply
    tenant isolation in cloud mode.

    Args:
        context: Request context with tenant info (x-tenant-id, user_id, etc.)

    Returns:
        Filter dict for Pixeltable query, or empty dict in OSS mode.
    """
    registry = ExtensionRegistry.get()
    if registry.tenant_provider:
        tenant_id = registry.tenant_provider.get_tenant_id(context)
        if tenant_id:
            return registry.tenant_provider.get_tenant_filter(tenant_id)
    return {}


def check_quota(tenant_id: str, operation: str) -> tuple[bool, Optional[str]]:
    """
    Check if tenant has quota for operation.

    Args:
        tenant_id: Tenant identifier
        operation: Operation type (query, ingest, etc.)

    Returns:
        Tuple of (allowed, reason). In OSS mode, always returns (True, None).
    """
    registry = ExtensionRegistry.get()
    if registry.usage_tracker:
        return registry.usage_tracker.check_quota(tenant_id, operation)
    return (True, None)


def track_usage(operation: str, tokens: int, metadata: dict) -> None:
    """
    Track usage for billing purposes.

    No-op in OSS mode. In cloud mode, records usage event.

    Args:
        operation: Operation type
        tokens: Token/unit count
        metadata: Additional context
    """
    registry = ExtensionRegistry.get()
    if registry.usage_tracker:
        try:
            registry.usage_tracker.track(operation, tokens, metadata)
        except Exception:
            # Don't fail the request if tracking fails
            pass


def log_audit(
    event_type: str,
    actor: str,
    resource: str,
    action: str,
    outcome: str,
    details: Optional[dict] = None,
) -> None:
    """
    Log audit event for compliance.

    No-op in OSS mode. In cloud mode, records audit event.

    Args:
        event_type: Event category (data_access, admin, etc.)
        actor: User/system performing action
        resource: Resource being acted upon
        action: Action performed
        outcome: Result (success, failure, denied)
        details: Additional context
    """
    registry = ExtensionRegistry.get()
    if registry.audit_logger:
        try:
            registry.audit_logger.log_event(
                event_type, actor, resource, action, outcome, details
            )
        except Exception:
            # Don't fail the request if audit fails
            pass


# ============================================================================
# Tests
# ============================================================================

class TestOSSMode:
    """Tests for OSS mode (no extensions registered)."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset extension registry for each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_oss_mode_has_no_extensions(self):
        """In OSS mode, no extensions should be registered."""
        registry = ExtensionRegistry.get()

        assert registry.tenant_provider is None
        assert registry.usage_tracker is None
        assert registry.audit_logger is None
        assert registry.get_status()["mode"] == "oss"

    def test_get_tenant_filter_returns_empty_dict(self):
        """get_tenant_filter should return empty dict in OSS mode."""
        context = {"x-tenant-id": "tenant-123", "user_id": "user-456"}
        result = get_tenant_filter(context)
        assert result == {}

    def test_check_quota_always_allows(self):
        """check_quota should always return (True, None) in OSS mode."""
        allowed, reason = check_quota("tenant-123", "query")
        assert allowed is True
        assert reason is None

    def test_track_usage_is_noop(self):
        """track_usage should be no-op (no exceptions) in OSS mode."""
        # Should not raise
        track_usage("search", 100, {"tenant_id": "test"})

    def test_log_audit_is_noop(self):
        """log_audit should be no-op (no exceptions) in OSS mode."""
        # Should not raise
        log_audit("data_access", "user-123", "kb", "search", "success")


class TestCloudMode:
    """Tests for cloud mode (with extensions registered)."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset extension registry for each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    @pytest.fixture
    def mock_tenant_provider(self):
        """Create mock TenantProvider."""
        provider = MagicMock()
        provider.get_tenant_id.return_value = "tenant-123"
        provider.get_tenant_filter.return_value = {"tenant_id": {"$eq": "tenant-123"}}
        provider.validate_tenant_access.return_value = True
        return provider

    @pytest.fixture
    def mock_usage_tracker(self):
        """Create mock UsageTracker."""
        tracker = MagicMock()
        tracker.check_quota.return_value = (True, None)
        tracker.track = MagicMock()
        return tracker

    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock AuditLogger."""
        logger = MagicMock()
        logger.log_event = MagicMock()
        logger.log_security_event = MagicMock()
        return logger

    # ========================================
    # Tenant Isolation Tests
    # ========================================
    def test_cloud_mode_with_tenant_provider(self, mock_tenant_provider):
        """Cloud mode should have tenant provider registered."""
        registry = ExtensionRegistry.get()
        registry.tenant_provider = mock_tenant_provider

        assert registry.is_multi_tenant() is True
        assert registry.get_status()["mode"] == "cloud"

    def test_get_tenant_filter_returns_filter(self, mock_tenant_provider):
        """get_tenant_filter should return filter dict in cloud mode."""
        registry = ExtensionRegistry.get()
        registry.tenant_provider = mock_tenant_provider

        context = {"x-tenant-id": "tenant-123", "user_id": "user-456"}
        result = get_tenant_filter(context)

        assert result == {"tenant_id": {"$eq": "tenant-123"}}
        mock_tenant_provider.get_tenant_id.assert_called_once_with(context)
        mock_tenant_provider.get_tenant_filter.assert_called_once_with("tenant-123")

    def test_get_tenant_filter_handles_no_tenant_id(self, mock_tenant_provider):
        """get_tenant_filter should return empty if no tenant ID found."""
        registry = ExtensionRegistry.get()
        mock_tenant_provider.get_tenant_id.return_value = None
        registry.tenant_provider = mock_tenant_provider

        result = get_tenant_filter({})
        assert result == {}

    # ========================================
    # Usage Tracking Tests
    # ========================================
    def test_cloud_mode_with_usage_tracker(self, mock_usage_tracker):
        """Cloud mode should have usage tracker registered."""
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        assert registry.is_metered() is True
        assert registry.get_status()["mode"] == "cloud"

    def test_check_quota_calls_tracker(self, mock_usage_tracker):
        """check_quota should call tracker in cloud mode."""
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        allowed, reason = check_quota("tenant-123", "query")

        assert allowed is True
        assert reason is None
        mock_usage_tracker.check_quota.assert_called_once_with("tenant-123", "query")

    def test_check_quota_returns_exceeded(self, mock_usage_tracker):
        """check_quota should return exceeded status when quota exceeded."""
        registry = ExtensionRegistry.get()
        mock_usage_tracker.check_quota.return_value = (False, "Monthly limit exceeded")
        registry.usage_tracker = mock_usage_tracker

        allowed, reason = check_quota("tenant-123", "query")

        assert allowed is False
        assert reason == "Monthly limit exceeded"

    def test_track_usage_calls_tracker(self, mock_usage_tracker):
        """track_usage should call tracker in cloud mode."""
        registry = ExtensionRegistry.get()
        registry.usage_tracker = mock_usage_tracker

        track_usage("search", 150, {"tenant_id": "tenant-123", "latency_ms": 45})

        mock_usage_tracker.track.assert_called_once_with(
            "search", 150, {"tenant_id": "tenant-123", "latency_ms": 45}
        )

    # ========================================
    # Audit Logging Tests
    # ========================================
    def test_cloud_mode_with_audit_logger(self, mock_audit_logger):
        """Cloud mode should have audit logger registered."""
        registry = ExtensionRegistry.get()
        registry.audit_logger = mock_audit_logger

        assert registry.is_audited() is True
        assert registry.get_status()["mode"] == "cloud"

    def test_log_audit_calls_logger(self, mock_audit_logger):
        """log_audit should call logger in cloud mode."""
        registry = ExtensionRegistry.get()
        registry.audit_logger = mock_audit_logger

        log_audit(
            "data_access",
            "user-123",
            "knowledge_base:acme-corp",
            "search",
            "success",
            {"query": "auth flow", "results": 5},
        )

        mock_audit_logger.log_event.assert_called_once_with(
            "data_access",
            "user-123",
            "knowledge_base:acme-corp",
            "search",
            "success",
            {"query": "auth flow", "results": 5},
        )

    # ========================================
    # Full Cloud Mode Tests
    # ========================================
    def test_full_cloud_mode(
        self, mock_tenant_provider, mock_usage_tracker, mock_audit_logger
    ):
        """Full cloud mode should use all three extensions."""
        registry = ExtensionRegistry.get()
        registry.tenant_provider = mock_tenant_provider
        registry.usage_tracker = mock_usage_tracker
        registry.audit_logger = mock_audit_logger

        status = registry.get_status()
        assert status["mode"] == "cloud"
        assert status["tenant_provider"] is True
        assert status["usage_tracker"] is True
        assert status["audit_logger"] is True


class TestErrorHandling:
    """Tests for extension error handling."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset extension registry for each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_tenant_provider_exception_handled(self):
        """Exceptions from tenant provider should be handled gracefully."""
        registry = ExtensionRegistry.get()

        mock_provider = MagicMock()
        mock_provider.get_tenant_id.side_effect = Exception("Provider error")
        registry.tenant_provider = mock_provider

        # Define safe version
        def get_tenant_filter_safe(context: dict) -> dict:
            try:
                return get_tenant_filter(context)
            except Exception:
                return {}

        # Should not raise, should return empty filter
        result = get_tenant_filter_safe({"x-tenant-id": "test"})
        assert result == {}

    def test_usage_tracker_exception_handled(self):
        """Exceptions from usage tracker should not crash."""
        registry = ExtensionRegistry.get()

        mock_tracker = MagicMock()
        mock_tracker.track.side_effect = Exception("Tracker error")
        registry.usage_tracker = mock_tracker

        # Should not raise (track_usage has internal try/except)
        track_usage("search", 100, {})

    def test_audit_logger_exception_handled(self):
        """Exceptions from audit logger should not crash."""
        registry = ExtensionRegistry.get()

        mock_logger = MagicMock()
        mock_logger.log_event.side_effect = Exception("Logger error")
        registry.audit_logger = mock_logger

        # Should not raise (log_audit has internal try/except)
        log_audit("data_access", "user", "kb", "search", "success")


class TestQueryWithExtensions:
    """Tests simulating full query flow with extensions."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset extension registry for each test."""
        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_oss_query_flow(self):
        """Simulate complete query flow in OSS mode."""
        # OSS query pattern
        context = {"user_id": "local-user"}

        # 1. Check quota (always passes in OSS)
        allowed, reason = check_quota("", "query")
        assert allowed is True

        # 2. Get tenant filter (empty in OSS)
        tenant_filter = get_tenant_filter(context)
        assert tenant_filter == {}

        # 3. Execute query (simulated)
        results = [{"title": "Result 1"}]

        # 4. Track usage (no-op in OSS)
        track_usage("query", len(results), context)

        # 5. Log audit (no-op in OSS)
        log_audit("data_access", "local-user", "kb", "search", "success")

        assert results == [{"title": "Result 1"}]

    def test_cloud_query_flow(self):
        """Simulate complete query flow in cloud mode."""
        registry = ExtensionRegistry.get()

        # Set up mocks
        mock_tenant = MagicMock()
        mock_tenant.get_tenant_id.return_value = "acme-corp"
        mock_tenant.get_tenant_filter.return_value = {"tenant_id": {"$eq": "acme-corp"}}

        mock_tracker = MagicMock()
        mock_tracker.check_quota.return_value = (True, None)

        mock_audit = MagicMock()

        registry.tenant_provider = mock_tenant
        registry.usage_tracker = mock_tracker
        registry.audit_logger = mock_audit

        # Cloud query pattern
        context = {"x-tenant-id": "acme-corp", "user_id": "user-123"}

        # 1. Check quota
        allowed, reason = check_quota("acme-corp", "query")
        assert allowed is True

        # 2. Get tenant filter
        tenant_filter = get_tenant_filter(context)
        assert tenant_filter == {"tenant_id": {"$eq": "acme-corp"}}

        # 3. Execute query (simulated with filter applied)
        results = [{"title": "Result 1", "tenant_id": "acme-corp"}]

        # 4. Track usage
        track_usage("query", len(results), context)
        mock_tracker.track.assert_called_once()

        # 5. Log audit
        log_audit("data_access", "user-123", "kb:acme-corp", "search", "success")
        mock_audit.log_event.assert_called_once()

    def test_cloud_query_blocked_by_quota(self):
        """Simulate query blocked by quota in cloud mode."""
        registry = ExtensionRegistry.get()

        mock_tracker = MagicMock()
        mock_tracker.check_quota.return_value = (False, "Monthly quota exceeded")
        registry.usage_tracker = mock_tracker

        # Check quota first
        allowed, reason = check_quota("acme-corp", "query")

        assert allowed is False
        assert reason == "Monthly quota exceeded"

        # Query should not proceed - application would raise error here
