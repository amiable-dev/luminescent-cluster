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
Extension Registry for Luminescent Cluster.

Singleton registry that holds extension implementations. The private
luminescent-cloud repo injects implementations at startup; OSS code
checks the registry and gracefully handles None values.

Design (from ADR-005):
- Registry is a singleton (one per process)
- All extension fields default to None
- OSS code checks `if registry.tenant_provider:` before using
- Cloud code calls `registry.tenant_provider = CloudTenantProvider()` at startup

Thread Safety:
- Registry initialization is thread-safe via class-level lock
- Extension assignment is atomic (single reference assignment)
- Extensions themselves must be thread-safe if used concurrently
"""

from dataclasses import dataclass
from typing import Optional, ClassVar, TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from .protocols import TenantProvider, UsageTracker, AuditLogger


@dataclass
class ExtensionRegistry:
    """
    Central registry for extension point implementations.

    Usage (checking for extensions):
        registry = ExtensionRegistry.get()
        if registry.tenant_provider:
            tenant_id = registry.tenant_provider.get_tenant_id(context)

    Usage (registering extensions - cloud repo only):
        registry = ExtensionRegistry.get()
        registry.tenant_provider = MyTenantProvider()
        registry.usage_tracker = MyUsageTracker()
        registry.audit_logger = MyAuditLogger()

    Attributes:
        tenant_provider: Multi-tenancy support (isolation, filtering)
        usage_tracker: Usage metering for billing/quotas
        audit_logger: Enterprise audit logging for compliance
    """

    # Extension implementations (all optional, default None)
    tenant_provider: Optional["TenantProvider"] = None
    usage_tracker: Optional["UsageTracker"] = None
    audit_logger: Optional["AuditLogger"] = None

    # Singleton management (ClassVars are not dataclass fields)
    _instance: ClassVar[Optional["ExtensionRegistry"]] = None
    _lock: ClassVar[threading.Lock]  # Initialized at module level

    def __post_init__(self):
        """Validate that this is the singleton instance."""
        # This runs after dataclass __init__, used for any setup
        pass

    @classmethod
    def get(cls) -> "ExtensionRegistry":
        """
        Get the singleton ExtensionRegistry instance.

        Thread-safe: Uses double-checked locking pattern.

        Returns:
            The singleton ExtensionRegistry instance.

        Example:
            registry = ExtensionRegistry.get()
            if registry.usage_tracker:
                registry.usage_tracker.track("query", 100, {})
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance (for testing only).

        Warning:
            This should only be used in test fixtures to ensure
            clean state between tests. Never call in production code.

        Example:
            def teardown_function():
                ExtensionRegistry.reset()
        """
        with cls._lock:
            cls._instance = None

    def is_multi_tenant(self) -> bool:
        """
        Check if multi-tenancy is enabled.

        Returns:
            True if a TenantProvider is registered.
        """
        return self.tenant_provider is not None

    def is_metered(self) -> bool:
        """
        Check if usage metering is enabled.

        Returns:
            True if a UsageTracker is registered.
        """
        return self.usage_tracker is not None

    def is_audited(self) -> bool:
        """
        Check if audit logging is enabled.

        Returns:
            True if an AuditLogger is registered.
        """
        return self.audit_logger is not None

    def get_status(self) -> dict:
        """
        Get status of all registered extensions.

        Returns:
            Dict with extension registration status.

        Example:
            >>> ExtensionRegistry.get().get_status()
            {
                "tenant_provider": False,
                "usage_tracker": False,
                "audit_logger": False,
                "mode": "oss"
            }
        """
        has_any = any([
            self.tenant_provider,
            self.usage_tracker,
            self.audit_logger,
        ])

        return {
            "tenant_provider": self.tenant_provider is not None,
            "usage_tracker": self.usage_tracker is not None,
            "audit_logger": self.audit_logger is not None,
            "mode": "cloud" if has_any else "oss",
        }


# Module-level lock for singleton (dataclass field default_factory doesn't work for ClassVar)
ExtensionRegistry._lock = threading.Lock()
