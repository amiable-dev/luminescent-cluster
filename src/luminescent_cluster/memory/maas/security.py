# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MaaS Security Module - ADR-003 Phase 4.2 (Issues #162-167).

Security components for multi-agent collaboration:
- MEXTRAValidator: Input sanitization, injection detection
- MemoryPoisoningDefense: Output filtering, query analysis
- AgentRateLimiter: Per-agent rate limiting
- MaaSAuditLogger: Agent operation audit logging

MEXTRA Attack Mitigations:
- Input sanitization: Block known attack patterns
- Output filtering: Max results, sensitive masking
- Query analysis: Anomaly scoring with thresholds
- Rate limiting: Per agent, per user, per session
"""

import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# =============================================================================
# MEXTRA Validator
# =============================================================================

# Known attack patterns
_INJECTION_PATTERNS = [
    r"SELECT\s+\*\s+FROM",  # SQL injection
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"<script[^>]*>",  # XSS
    r"javascript:",
    r"on\w+\s*=",
    r"UNION\s+SELECT",
]

_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all)\s+instructions",
    r"SYSTEM:\s*",
    r"</system>",
    r"</user>",
    r"<\|im_start\|>",
    r"IGNORE\s+ALL\s+INSTRUCTIONS",
    r"You\s+are\s+now\s+",
    r"Pretend\s+you\s+are\s+",
]

# Sensitive data patterns
_SENSITIVE_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{3,}", "[API_KEY_REDACTED]"),  # OpenAI API keys (sk- prefix)
    (r"ghp_[a-zA-Z0-9]{20,}", "[GITHUB_TOKEN_REDACTED]"),  # GitHub PAT
    (r"password\s*[=:]\s*['\"]?[^\s'\"]+", "[PASSWORD_REDACTED]"),
    (r"secret\s*[=:]\s*['\"]?[^\s'\"]+", "[SECRET_REDACTED]"),
    (r"api[_-]?key\s*[=:]\s*['\"]?[^\s'\"]+", "[API_KEY_REDACTED]"),
]

# Anomalous query indicators
_ANOMALY_KEYWORDS = [
    "password",
    "secret",
    "api key",
    "credentials",
    "token",
    "all memories",
    "dump",
    "export all",
]


@dataclass
class ValidationResult:
    """Result of content validation."""

    is_valid: bool
    reason: Optional[str] = None
    sanitized: Optional[str] = None


class MEXTRAValidator:
    """Validator for MEXTRA attack detection and input sanitization.

    Detects:
    - SQL injection patterns
    - XSS/script injection
    - Prompt injection attempts
    """

    def __init__(self):
        """Initialize the validator."""
        self._injection_patterns = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
        self._prompt_patterns = [re.compile(p, re.IGNORECASE) for p in _PROMPT_INJECTION_PATTERNS]

    def is_suspicious(self, text: str) -> bool:
        """Check if text contains suspicious patterns.

        Args:
            text: Text to check.

        Returns:
            True if suspicious patterns detected.
        """
        # Check injection patterns
        for pattern in self._injection_patterns:
            if pattern.search(text):
                return True

        # Check prompt injection patterns
        for pattern in self._prompt_patterns:
            if pattern.search(text):
                return True

        return False

    def sanitize(self, text: str) -> str:
        """Sanitize text by removing dangerous patterns.

        Args:
            text: Text to sanitize.

        Returns:
            Sanitized text.
        """
        result = text

        # Remove script tags
        result = re.sub(r"<script[^>]*>.*?</script>", "", result, flags=re.IGNORECASE | re.DOTALL)
        result = re.sub(r"<script[^>]*>", "", result, flags=re.IGNORECASE)
        result = re.sub(r"</script>", "", result, flags=re.IGNORECASE)

        # Remove event handlers
        result = re.sub(r"\s+on\w+\s*=\s*['\"][^'\"]*['\"]", "", result, flags=re.IGNORECASE)

        return result

    def validate_memory_content(self, content: str) -> ValidationResult:
        """Validate memory content for safety.

        Args:
            content: Memory content to validate.

        Returns:
            ValidationResult with status and reason.
        """
        if self.is_suspicious(content):
            return ValidationResult(
                is_valid=False,
                reason="Potential injection pattern detected",
            )

        return ValidationResult(
            is_valid=True,
            sanitized=self.sanitize(content),
        )


# =============================================================================
# Memory Poisoning Defense
# =============================================================================


class MemoryPoisoningDefense:
    """Defense mechanisms against memory poisoning attacks.

    Features:
    - Output filtering: Remove sensitive data
    - Max results limit: Prevent data exfiltration
    - Query anomaly detection: Flag suspicious queries
    """

    def __init__(self, max_results: int = 100):
        """Initialize defense.

        Args:
            max_results: Maximum results to return.
        """
        self.max_results = max_results
        self._sensitive_patterns = [
            (re.compile(p, re.IGNORECASE), replacement) for p, replacement in _SENSITIVE_PATTERNS
        ]

    def filter_output(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter output to remove sensitive data and limit results.

        Args:
            memories: List of memory dicts.

        Returns:
            Filtered list of memories.
        """
        # Limit results
        filtered = memories[: self.max_results]

        # Mask sensitive data
        for memory in filtered:
            if "content" in memory:
                content = memory["content"]
                for pattern, replacement in self._sensitive_patterns:
                    content = pattern.sub(replacement, content)
                memory["content"] = content

        return filtered

    def analyze_query(self, query: str) -> float:
        """Analyze query for anomalous patterns.

        Args:
            query: Query string.

        Returns:
            Anomaly score (0.0 - 1.0, higher = more anomalous).
        """
        query_lower = query.lower()
        score = 0.0

        # Check for anomaly keywords
        for keyword in _ANOMALY_KEYWORDS:
            if keyword in query_lower:
                score += 0.15

        # Check for multiple sensitive keywords
        sensitive_count = sum(1 for kw in _ANOMALY_KEYWORDS if kw in query_lower)
        if sensitive_count >= 3:
            score += 0.3

        # Check for unusual length
        if len(query) > 500:
            score += 0.1

        return min(score, 1.0)


