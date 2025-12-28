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
TDD: RED Phase - Tests for GDPR audit methods in AuditLogger.

Part of Issue #73: Add GDPR Audit Methods to AuditLogger Protocol.

ADR Reference: ADR-007 Cross-ADR Integration Guide
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock


class TestAuditLoggerGDPRMethods:
    """Tests that AuditLogger protocol has GDPR methods."""

    def test_audit_logger_has_log_gdpr_deletion_method(self):
        """AuditLogger protocol defines log_gdpr_deletion method."""
        from src.extensions.protocols import AuditLogger

        assert hasattr(AuditLogger, "log_gdpr_deletion")

    def test_audit_logger_has_log_gdpr_export_method(self):
        """AuditLogger protocol defines log_gdpr_export method."""
        from src.extensions.protocols import AuditLogger

        assert hasattr(AuditLogger, "log_gdpr_export")


class TestAuditLoggerVersionBump:
    """Tests that AUDIT_LOGGER_VERSION is bumped for new methods."""

    def test_audit_logger_version_is_1_1_0(self):
        """AuditLogger version is bumped to 1.1.0 after GDPR methods added."""
        from src.extensions.protocols import AUDIT_LOGGER_VERSION

        assert AUDIT_LOGGER_VERSION == "1.1.0"


class TestGDPRDeletionMethod:
    """Tests for log_gdpr_deletion method signature and behavior."""

    def test_log_gdpr_deletion_signature(self):
        """log_gdpr_deletion accepts required parameters."""
        from src.extensions.protocols import AuditLogger
        from typing import Dict, Any

        # Create a mock implementation
        class MockAuditLogger:
            def log_event(
                self,
                event_type: str,
                actor: str,
                resource: str,
                action: str,
                outcome: str,
                details: dict | None = None,
            ) -> None:
                pass

            def log_security_event(
                self,
                event_type: str,
                severity: str,
                message: str,
                details: dict | None = None,
            ) -> None:
                pass

            def log_gdpr_deletion(
                self,
                user_id: str,
                workspace_id: str,
                items_deleted: Dict[str, int],
                timestamp: datetime,
            ) -> None:
                pass

            def log_gdpr_export(
                self,
                user_id: str,
                workspace_id: str,
                total_items: int,
                timestamp: datetime,
            ) -> None:
                pass

        logger = MockAuditLogger()

        # Should be callable with expected parameters
        logger.log_gdpr_deletion(
            user_id="user-123",
            workspace_id="ws-456",
            items_deleted={"conversations": 5, "knowledge": 2},
            timestamp=datetime.now(),
        )

        # Should satisfy protocol
        assert isinstance(logger, AuditLogger)


class TestGDPRExportMethod:
    """Tests for log_gdpr_export method signature and behavior."""

    def test_log_gdpr_export_signature(self):
        """log_gdpr_export accepts required parameters."""
        from src.extensions.protocols import AuditLogger
        from typing import Dict, Any

        # Create a mock implementation
        class MockAuditLogger:
            def log_event(
                self,
                event_type: str,
                actor: str,
                resource: str,
                action: str,
                outcome: str,
                details: dict | None = None,
            ) -> None:
                pass

            def log_security_event(
                self,
                event_type: str,
                severity: str,
                message: str,
                details: dict | None = None,
            ) -> None:
                pass

            def log_gdpr_deletion(
                self,
                user_id: str,
                workspace_id: str,
                items_deleted: Dict[str, int],
                timestamp: datetime,
            ) -> None:
                pass

            def log_gdpr_export(
                self,
                user_id: str,
                workspace_id: str,
                total_items: int,
                timestamp: datetime,
            ) -> None:
                pass

        logger = MockAuditLogger()

        # Should be callable with expected parameters
        logger.log_gdpr_export(
            user_id="user-123",
            workspace_id="ws-456",
            total_items=10,
            timestamp=datetime.now(),
        )

        # Should satisfy protocol
        assert isinstance(logger, AuditLogger)


class TestGDPRMethodsWithRegistry:
    """Tests for GDPR methods via ExtensionRegistry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the singleton before each test."""
        from src.extensions.registry import ExtensionRegistry

        ExtensionRegistry.reset()
        yield
        ExtensionRegistry.reset()

    def test_can_call_gdpr_deletion_via_registry(self):
        """Can call log_gdpr_deletion via registered audit logger."""
        from src.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        mock_logger = MagicMock()
        registry.audit_logger = mock_logger

        registry.audit_logger.log_gdpr_deletion(
            user_id="user-123",
            workspace_id="ws-456",
            items_deleted={"conversations": 5},
            timestamp=datetime.now(),
        )

        mock_logger.log_gdpr_deletion.assert_called_once()

    def test_can_call_gdpr_export_via_registry(self):
        """Can call log_gdpr_export via registered audit logger."""
        from src.extensions.registry import ExtensionRegistry

        registry = ExtensionRegistry.get()
        mock_logger = MagicMock()
        registry.audit_logger = mock_logger

        registry.audit_logger.log_gdpr_export(
            user_id="user-123",
            workspace_id="ws-456",
            total_items=10,
            timestamp=datetime.now(),
        )

        mock_logger.log_gdpr_export.assert_called_once()
