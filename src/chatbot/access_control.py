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
Access control implementations for Luminescent Cluster chatbot.

This module provides access control policies per ADR-006 requirements:
- DefaultAccessControlPolicy: Permissive default for OSS deployments
- ConfigurableAccessControlPolicy: File-based allowlist/blocklist
- ResponseFilterPolicy: Filter sensitive data in public channels

Per ADR-005, cloud-specific implementations (CloudAccessController with
workspace SSO) belong in luminescent-cloud repository.

Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Optional, List, Pattern
import re
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Default Access Control Policy (OSS Mode)
# =============================================================================


class DefaultAccessControlPolicy:
    """
    Permissive default access control for OSS deployments.

    Allows all channels and commands by default. This is the appropriate
    behavior for self-hosted deployments where users have full control
    over their environment.

    Cloud implementations (in luminescent-cloud) can override with
    workspace-specific allowlists and role-based access.

    Per ADR-005 Dual-Repo Pattern:
    - This class: Public repo (luminescent-cluster)
    - CloudAccessController: Private repo (luminescent-cloud)

    Example:
        policy = DefaultAccessControlPolicy()
        allowed, reason = policy.check_channel_access(
            user_id="user-123",
            channel_id="any-channel",
            workspace_id="ws-456"
        )
        # allowed == True for all channels

    Version: 1.0.0
    """

    def check_channel_access(
        self,
        user_id: str,
        channel_id: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if bot should respond in a channel.

        In OSS mode, all channels are allowed.

        Args:
            user_id: User who triggered the bot
            channel_id: Channel where bot was invoked
            workspace_id: Workspace context

        Returns:
            Tuple of (True, None) - always allowed
        """
        return True, None

    def check_command_access(
        self,
        user_id: str,
        command: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can execute a command.

        In OSS mode, all commands are allowed.

        Args:
            user_id: User executing the command
            command: Command being executed (e.g., "/help")
            workspace_id: Workspace context

        Returns:
            Tuple of (True, None) - always allowed
        """
        return True, None

    def get_allowed_channels(
        self,
        workspace_id: str,
    ) -> List[str]:
        """
        Get list of channels where bot is enabled.

        In OSS mode, returns empty list meaning all channels are allowed.

        Args:
            workspace_id: Workspace to query

        Returns:
            Empty list (signifying all channels allowed)
        """
        return []


# =============================================================================
# Configurable Access Control Policy (Self-Hosted with Config)
# =============================================================================


@dataclass
class ConfigurableAccessControlPolicy:
    """
    File-based access control for self-hosted deployments.

    Supports channel allowlists, blocklists, and command restrictions.
    Useful for organizations that want some control without full cloud
    integration.

    Precedence:
    1. If allowed_channels is set, only those channels are permitted
    2. If blocked_channels is set, those are denied (all others allowed)
    3. If allowed_commands is set, only those commands are permitted

    Example:
        policy = ConfigurableAccessControlPolicy(
            allowed_channels=["#general", "#engineering"],
            blocked_channels=[],
            allowed_commands=["/help", "/ask"],
        )

    Version: 1.0.0
    """

    allowed_channels: Optional[List[str]] = None
    blocked_channels: List[str] = field(default_factory=list)
    allowed_commands: Optional[List[str]] = None

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
            Tuple of (allowed, reason)
        """
        # Check allowlist first (if configured)
        if self.allowed_channels is not None:
            if channel_id not in self.allowed_channels:
                return False, f"Channel '{channel_id}' is not in allowed channels list"
            return True, None

        # Check blocklist
        if channel_id in self.blocked_channels:
            return False, f"Channel '{channel_id}' is blocked"

        return True, None

    def check_command_access(
        self,
        user_id: str,
        command: str,
        workspace_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can execute a command.

        Args:
            user_id: User executing the command
            command: Command being executed
            workspace_id: Workspace context

        Returns:
            Tuple of (allowed, reason)
        """
        if self.allowed_commands is None:
            return True, None

        if command not in self.allowed_commands:
            return False, f"Command '{command}' is not allowed"

        return True, None

    def get_allowed_channels(
        self,
        workspace_id: str,
    ) -> List[str]:
        """
        Get list of channels where bot is enabled.

        Args:
            workspace_id: Workspace to query

        Returns:
            List of allowed channels, or empty if all allowed
        """
        return self.allowed_channels or []


# =============================================================================
# Response Filter Policy (Public Channel Filtering)
# =============================================================================


@dataclass
class ResponseFilterPolicy:
    """
    Filter sensitive data from responses in public channels.

    Per ADR-006 Access Control requirements:
    - Public channel: Public memories only, visible to all
    - Private channel: Workspace memories, visible to channel members
    - DM: User's full access, private to user

    This policy filters responses containing sensitive patterns
    (passwords, API keys, secrets) when responding in public channels.

    Example:
        policy = ResponseFilterPolicy(
            sensitive_patterns=[
                r"password\\s*[:=]\\s*\\S+",
                r"api[_-]?key\\s*[:=]\\s*\\S+",
            ]
        )

        filtered = policy.filter_response(
            query="Show config",
            response="password=secret123",
            is_public_channel=True,
        )
        # Returns warning about sensitive data

    Version: 1.0.0
    """

    sensitive_patterns: List[str] = field(default_factory=list)
    redaction_message: str = (
        "I found relevant information but it may contain sensitive data. "
        "Please ask me in a private channel or DM for the full response."
    )
    _compiled_patterns: List[Pattern] = field(default_factory=list, init=False)

    def __post_init__(self):
        """Compile regex patterns for performance."""
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.sensitive_patterns
        ]

    def filter_response(
        self,
        query: str,
        response: str,
        is_public_channel: bool,
    ) -> str:
        """
        Filter response based on channel visibility.

        Args:
            query: Original user query
            response: LLM response to filter
            is_public_channel: Whether this is a public channel

        Returns:
            Filtered response (may be redacted if sensitive data found)
        """
        # Private channels get full response
        if not is_public_channel:
            return response

        # Check for sensitive patterns in public channels
        if self._contains_sensitive_data(response):
            logger.warning(
                f"Sensitive data detected in public channel response, redacting"
            )
            return self.redaction_message

        return response

    def _contains_sensitive_data(self, text: str) -> bool:
        """
        Check if text contains sensitive data patterns.

        Args:
            text: Text to check

        Returns:
            True if sensitive patterns found
        """
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                return True
        return False

    def check_retrieval_permission(
        self,
        user_id: str,
        memory_visibility: str,
        user_workspace_ids: List[str],
        memory_workspace_id: str,
    ) -> bool:
        """
        Check if user can retrieve a memory item.

        Per ADR-006 channel permission rules:
        - Public memories: Visible to all
        - Workspace memories: Visible to workspace members
        - Private memories: Visible only to owner

        Args:
            user_id: User requesting the memory
            memory_visibility: "public", "workspace", or "private"
            user_workspace_ids: Workspaces user belongs to
            memory_workspace_id: Workspace the memory belongs to

        Returns:
            True if user can access the memory
        """
        if memory_visibility == "public":
            return True

        if memory_visibility == "workspace":
            return memory_workspace_id in user_workspace_ids

        # Private memories would need owner check (not implemented here)
        return False
