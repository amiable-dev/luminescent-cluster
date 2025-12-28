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

from typing import Protocol, Optional, Any, runtime_checkable
from datetime import datetime


# =============================================================================
# Protocol Version Constants (ADR-007)
# =============================================================================
# These constants enable runtime version validation for cross-repo compatibility.
# Follow SemVer: MAJOR.MINOR.PATCH
# - MAJOR: Breaking changes to method signatures
# - MINOR: New optional methods with defaults
# - PATCH: Documentation or type hint fixes

TENANT_PROVIDER_VERSION = "1.0.0"
USAGE_TRACKER_VERSION = "1.0.0"
AUDIT_LOGGER_VERSION = "1.1.0"  # Bumped for GDPR methods (Issue #73)
CHATBOT_AUTH_PROVIDER_VERSION = "1.0.0"
CHATBOT_RATE_LIMITER_VERSION = "1.0.0"
CHATBOT_ACCESS_CONTROLLER_VERSION = "1.0.0"
CONTEXT_STORE_VERSION = "1.0.0"
RESPONSE_FILTER_VERSION = "1.0.0"


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


@runtime_checkable
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

    def log_gdpr_deletion(
        self,
        user_id: str,
        workspace_id: str,
        items_deleted: dict,
        timestamp: datetime,
    ) -> None:
        """
        Record a GDPR Article 17 deletion event (Right to Erasure).

        This method creates a compliance audit record for user data deletion.
        Must be called after successfully deleting user data.

        Args:
            user_id: User identifier whose data was deleted
            workspace_id: Workspace context for the deletion
            items_deleted: Dict mapping category to count of deleted items
                          e.g., {"conversations": 5, "knowledge": 2}
            timestamp: When the deletion occurred

        Example:
            logger.log_gdpr_deletion(
                user_id="user-123",
                workspace_id="ws-456",
                items_deleted={
                    "conversation_context": 5,
                    "org_knowledge": 2,
                    "meetings": 1,
                    "usage_metrics": 10
                },
                timestamp=datetime.now()
            )

        Note:
            - Do NOT include PII in the log (only counts and IDs)
            - This audit record must be retained for compliance
            - Added in version 1.1.0 (Issue #73)
        """
        ...

    def log_gdpr_export(
        self,
        user_id: str,
        workspace_id: str,
        total_items: int,
        timestamp: datetime,
    ) -> None:
        """
        Record a GDPR Article 20 export event (Data Portability).

        This method creates a compliance audit record for user data export.
        Must be called after successfully exporting user data.

        Args:
            user_id: User identifier whose data was exported
            workspace_id: Workspace context for the export
            total_items: Total number of items exported
            timestamp: When the export occurred

        Example:
            logger.log_gdpr_export(
                user_id="user-123",
                workspace_id="ws-456",
                total_items=18,
                timestamp=datetime.now()
            )

        Note:
            - Do NOT include exported data in the log
            - This audit record must be retained for compliance
            - Added in version 1.1.0 (Issue #73)
        """
        ...


# =============================================================================
# Chatbot Extension Protocols (ADR-006)
# =============================================================================


