# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: RED Phase - Tests for user_memory Pixeltable Table.

These tests define the expected schema and behavior for the user_memory
table which stores user-specific memories.

Related GitHub Issues:
- #83: Create user_memory Table

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

import pytest
from datetime import datetime, timezone
from typing import Optional


class TestUserMemoryTableSetup:
    """TDD: Tests for user_memory table setup function."""

    def test_setup_user_memory_table_function_exists(self):
        """setup_user_memory_table function should be defined.

        GitHub Issue: #83
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.storage.tables import setup_user_memory_table

        assert callable(setup_user_memory_table)


class TestUserMemoryTableSchema:
    """TDD: Tests for user_memory table schema constants."""

    def test_user_memory_table_name_constant(self):
        """USER_MEMORY_TABLE constant should be defined.

        GitHub Issue: #83
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.storage.tables import USER_MEMORY_TABLE

        assert USER_MEMORY_TABLE == "user_memory"

    def test_user_memory_schema_constant(self):
        """USER_MEMORY_SCHEMA should define expected columns.

        GitHub Issue: #83
        ADR Reference: ADR-003 lines 881-900
        """
        from src.memory.storage.tables import USER_MEMORY_SCHEMA

        expected_columns = {
            "user_id",
            "content",
            "memory_type",
            "confidence",
            "source",
            "raw_source",
            "extraction_version",
            "created_at",
            "last_accessed_at",
            "expires_at",
            "metadata",
        }

        assert set(USER_MEMORY_SCHEMA.keys()) == expected_columns


class TestConversationMemoryTableSetup:
    """TDD: Tests for conversation_memory table setup function."""

    def test_setup_conversation_memory_table_function_exists(self):
        """setup_conversation_memory_table function should be defined.

        GitHub Issue: #84
        ADR Reference: ADR-003 Phase 1a (Hot Memory)
        """
        from src.memory.storage.tables import setup_conversation_memory_table

        assert callable(setup_conversation_memory_table)


class TestConversationMemoryTableSchema:
    """TDD: Tests for conversation_memory table schema constants."""

    def test_conversation_memory_table_name_constant(self):
        """CONVERSATION_MEMORY_TABLE constant should be defined.

        GitHub Issue: #84
        ADR Reference: ADR-003 Phase 1a (Hot Memory)
        """
        from src.memory.storage.tables import CONVERSATION_MEMORY_TABLE

        assert CONVERSATION_MEMORY_TABLE == "conversation_memory"

    def test_conversation_memory_schema_constant(self):
        """CONVERSATION_MEMORY_SCHEMA should define expected columns.

        GitHub Issue: #84
        ADR Reference: ADR-003 Phase 1a (Hot Memory)
        """
        from src.memory.storage.tables import CONVERSATION_MEMORY_SCHEMA

        expected_columns = {
            "conversation_id",
            "user_id",
            "role",
            "content",
            "timestamp",
            "metadata",
        }

        assert set(CONVERSATION_MEMORY_SCHEMA.keys()) == expected_columns


class TestStorageModuleExports:
    """TDD: Tests for storage module exports."""

    def test_storage_module_exists(self):
        """src.memory.storage module should exist.

        GitHub Issue: #83
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        import src.memory.storage

        assert src.memory.storage is not None

    def test_storage_exports_table_names(self):
        """storage module should export table name constants.

        GitHub Issue: #83
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.storage import USER_MEMORY_TABLE, CONVERSATION_MEMORY_TABLE

        assert USER_MEMORY_TABLE is not None
        assert CONVERSATION_MEMORY_TABLE is not None

    def test_storage_exports_schemas(self):
        """storage module should export schema constants.

        GitHub Issue: #83
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.storage import USER_MEMORY_SCHEMA, CONVERSATION_MEMORY_SCHEMA

        assert USER_MEMORY_SCHEMA is not None
        assert CONVERSATION_MEMORY_SCHEMA is not None

    def test_storage_exports_setup_functions(self):
        """storage module should export setup functions.

        GitHub Issue: #83
        ADR Reference: ADR-003 Phase 1a (Storage)
        """
        from src.memory.storage import (
            setup_user_memory_table,
            setup_conversation_memory_table,
        )

        assert callable(setup_user_memory_table)
        assert callable(setup_conversation_memory_table)