# =============================================================================
# Rate Limiter
# =============================================================================


class AgentRateLimiter:
    """Rate limiter for agent operations.

    Implements sliding window rate limiting per agent.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        window_seconds: float = 60.0,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute.
            window_seconds: Window size in seconds.
        """
        self.max_requests = requests_per_minute
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def check(self, agent_id: str) -> tuple[bool, Optional[str]]:
        """Check if request is allowed.

        Args:
            agent_id: Agent making the request.

        Returns:
            Tuple of (allowed, reason).
        """
        with self._lock:
            now = time.time()

            # Initialize if needed
            if agent_id not in self._requests:
                self._requests[agent_id] = []

            # Clean old requests
            cutoff = now - self.window_seconds
            self._requests[agent_id] = [t for t in self._requests[agent_id] if t > cutoff]

            # Check limit
            if len(self._requests[agent_id]) >= self.max_requests:
                return False, f"Rate limit exceeded ({self.max_requests}/min)"

            # Record request
            self._requests[agent_id].append(now)
            return True, None


# =============================================================================
# Audit Logger
# =============================================================================


@dataclass
class AuditEntry:
    """An audit log entry."""

    timestamp: datetime
    event_type: str
    agent_id: Optional[str]
    action: str
    outcome: str
    details: dict[str, Any] = field(default_factory=dict)


class MaaSAuditLogger:
    """Audit logger for agent operations.

    Logs security-relevant events for compliance and forensics.
    """

    def __init__(self, max_entries: int = 10000):
        """Initialize audit logger.

        Args:
            max_entries: Maximum entries to keep in memory.
        """
        self.max_entries = max_entries
        self._entries: list[AuditEntry] = []
        self._lock = threading.RLock()

    def log_agent_operation(
        self,
        event_type: str,
        agent_id: str,
        action: str,
        outcome: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an agent operation.

        Args:
            event_type: Type of event (AGENT_AUTH, etc.)
            agent_id: Agent performing the operation.
            action: What was done.
            outcome: Result (success, failure, denied).
            details: Additional context.
        """
        with self._lock:
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                agent_id=agent_id,
                action=action,
                outcome=outcome,
                details=details or {},
            )
            self._entries.append(entry)

            # Trim if needed
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries :]

    def log_cross_agent_access(
        self,
        source_agent_id: str,
        target_agent_id: str,
        action: str,
        outcome: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log cross-agent access.

        Args:
            source_agent_id: Agent initiating access.
            target_agent_id: Agent being accessed.
            action: What was done.
            outcome: Result.
            details: Additional context.
        """
        self.log_agent_operation(
            event_type="CROSS_AGENT_READ",
            agent_id=source_agent_id,
            action=action,
            outcome=outcome,
            details={
                "target_agent_id": target_agent_id,
                **(details or {}),
            },
        )

    def log_permission_denied(
        self,
        agent_id: str,
        action: str,
        resource: str,
        reason: str,
    ) -> None:
        """Log a permission denied event.

        Args:
            agent_id: Agent that was denied.
            action: What was attempted.
            resource: Resource that was accessed.
            reason: Why it was denied.
        """
        self.log_agent_operation(
            event_type="PERMISSION_DENIED",
            agent_id=agent_id,
            action=action,
            outcome="denied",
            details={
                "resource": resource,
                "reason": reason,
            },
        )

    def get_recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit logs.

        Args:
            limit: Maximum entries to return.

        Returns:
            List of log entry dicts.
        """
        with self._lock:
            entries = self._entries[-limit:]
            return [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "agent_id": e.agent_id,
                    "action": e.action,
                    "outcome": e.outcome,
                    "details": e.details,
                }
                for e in reversed(entries)
            ]
