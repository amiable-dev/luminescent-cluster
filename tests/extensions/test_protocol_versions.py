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
TDD: RED Phase - Tests for protocol version constants.

These tests verify that protocol version constants exist and follow
semantic versioning. Part of Issue #71.

ADR Reference: ADR-007 Cross-ADR Integration Guide
"""

import re
import pytest


class TestProtocolVersionConstants:
    """Tests for protocol version constant definitions."""

    def test_tenant_provider_version_exists(self):
        """TenantProvider has a version constant."""
        from src.extensions.protocols import TENANT_PROVIDER_VERSION

        assert TENANT_PROVIDER_VERSION is not None

    def test_usage_tracker_version_exists(self):
        """UsageTracker has a version constant."""
        from src.extensions.protocols import USAGE_TRACKER_VERSION

        assert USAGE_TRACKER_VERSION is not None

    def test_audit_logger_version_exists(self):
        """AuditLogger has a version constant."""
        from src.extensions.protocols import AUDIT_LOGGER_VERSION

        assert AUDIT_LOGGER_VERSION is not None

    def test_chatbot_auth_provider_version_exists(self):
        """ChatbotAuthProvider has a version constant."""
        from src.extensions.protocols import CHATBOT_AUTH_PROVIDER_VERSION

        assert CHATBOT_AUTH_PROVIDER_VERSION is not None

    def test_chatbot_rate_limiter_version_exists(self):
        """ChatbotRateLimiter has a version constant."""
        from src.extensions.protocols import CHATBOT_RATE_LIMITER_VERSION

        assert CHATBOT_RATE_LIMITER_VERSION is not None

    def test_chatbot_access_controller_version_exists(self):
        """ChatbotAccessController has a version constant."""
        from src.extensions.protocols import CHATBOT_ACCESS_CONTROLLER_VERSION

        assert CHATBOT_ACCESS_CONTROLLER_VERSION is not None


class TestProtocolVersionsFollowSemVer:
    """Tests that version constants follow semantic versioning."""

    SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

    def test_tenant_provider_version_semver(self):
        """TenantProvider version follows SemVer."""
        from src.extensions.protocols import TENANT_PROVIDER_VERSION

        assert self.SEMVER_PATTERN.match(TENANT_PROVIDER_VERSION), (
            f"TENANT_PROVIDER_VERSION '{TENANT_PROVIDER_VERSION}' does not follow SemVer"
        )

    def test_usage_tracker_version_semver(self):
        """UsageTracker version follows SemVer."""
        from src.extensions.protocols import USAGE_TRACKER_VERSION

        assert self.SEMVER_PATTERN.match(USAGE_TRACKER_VERSION), (
            f"USAGE_TRACKER_VERSION '{USAGE_TRACKER_VERSION}' does not follow SemVer"
        )

    def test_audit_logger_version_semver(self):
        """AuditLogger version follows SemVer."""
        from src.extensions.protocols import AUDIT_LOGGER_VERSION

        assert self.SEMVER_PATTERN.match(AUDIT_LOGGER_VERSION), (
            f"AUDIT_LOGGER_VERSION '{AUDIT_LOGGER_VERSION}' does not follow SemVer"
        )

    def test_chatbot_auth_provider_version_semver(self):
        """ChatbotAuthProvider version follows SemVer."""
        from src.extensions.protocols import CHATBOT_AUTH_PROVIDER_VERSION

        assert self.SEMVER_PATTERN.match(CHATBOT_AUTH_PROVIDER_VERSION), (
            f"CHATBOT_AUTH_PROVIDER_VERSION '{CHATBOT_AUTH_PROVIDER_VERSION}' does not follow SemVer"
        )

    def test_chatbot_rate_limiter_version_semver(self):
        """ChatbotRateLimiter version follows SemVer."""
        from src.extensions.protocols import CHATBOT_RATE_LIMITER_VERSION

        assert self.SEMVER_PATTERN.match(CHATBOT_RATE_LIMITER_VERSION), (
            f"CHATBOT_RATE_LIMITER_VERSION '{CHATBOT_RATE_LIMITER_VERSION}' does not follow SemVer"
        )

    def test_chatbot_access_controller_version_semver(self):
        """ChatbotAccessController version follows SemVer."""
        from src.extensions.protocols import CHATBOT_ACCESS_CONTROLLER_VERSION

        assert self.SEMVER_PATTERN.match(CHATBOT_ACCESS_CONTROLLER_VERSION), (
            f"CHATBOT_ACCESS_CONTROLLER_VERSION '{CHATBOT_ACCESS_CONTROLLER_VERSION}' does not follow SemVer"
        )


class TestProtocolVersionValues:
    """Tests for expected version values."""

    def test_tenant_provider_version_is_1_0_0(self):
        """TenantProvider version is 1.0.0 as documented."""
        from src.extensions.protocols import TENANT_PROVIDER_VERSION

        assert TENANT_PROVIDER_VERSION == "1.0.0"

    def test_usage_tracker_version_is_1_0_0(self):
        """UsageTracker version is 1.0.0 as documented."""
        from src.extensions.protocols import USAGE_TRACKER_VERSION

        assert USAGE_TRACKER_VERSION == "1.0.0"

    def test_audit_logger_version_is_1_1_0(self):
        """AuditLogger version is 1.1.0 (bumped for GDPR methods in Issue #73)."""
        from src.extensions.protocols import AUDIT_LOGGER_VERSION

        assert AUDIT_LOGGER_VERSION == "1.1.0"

    def test_chatbot_auth_provider_version_is_1_0_0(self):
        """ChatbotAuthProvider version is 1.0.0 as documented."""
        from src.extensions.protocols import CHATBOT_AUTH_PROVIDER_VERSION

        assert CHATBOT_AUTH_PROVIDER_VERSION == "1.0.0"

    def test_chatbot_rate_limiter_version_is_1_0_0(self):
        """ChatbotRateLimiter version is 1.0.0 as documented."""
        from src.extensions.protocols import CHATBOT_RATE_LIMITER_VERSION

        assert CHATBOT_RATE_LIMITER_VERSION == "1.0.0"

    def test_chatbot_access_controller_version_is_1_0_0(self):
        """ChatbotAccessController version is 1.0.0 as documented."""
        from src.extensions.protocols import CHATBOT_ACCESS_CONTROLLER_VERSION

        assert CHATBOT_ACCESS_CONTROLLER_VERSION == "1.0.0"


class TestProtocolVersionExports:
    """Tests that version constants are exported in __all__."""

    def test_version_constants_in_protocols_all(self):
        """Version constants are exported from protocols module."""
        from src.extensions import protocols

        expected_exports = [
            "TENANT_PROVIDER_VERSION",
            "USAGE_TRACKER_VERSION",
            "AUDIT_LOGGER_VERSION",
            "CHATBOT_AUTH_PROVIDER_VERSION",
            "CHATBOT_RATE_LIMITER_VERSION",
            "CHATBOT_ACCESS_CONTROLLER_VERSION",
        ]

        for export in expected_exports:
            assert export in protocols.__all__, f"{export} not in protocols.__all__"

    def test_version_constants_in_extensions_all(self):
        """Version constants are exported from extensions package."""
        from src import extensions

        expected_exports = [
            "TENANT_PROVIDER_VERSION",
            "USAGE_TRACKER_VERSION",
            "AUDIT_LOGGER_VERSION",
            "CHATBOT_AUTH_PROVIDER_VERSION",
            "CHATBOT_RATE_LIMITER_VERSION",
            "CHATBOT_ACCESS_CONTROLLER_VERSION",
        ]

        for export in expected_exports:
            assert export in extensions.__all__, f"{export} not in extensions.__all__"
