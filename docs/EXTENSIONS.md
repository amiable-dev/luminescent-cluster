# Extension System Developer Guide

This guide explains how to use and implement extensions for Luminescent Cluster.

## Overview

Luminescent Cluster uses a **Protocol/Registry pattern** to support both open-source (OSS) and cloud deployments from the same codebase. Extensions allow the private `luminescent-cloud` repository to inject paid features (multi-tenancy, billing, audit logging) without modifying the public OSS code.

**Design Principles** (from [ADR-005](adrs/ADR-005-repository-organization-strategy.md)):
1. **Composition over Inheritance** - No base classes to subclass
2. **Clean Separation** - OSS code has no concept of tenancy or billing
3. **Graceful Degradation** - OSS works perfectly without any extensions
4. **Testable** - Extensions can be mocked in tests

## Quick Start

### Checking Extension Status

```python
from src.extensions import ExtensionRegistry

registry = ExtensionRegistry.get()

# Check what mode we're in
status = registry.get_status()
# OSS: {'tenant_provider': False, 'usage_tracker': False, 'audit_logger': False, 'mode': 'oss'}
# Cloud: {'tenant_provider': True, 'usage_tracker': True, 'audit_logger': True, 'mode': 'cloud'}

# Helper methods
registry.is_multi_tenant()  # True if tenant_provider registered
registry.is_metered()       # True if usage_tracker registered
registry.is_audited()       # True if audit_logger registered
```

### Using Extensions in Code

Always check if an extension is registered before using it:

```python
from src.extensions import ExtensionRegistry

def handle_query(query: str, context: dict) -> dict:
    registry = ExtensionRegistry.get()

    # Apply tenant isolation (only if multi-tenant)
    tenant_filter = {}
    if registry.tenant_provider:
        tenant_id = registry.tenant_provider.get_tenant_id(context)
        tenant_filter = registry.tenant_provider.get_tenant_filter(tenant_id)

    # Execute query with filter
    results = execute_query(query, tenant_filter)

    # Track usage (only if metered)
    if registry.usage_tracker:
        registry.usage_tracker.track("query", len(query), context)

    # Audit log (only if audited)
    if registry.audit_logger:
        registry.audit_logger.log_event(
            event_type="data_access",
            actor=context.get("user_id", "unknown"),
            resource="knowledge_base",
            action="search",
            outcome="success",
            details={"query": query}
        )

    return results
```

## Extension Protocols

### TenantProvider

Provides multi-tenancy support for the cloud tier.

```python
from typing import Protocol, Optional

class TenantProvider(Protocol):
    def get_tenant_id(self, request_context: dict) -> Optional[str]:
        """Extract tenant ID from request context."""
        ...

    def get_tenant_filter(self, tenant_id: str) -> dict:
        """Return Pixeltable-compatible filter for tenant isolation."""
        ...

    def validate_tenant_access(
        self, tenant_id: str, user_id: str, resource: str
    ) -> bool:
        """Check if user has access to resource within tenant."""
        ...
```

**Example Implementation:**

```python
class CloudTenantProvider:
    def get_tenant_id(self, request_context: dict) -> Optional[str]:
        # Extract from header or JWT
        return request_context.get("x-tenant-id")

    def get_tenant_filter(self, tenant_id: str) -> dict:
        # Pixeltable query filter
        return {"tenant_id": {"$eq": tenant_id}}

    def validate_tenant_access(
        self, tenant_id: str, user_id: str, resource: str
    ) -> bool:
        # Check RBAC permissions
        return self.rbac.check(tenant_id, user_id, resource)
```

### UsageTracker

Provides usage metering for billing and quota enforcement.

```python
from typing import Protocol, Optional
from datetime import datetime

class UsageTracker(Protocol):
    def track(
        self,
        operation: str,
        tokens: int,
        metadata: dict,
    ) -> None:
        """Record a usage event."""
        ...

    def check_quota(
        self,
        tenant_id: str,
        operation: str,
    ) -> tuple[bool, Optional[str]]:
        """Check if tenant has remaining quota."""
        ...

    def get_usage_summary(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Get usage summary for billing."""
        ...
```

**Example Implementation:**

```python
import stripe

class StripeUsageTracker:
    def __init__(self, stripe_key: str):
        stripe.api_key = stripe_key

    def track(self, operation: str, tokens: int, metadata: dict) -> None:
        # Fire-and-forget to avoid blocking
        stripe.usage_records.create(
            subscription_item=metadata.get("subscription_item_id"),
            quantity=tokens,
            timestamp=int(time.time()),
        )

    def check_quota(self, tenant_id: str, operation: str) -> tuple[bool, Optional[str]]:
        usage = self.get_current_usage(tenant_id)
        limit = self.get_quota_limit(tenant_id)

        if usage >= limit:
            return (False, f"Monthly {operation} quota exceeded ({usage}/{limit})")
        return (True, None)

    def get_usage_summary(self, tenant_id: str, start_date=None, end_date=None) -> dict:
        # Query Stripe for usage records
        return {
            "total_tokens": self.get_token_count(tenant_id, start_date, end_date),
            "total_queries": self.get_query_count(tenant_id, start_date, end_date),
            "quota_remaining": self.get_quota_limit(tenant_id) - self.get_current_usage(tenant_id),
        }
```