@runtime_checkable
class ChatbotAuthProvider(Protocol):
    """
    Extension point for chatbot platform authentication.

    Maps platform-specific identities (Discord user IDs, Slack user IDs) to
    internal tenant and user identities.

    OSS Behavior: Not registered; all users treated as anonymous.
    Cloud Behavior: Maps platform workspaces to tenants, users to accounts.

    Version: 1.0.0

    Related: ADR-006 Chatbot Platform Integrations
    """

    def authenticate_platform_user(
        self,
        platform: str,
        platform_user_id: str,
        workspace_id: str,
    ) -> dict:
        """
        Authenticate a user from a chat platform.

        Args:
            platform: Platform identifier ("discord", "slack", "telegram", "whatsapp")
            platform_user_id: User ID from the platform (e.g., Discord snowflake)
            workspace_id: Workspace/guild/org ID from the platform

        Returns:
            Authentication result dict:
            {
                "authenticated": bool,
                "tenant_id": str | None,
                "user_id": str | None,
                "permissions": list[str],
                "error": str | None
            }

        Example:
            result = provider.authenticate_platform_user(
                platform="discord",
                platform_user_id="123456789",
                workspace_id="guild-acme"
            )
            if result["authenticated"]:
                tenant_id = result["tenant_id"]
        """
        ...

    def resolve_tenant(
        self,
        platform: str,
        workspace_id: str,
    ) -> Optional[str]:
        """
        Resolve a platform workspace to a tenant ID.

        Args:
            platform: Platform identifier
            workspace_id: Workspace ID from the platform

        Returns:
            Tenant ID if workspace is registered, None otherwise.

        Example:
            tenant = provider.resolve_tenant("slack", "T12345")
            # Returns "acme-corp" if Slack workspace T12345 is linked to acme-corp
        """
        ...

    def get_user_identity(
        self,
        platform: str,
        platform_user_id: str,
    ) -> Optional[dict]:
        """
        Get internal user identity for a platform user.

        Args:
            platform: Platform identifier
            platform_user_id: User ID from the platform

        Returns:
            User identity dict or None:
            {
                "user_id": str,
                "email": str | None,
                "display_name": str | None
            }

        Note:
            Returns None if user is not linked to an internal account.
        """
        ...


