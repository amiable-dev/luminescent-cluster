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
TDD Tests for default access control policy.

These tests cover the DefaultAccessControlPolicy class which provides
permissive defaults for OSS deployments per ADR-005/ADR-006.

Version: 1.0.0
"""

import pytest
from typing import Optional, List

from luminescent_cluster.extensions.protocols import ChatbotAccessController


# =============================================================================
# DefaultAccessControlPolicy Tests (Issues #68-69)
# =============================================================================


class TestDefaultAccessControlPolicy:
    """TDD: Tests for DefaultAccessControlPolicy (permissive OSS default)."""

    @pytest.fixture
    def policy(self):
        """Create default access control policy."""
        from luminescent_cluster.chatbot.access_control import DefaultAccessControlPolicy

        return DefaultAccessControlPolicy()

    def test_implements_protocol(self, policy):
        """DefaultAccessControlPolicy should implement ChatbotAccessController."""
        assert isinstance(policy, ChatbotAccessController)

    def test_allows_all_channels_by_default(self, policy):
        """Default policy should allow all channels."""
        allowed, reason = policy.check_channel_access(
            user_id="user-123",
            channel_id="any-channel",
            workspace_id="ws-456",
        )

        assert allowed is True
        assert reason is None

    def test_allows_private_channels(self, policy):
        """Default policy should allow private channels."""
        allowed, reason = policy.check_channel_access(
            user_id="user-123",
            channel_id="private-channel",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_allows_public_channels(self, policy):
        """Default policy should allow public channels."""
        allowed, reason = policy.check_channel_access(
            user_id="user-123",
            channel_id="public-channel",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_allows_direct_messages(self, policy):
        """Default policy should allow DMs."""
        allowed, reason = policy.check_channel_access(
            user_id="user-123",
            channel_id="dm-user-123",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_allows_all_commands_by_default(self, policy):
        """Default policy should allow all commands."""
        allowed, reason = policy.check_command_access(
            user_id="user-123",
            command="/ask",
            workspace_id="ws-456",
        )

        assert allowed is True
        assert reason is None

    def test_allows_admin_commands(self, policy):
        """Default policy should allow admin commands (no restrictions in OSS)."""
        allowed, reason = policy.check_command_access(
            user_id="user-123",
            command="/admin",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_allows_slash_commands(self, policy):
        """Default policy should allow slash commands."""
        for command in ["/help", "/memorize", "/settings", "/clear"]:
            allowed, reason = policy.check_command_access(
                user_id="user-123",
                command=command,
                workspace_id="ws-456",
            )
            assert allowed is True, f"Command {command} should be allowed"

    def test_returns_empty_allowed_channels_list(self, policy):
        """get_allowed_channels should return empty list (meaning all allowed)."""
        channels = policy.get_allowed_channels(workspace_id="ws-456")

        assert channels == []
        assert isinstance(channels, list)


# =============================================================================
# ConfigurableAccessControlPolicy Tests
# =============================================================================


class TestConfigurableAccessControlPolicy:
    """TDD: Tests for ConfigurableAccessControlPolicy (file-based config)."""

    @pytest.fixture
    def policy_with_allowlist(self):
        """Create policy with channel allowlist."""
        from luminescent_cluster.chatbot.access_control import ConfigurableAccessControlPolicy

        return ConfigurableAccessControlPolicy(
            allowed_channels=["channel-1", "channel-2", "channel-3"],
            blocked_channels=[],
            allowed_commands=None,  # Allow all
        )

    @pytest.fixture
    def policy_with_blocklist(self):
        """Create policy with channel blocklist."""
        from luminescent_cluster.chatbot.access_control import ConfigurableAccessControlPolicy

        return ConfigurableAccessControlPolicy(
            allowed_channels=None,  # Allow all except blocked
            blocked_channels=["secret-channel", "hr-channel"],
            allowed_commands=None,
        )

    @pytest.fixture
    def policy_with_command_restrictions(self):
        """Create policy with command restrictions."""
        from luminescent_cluster.chatbot.access_control import ConfigurableAccessControlPolicy

        return ConfigurableAccessControlPolicy(
            allowed_channels=None,
            blocked_channels=[],
            allowed_commands=["/help", "/ask", "/search"],
        )

    def test_allowlist_allows_listed_channels(self, policy_with_allowlist):
        """Should allow channels in allowlist."""
        allowed, _ = policy_with_allowlist.check_channel_access(
            user_id="user-123",
            channel_id="channel-1",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_allowlist_blocks_unlisted_channels(self, policy_with_allowlist):
        """Should block channels not in allowlist."""
        allowed, reason = policy_with_allowlist.check_channel_access(
            user_id="user-123",
            channel_id="channel-999",
            workspace_id="ws-456",
        )

        assert allowed is False
        assert reason is not None
        assert "not in allowed" in reason.lower()

    def test_blocklist_blocks_listed_channels(self, policy_with_blocklist):
        """Should block channels in blocklist."""
        allowed, reason = policy_with_blocklist.check_channel_access(
            user_id="user-123",
            channel_id="secret-channel",
            workspace_id="ws-456",
        )

        assert allowed is False
        assert reason is not None

    def test_blocklist_allows_unlisted_channels(self, policy_with_blocklist):
        """Should allow channels not in blocklist."""
        allowed, _ = policy_with_blocklist.check_channel_access(
            user_id="user-123",
            channel_id="general-channel",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_command_restrictions_allow_listed_commands(self, policy_with_command_restrictions):
        """Should allow commands in allowed list."""
        allowed, _ = policy_with_command_restrictions.check_command_access(
            user_id="user-123",
            command="/help",
            workspace_id="ws-456",
        )

        assert allowed is True

    def test_command_restrictions_block_unlisted_commands(self, policy_with_command_restrictions):
        """Should block commands not in allowed list."""
        allowed, reason = policy_with_command_restrictions.check_command_access(
            user_id="user-123",
            command="/admin",
            workspace_id="ws-456",
        )

        assert allowed is False
        assert reason is not None

    def test_get_allowed_channels_returns_allowlist(self, policy_with_allowlist):
        """Should return allowed channels list."""
        channels = policy_with_allowlist.get_allowed_channels(workspace_id="ws-456")

        assert channels == ["channel-1", "channel-2", "channel-3"]


# =============================================================================
# ResponseFilterPolicy Tests (ADR-006 sensitive data filtering)
# =============================================================================


class TestResponseFilterPolicy:
    """TDD: Tests for ResponseFilterPolicy (public channel filtering)."""

    @pytest.fixture
    def filter_policy(self):
        """Create response filter policy."""
        from luminescent_cluster.chatbot.access_control import ResponseFilterPolicy

        return ResponseFilterPolicy(
            sensitive_patterns=[
                r"password\s*[:=]\s*\S+",
                r"api[_-]?key\s*[:=]\s*\S+",
                r"secret\s*[:=]\s*\S+",
            ]
        )

    def test_passes_clean_response(self, filter_policy):
        """Should pass response without sensitive data."""
        response = "The weather today is sunny and warm."

        filtered = filter_policy.filter_response(
            query="What's the weather?",
            response=response,
            is_public_channel=True,
        )

        assert filtered == response

    def test_filters_password_in_public_channel(self, filter_policy):
        """Should filter password from public channel response."""
        response = "Found in config: password=secret123 and other data"

        filtered = filter_policy.filter_response(
            query="Show me the config",
            response=response,
            is_public_channel=True,
        )

        assert "password=secret123" not in filtered
        assert "sensitive data" in filtered.lower() or "redacted" in filtered.lower()

    def test_allows_sensitive_data_in_private_channel(self, filter_policy):
        """Should allow sensitive data in private channels."""
        response = "Found: password=secret123"

        filtered = filter_policy.filter_response(
            query="Show password",
            response=response,
            is_public_channel=False,
        )

        assert filtered == response

    def test_filters_api_key(self, filter_policy):
        """Should filter API keys."""
        response = "Your api_key: sk-1234567890abcdef"

        filtered = filter_policy.filter_response(
            query="What's my API key?",
            response=response,
            is_public_channel=True,
        )

        assert "sk-1234567890abcdef" not in filtered

    def test_filters_multiple_sensitive_items(self, filter_policy):
        """Should filter multiple sensitive items."""
        response = "Config: password=abc123 and api-key=xyz789"

        filtered = filter_policy.filter_response(
            query="Show config",
            response=response,
            is_public_channel=True,
        )

        assert "abc123" not in filtered
        assert "xyz789" not in filtered