### AuditLogger

Provides enterprise audit logging for compliance (SOC2, HIPAA, etc.).

```python
from typing import Protocol, Optional

class AuditLogger(Protocol):
    def log_event(
        self,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        outcome: str,
        details: Optional[dict] = None,
    ) -> None:
        """Record an auditable event."""
        ...

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        """Record a security event."""
        ...
```

**Example Implementation:**

```python
import logging
import json

class CloudAuditLogger:
    def __init__(self, audit_endpoint: str):
        self.endpoint = audit_endpoint
        self.logger = logging.getLogger("audit")

    def log_event(
        self,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        outcome: str,
        details: Optional[dict] = None,
    ) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "actor": actor,
            "resource": resource,
            "action": action,
            "outcome": outcome,
            "details": details or {},
        }

        # Send to centralized audit system
        self._send_to_audit_system(event)

        # Also log locally for debugging
        self.logger.info(json.dumps(event))

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "details": details or {},
        }

        self._send_to_security_system(event)

        if severity == "critical":
            self._alert_security_team(event)
```

## Registering Extensions

Extensions are registered at application startup, typically in the cloud repository's entry point:

```python
# luminescent-cloud/cloud/startup.py

from luminescent_cluster.extensions import ExtensionRegistry
from cloud.extensions.multi_tenant import CloudTenantProvider
from cloud.extensions.stripe_tracker import StripeUsageTracker
from cloud.extensions.audit_logger import CloudAuditLogger

def init_cloud_extensions():
    """Initialize all cloud extensions at startup."""
    registry = ExtensionRegistry.get()

    # Multi-tenancy
    registry.tenant_provider = CloudTenantProvider(
        config=load_tenant_config()
    )

    # Usage tracking
    registry.usage_tracker = StripeUsageTracker(
        stripe_key=os.environ["STRIPE_API_KEY"]
    )

    # Audit logging
    registry.audit_logger = CloudAuditLogger(
        endpoint=os.environ["AUDIT_ENDPOINT"]
    )

    print(f"Extensions initialized: {registry.get_status()}")
```

## Testing

### Testing Without Extensions (OSS Mode)

```python
import pytest
from src.extensions import ExtensionRegistry

@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry for each test."""
    ExtensionRegistry.reset()
    yield
    ExtensionRegistry.reset()

def test_query_without_tenant_filter():
    """Test that queries work without tenant provider."""
    registry = ExtensionRegistry.get()

    # No extensions registered
    assert registry.is_multi_tenant() is False

    # Query should work with empty filter
    filter = {}
    if registry.tenant_provider:
        filter = registry.tenant_provider.get_tenant_filter("tenant-123")

    assert filter == {}  # No filtering in OSS mode
```

### Testing With Mock Extensions

```python
from unittest.mock import MagicMock

def test_query_with_tenant_filter():
    """Test that tenant filter is applied when provider registered."""
    registry = ExtensionRegistry.get()

    # Register mock provider
    mock_provider = MagicMock()
    mock_provider.get_tenant_id.return_value = "tenant-123"
    mock_provider.get_tenant_filter.return_value = {"tenant_id": {"$eq": "tenant-123"}}
    registry.tenant_provider = mock_provider

    # Now tenant filtering should apply
    assert registry.is_multi_tenant() is True

    context = {"x-tenant-id": "tenant-123"}
    tenant_id = registry.tenant_provider.get_tenant_id(context)
    filter = registry.tenant_provider.get_tenant_filter(tenant_id)

    assert filter == {"tenant_id": {"$eq": "tenant-123"}}
```

### Testing Quota Enforcement

```python
def test_quota_exceeded_raises_error():
    """Test that quota exceeded blocks operations."""
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
```

## Thread Safety

The `ExtensionRegistry` is thread-safe:

- Singleton initialization uses double-checked locking
- Extension assignment is atomic (single reference assignment)
- Extensions themselves must be thread-safe if used concurrently

```python
import threading

def test_singleton_thread_safety():
    """Registry should be thread-safe."""
    results = []

    def get_registry():
        registry = ExtensionRegistry.get()
        results.append(id(registry))

    threads = [threading.Thread(target=get_registry) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should get the same instance
    assert len(set(results)) == 1
```

## Versioning

Extension protocols follow semantic versioning:

- **MAJOR**: Breaking changes to method signatures
- **MINOR**: New optional methods with defaults
- **PATCH**: Documentation or type hint fixes

Current versions:
- `TenantProvider`: 1.0.0
- `UsageTracker`: 1.0.0
- `AuditLogger`: 1.0.0

## Related Documentation

- [ADR-005: Repository Organization Strategy](adrs/ADR-005-repository-organization-strategy.md)
- [ADR-004: Monetization Strategy](adrs/ADR-004-monetization-strategy.md)
- [ADR-003: Project Intent](adrs/ADR-003-project-intent-persistent-context.md)
