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
Extension point protocols for Luminescent Cluster.

These Protocol classes define the interfaces that the private luminescent-cloud
repo can implement to extend core functionality. The OSS repo defines the contracts;
the cloud repo provides the implementations.

Design Principles (from ADR-005):
1. Composition over inheritance - no base classes to subclass
2. Clean separation - OSS code has no concept of tenancy or billing
3. Testable - protocols can be mocked in OSS tests
4. Versioned - protocols follow semantic versioning

Protocol Versioning:
- MAJOR: Breaking changes to method signatures
- MINOR: New optional methods with defaults
- PATCH: Documentation or type hint fixes
"""

from typing import Protocol, Optional, Any
from datetime import datetime


class TenantProvider(Protocol):
    """
    Extension point for multi-tenancy support.

    Implementations resolve tenant identity from request context and provide
    database filters for tenant isolation.

    OSS Behavior: Not registered; queries run without tenant filtering.
    Cloud Behavior: Resolves tenant from JWT/session, filters all queries.

    Version: 1.0.0
    """

    def get_tenant_id(self, request_context: dict) -> Optional[str]:
        """
        Extract tenant identifier from request context.

        Args:
            request_context: Dict containing headers, auth info, session data.
                             Expected keys: 'x-tenant-id', 'authorization', 'user_id'

        Returns:
            Tenant ID string, or None if not in multi-tenant context.

        Example:
            ctx = {"x-tenant-id": "acme-corp", "user_id": "user-123"}
            tenant_id = provider.get_tenant_id(ctx)  # "acme-corp"
        """
        ...

    def get_tenant_filter(self, tenant_id: str) -> dict:
        """
        Generate database filter clause for tenant isolation.

        Args:
            tenant_id: The tenant identifier from get_tenant_id()

        Returns:
            Filter dict compatible with Pixeltable queries.
            Example: {"tenant_id": {"$eq": "acme-corp"}}

        Note:
            Filter format must match Pixeltable's query syntax.
        """
        ...

    def validate_tenant_access(
        self, tenant_id: str, user_id: str, resource: str
    ) -> bool:
        """
        Check if user has access to resource within tenant.

        Args:
            tenant_id: The tenant context
            user_id: The user requesting access
            resource: Resource identifier (e.g., "knowledge_base", "settings")

        Returns:
            True if access allowed, False otherwise.

        Note:
            This is optional; implementations may return True always
            and handle RBAC separately.
        """
        ...


class UsageTracker(Protocol):
    """
    Extension point for usage metering and billing.

    Tracks API operations for quota enforcement and billing integration.

    OSS Behavior: Not registered; no usage tracking occurs.
    Cloud Behavior: Tracks tokens, queries, storage for billing.

    Version: 1.0.0
    """

    def track(
        self,
        operation: str,
        tokens: int,
        metadata: dict,
    ) -> None:
        """
        Record a usage event for billing/quota purposes.

        Args:
            operation: Type of operation (e.g., "query", "ingest", "search")
            tokens: Token count or unit count for the operation
            metadata: Additional context for the event
                      Expected keys: 'tenant_id', 'user_id', 'model', 'latency_ms'

        Note:
            Implementations should be non-blocking (async or fire-and-forget)
            to avoid impacting request latency.

        Example:
            tracker.track(
                operation="semantic_search",
                tokens=150,
                metadata={
                    "tenant_id": "acme-corp",
                    "user_id": "user-123",
                    "latency_ms": 45,
                    "results_count": 10
                }
            )
        """
        ...

    def check_quota(
        self,
        tenant_id: str,
        operation: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if tenant has remaining quota for operation.

        Args:
            tenant_id: The tenant to check
            operation: The operation type to check quota for

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If not allowed, reason explains why (e.g., "Monthly token limit exceeded")

        Example:
            allowed, reason = tracker.check_quota("acme-corp", "query")
            if not allowed:
                raise QuotaExceededError(reason)
        """
        ...

    def get_usage_summary(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get usage summary for a tenant within date range.

        Args:
            tenant_id: The tenant to query
            start_date: Start of period (default: current billing period start)
            end_date: End of period (default: now)

        Returns:
            Dict with usage metrics:
            {
                "total_tokens": int,
                "total_queries": int,
                "total_ingests": int,
                "storage_bytes": int,
                "quota_remaining": int,
                "period_start": datetime,
                "period_end": datetime
            }
        """
        ...


class AuditLogger(Protocol):
    """
    Extension point for enterprise audit logging.

    Records security-relevant events for compliance (SOC2, HIPAA, etc.).

    OSS Behavior: Not registered; no audit logging.
    Cloud Behavior: Logs to centralized audit system with retention.

    Version: 1.0.0
    """

    def log_event(
        self,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        outcome: str,
        details: Optional[dict] = None,
    ) -> None:
        """
        Record an auditable event.

        Args:
            event_type: Category of event (e.g., "auth", "data_access", "admin")
            actor: Who performed the action (user_id or system identifier)
            resource: What was acted upon (e.g., "knowledge_base:kb-123")
            action: What was done (e.g., "read", "write", "delete", "export")
            outcome: Result of action ("success", "failure", "denied")
            details: Additional context for the event

        Example:
            logger.log_event(
                event_type="data_access",
                actor="user-123",
                resource="knowledge_base:acme-corp",
                action="search",
                outcome="success",
                details={
                    "query": "authentication flow",
                    "results_count": 5,
                    "ip_address": "192.168.1.1"
                }
            )
        """
        ...

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        """
        Record a security-specific event (failed auth, suspicious activity).

        Args:
            event_type: Type of security event (e.g., "auth_failure", "rate_limit")
            severity: Severity level ("info", "warning", "critical")
            message: Human-readable description
            details: Additional context

        Example:
            logger.log_security_event(
                event_type="auth_failure",
                severity="warning",
                message="Multiple failed login attempts",
                details={
                    "user_id": "user-123",
                    "attempts": 5,
                    "ip_address": "192.168.1.1"
                }
            )
        """
        ...