@runtime_checkable
class ChatbotRateLimiter(Protocol):
    """
    Extension point for chatbot-specific rate limiting.

    Implements token bucket or sliding window rate limiting for chatbot requests.
    Supports per-user, per-channel, and per-workspace limits.

    OSS Behavior: Not registered; no rate limiting (or simple local limiter).
    Cloud Behavior: Distributed rate limiting with Redis/Valkey backend.

    Version: 1.0.0

    Related: ADR-006 Chatbot Platform Integrations
    """

    def check_rate_limit(
        self,
        user_id: str,
        channel_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a request should be allowed under rate limits.

        Args:
            user_id: User making the request
            channel_id: Channel where request originated (optional)
            workspace_id: Workspace context (optional)

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If not allowed, reason explains the limit exceeded.

        Example:
            allowed, reason = limiter.check_rate_limit(
                user_id="user-123",
                channel_id="channel-456",
                workspace_id="ws-789"
            )
            if not allowed:
                return f"Rate limited: {reason}"
        """
        ...

    def record_request(
        self,
        user_id: str,
        tokens_used: int = 0,
        channel_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> None:
        """
        Record a request for rate limiting purposes.

        Args:
            user_id: User who made the request
            tokens_used: Number of LLM tokens consumed
            channel_id: Channel context (optional)
            workspace_id: Workspace context (optional)

        Note:
            Call this after successful request processing.
        """
        ...

    def get_remaining_quota(
        self,
        user_id: str,
        workspace_id: Optional[str] = None,
    ) -> dict:
        """
        Get remaining quota for a user.

        Args:
            user_id: User to check
            workspace_id: Workspace context (optional)

        Returns:
            Quota status dict:
            {
                "requests_remaining": int,
                "tokens_remaining": int,
                "reset_at": datetime | None
            }
        """
        ...


@runtime_checkable
class ChatbotAccessController(Protocol):
    """
    Extension point for chatbot access control.

    Controls which channels the bot can respond in and which commands
    users can execute. Implements allowlist/blocklist patterns.

    OSS Behavior: Not registered; bot responds everywhere.
    Cloud Behavior: Per-workspace channel allowlists, command permissions.

    Version: 1.0.0

    Related: ADR-006 Chatbot Platform Integrations
    """

    def check_channel_access(
        self,
        user_id: str,
        channel_id: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if bot should respond in a channel.

        Args:
            user_id: User who triggered the bot
            channel_id: Channel where bot was invoked
            workspace_id: Workspace context

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If not allowed, reason explains why.

        Example:
            allowed, reason = controller.check_channel_access(
                user_id="user-123",
                channel_id="private-channel",
                workspace_id="ws-789"
            )
            if not allowed:
                # Silently ignore or send ephemeral message
                pass
        """
        ...

    def check_command_access(
        self,
        user_id: str,
        command: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can execute a command.

        Args:
            user_id: User requesting command execution
            command: Command being executed (e.g., "/admin", "/config")
            workspace_id: Workspace context

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If not allowed, reason explains permission requirement.

        Example:
            allowed, reason = controller.check_command_access(
                user_id="user-123",
                command="/config",
                workspace_id="ws-789"
            )
            if not allowed:
                return f"Permission denied: {reason}"
        """
        ...

    def get_allowed_channels(
        self,
        workspace_id: str,
    ) -> list[str]:
        """
        Get list of channels where bot is enabled.

        Args:
            workspace_id: Workspace to query

        Returns:
            List of channel IDs where bot can respond.
            Empty list means bot is disabled in workspace.

        Note:
            If this returns an empty list and no blocklist is configured,
            implementations may choose to allow all channels by default.
        """
        ...


# =============================================================================
# Context Store Protocol (ADR-007)
# =============================================================================


@runtime_checkable
class ContextStore(Protocol):
    """
    Extension point for conversation context persistence.

    Implementations provide persistent storage for conversation contexts,
    enabling context recovery and long-term storage.

    OSS Behavior: Not registered; contexts are in-memory only.
    Cloud Behavior: Persists to Pixeltable with tenant isolation.

    Version: 1.0.0

    Related: ADR-006 Chatbot Platform Integrations, ADR-003 Pixeltable Patterns
    """

    async def save(self, thread_id: str, context_data: dict) -> None:
        """
        Save context data to persistent storage.

        Args:
            thread_id: Unique thread identifier
            context_data: Serialized context data (from to_dict)
        """
        ...

    async def load(self, thread_id: str) -> Optional[dict]:
        """
        Load context data from persistent storage.

        Args:
            thread_id: Unique thread identifier

        Returns:
            Context data dict if found, None otherwise
        """
        ...

    async def delete(self, thread_id: str) -> None:
        """
        Delete context from persistent storage.

        Args:
            thread_id: Unique thread identifier
        """
        ...

    async def cleanup_expired(self, ttl_days: int = 90) -> int:
        """
        Remove contexts older than TTL.

        Args:
            ttl_days: Days after which contexts expire

        Returns:
            Number of contexts deleted
        """
        ...


# =============================================================================
# Response Filtering Protocol (ADR-007)
# =============================================================================


@runtime_checkable
class ResponseFilter(Protocol):
    """
    Extension point for filtering LLM responses.

    Implementations can filter sensitive data from responses based on
    channel visibility, apply content policies, or modify responses
    for compliance requirements.

    Version: 1.0.0

    Example:
        class CloudResponseFilter:
            def filter_response(
                self,
                query: str,
                response: str,
                is_public_channel: bool,
            ) -> str:
                if is_public_channel and contains_pii(response):
                    return "[Sensitive data redacted]"
                return response

        registry = ExtensionRegistry.get()
        registry.response_filter = CloudResponseFilter()
    """

    def filter_response(
        self,
        query: str,
        response: str,
        is_public_channel: bool,
    ) -> str:
        """
        Filter an LLM response based on channel visibility and content.

        Args:
            query: The original user query
            response: The LLM response to filter
            is_public_channel: Whether this is a public channel

        Returns:
            The filtered response (may be original or modified)
        """
        ...


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Version constants
    "TENANT_PROVIDER_VERSION",
    "USAGE_TRACKER_VERSION",
    "AUDIT_LOGGER_VERSION",
    "CHATBOT_AUTH_PROVIDER_VERSION",
    "CHATBOT_RATE_LIMITER_VERSION",
    "CHATBOT_ACCESS_CONTROLLER_VERSION",
    "CONTEXT_STORE_VERSION",
    "RESPONSE_FILTER_VERSION",
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
    # Response filtering protocol (ADR-007)
    "ResponseFilter",
]
