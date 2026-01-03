# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory storage tables for ADR-003.

This module provides Pixeltable table definitions for memory storage:
- user_memory: User-specific memories (warm tier)
- conversation_memory: Conversation history (hot tier)

Related GitHub Issues:
- #83: Create user_memory Table
- #84: Create conversation_memory Table

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

from src.memory.storage.tables import (
    CONVERSATION_MEMORY_SCHEMA,
    CONVERSATION_MEMORY_TABLE,
    USER_MEMORY_SCHEMA,
    USER_MEMORY_TABLE,
    setup_conversation_memory_table,
    setup_user_memory_table,
)

__all__ = [
    # Table names
    "USER_MEMORY_TABLE",
    "CONVERSATION_MEMORY_TABLE",
    # Schemas
    "USER_MEMORY_SCHEMA",
    "CONVERSATION_MEMORY_SCHEMA",
    # Setup functions
    "setup_user_memory_table",
    "setup_conversation_memory_table",
]
