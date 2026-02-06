"""
Extension point system for Luminescent Cluster.

This module provides a Protocol/Registry pattern for extending core functionality
without tight coupling. The private luminescent-cloud repo injects implementations
at startup; the public OSS repo works standalone with no-op defaults.

See ADR-005: Repository Organization Strategy for design rationale.

Usage (OSS - standalone):
    # Core code checks registry, gets None, continues without extension
    from luminescent_cluster.extensions import ExtensionRegistry
    registry = ExtensionRegistry.get()
    if registry.tenant_provider:
        # Multi-tenancy logic (never runs in OSS)
        pass

Usage (Cloud - with extensions):
    # At startup, cloud repo injects implementations
    from luminescent_cluster.extensions import ExtensionRegistry
    from cloud.extensions import CloudTenantProvider, StripeUsageTracker

    registry = ExtensionRegistry.get()
    registry.tenant_provider = CloudTenantProvider()
    registry.usage_tracker = StripeUsageTracker()
"""

from .protocols import (
    # Version constants (ADR-007)
    TENANT_PROVIDER_VERSION,
    USAGE_TRACKER_VERSION,
    AUDIT_LOGGER_VERSION,
    CHATBOT_AUTH_PROVIDER_VERSION,
    CHATBOT_RATE_LIMITER_VERSION,
    CHATBOT_ACCESS_CONTROLLER_VERSION,
    CONTEXT_STORE_VERSION,
    MEMORY_PROVIDER_VERSION,
    # Core protocols
    TenantProvider,
    UsageTracker,
    AuditLogger,
    # Chatbot protocols (ADR-006)
    ChatbotAuthProvider,
    ChatbotRateLimiter,
    ChatbotAccessController,
    # Context protocol (ADR-007)
    ContextStore,
    # Memory protocols (ADR-003)
    MemoryProvider,
    ResponseFilter,
)
from .registry import ExtensionRegistry

__all__ = [
    # Version constants (ADR-007)
    "TENANT_PROVIDER_VERSION",
    "USAGE_TRACKER_VERSION",
    "AUDIT_LOGGER_VERSION",
    "CHATBOT_AUTH_PROVIDER_VERSION",
    "CHATBOT_RATE_LIMITER_VERSION",
    "CHATBOT_ACCESS_CONTROLLER_VERSION",
    "CONTEXT_STORE_VERSION",
    "MEMORY_PROVIDER_VERSION",
    # Core protocols
    "TenantProvider",
    "UsageTracker",
    "AuditLogger",
    # Chatbot protocols (ADR-006)
    "ChatbotAuthProvider",
    "ChatbotRateLimiter",
    "ChatbotAccessController",
    # Context protocol (ADR-007)
    "ContextStore",
    # Memory protocols (ADR-003)
    "MemoryProvider",
    "ResponseFilter",
    # Registry
    "ExtensionRegistry",
]
