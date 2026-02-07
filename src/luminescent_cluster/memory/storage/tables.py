# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Pixeltable table definitions for memory storage.

Defines schemas and setup functions for:
- user_memory: User-specific memories (warm tier)
- conversation_memory: Conversation history (hot tier)

Related GitHub Issues:
- #83: Create user_memory Table
- #84: Create conversation_memory Table

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

from typing import Any, Optional

# Table names
USER_MEMORY_TABLE: str = "user_memory"
CONVERSATION_MEMORY_TABLE: str = "conversation_memory"

# Schema definitions (column name -> type description)
# These mirror the ADR-003 schema from lines 881-900
USER_MEMORY_SCHEMA: dict[str, str] = {
    "user_id": "String",  # User who owns this memory
    "content": "String",  # The memory content (indexed for semantic search)
    "memory_type": "String",  # Type: preference, fact, decision
    "confidence": "Float",  # Extraction confidence score (0.0-1.0)
    "source": "String",  # Where this memory came from
    "raw_source": "String",  # Original text for re-extraction
    "extraction_version": "Int",  # For re-processing on prompt updates
    "created_at": "Timestamp",  # When the memory was created
    "last_accessed_at": "Timestamp",  # For decay scoring
    "expires_at": "Timestamp",  # TTL support (optional)
    "metadata": "Json",  # Flexible metadata (scope, project_id, etc.)
}

CONVERSATION_MEMORY_SCHEMA: dict[str, str] = {
    "conversation_id": "String",  # Unique conversation identifier
    "user_id": "String",  # User in the conversation
    "role": "String",  # Message role: user, assistant, system
    "content": "String",  # Message content
    "timestamp": "Timestamp",  # When the message was sent
    "metadata": "Json",  # Additional metadata (tool calls, etc.)
}


def setup_user_memory_table(check_health: bool = True) -> Any:
    """Initialize user_memory Pixeltable table.

    Creates the user_memory table with the schema from ADR-003.
    Includes embedding index on content for semantic search.

    Args:
        check_health: If True, verify table is healthy after setup.

    Returns:
        The Pixeltable table object.

    Note:
        This function requires Pixeltable to be installed and configured.
        In OSS mode without Pixeltable, returns a mock object.
    """
    try:
        import pixeltable as pxt

        # Check if table already exists
        try:
            table = pxt.get_table(USER_MEMORY_TABLE)
            print(f"Table {USER_MEMORY_TABLE} already exists")
            return table
        except Exception:
            pass

        # Create the table
        table = pxt.create_table(
            USER_MEMORY_TABLE,
            {
                "user_id": pxt.String,
                "content": pxt.String,
                "memory_type": pxt.String,
                "confidence": pxt.Float,
                "source": pxt.String,
                "raw_source": pxt.String,
                "extraction_version": pxt.Int,
                "created_at": pxt.Timestamp,
                "last_accessed_at": pxt.Timestamp,
                "expires_at": pxt.Timestamp,
                "metadata": pxt.Json,
            },
        )

        print(f"Created {USER_MEMORY_TABLE} table")

        # Add embedding index for semantic search
        from pixeltable.functions.huggingface import sentence_transformer

        embed_model = sentence_transformer.using(model_id="sentence-transformers/all-MiniLM-L6-v2")

        table.add_embedding_index("content", string_embed=embed_model)
        print(f"Added embedding index to {USER_MEMORY_TABLE}")

        return table

    except ImportError:
        # Pixeltable not installed - return mock for OSS mode
        print(f"Pixeltable not available, {USER_MEMORY_TABLE} table not created")
        return None


def setup_conversation_memory_table(check_health: bool = True) -> Any:
    """Initialize conversation_memory Pixeltable table.

    Creates the conversation_memory table for hot memory tier.
    Stores raw conversation history for immediate context.

    Args:
        check_health: If True, verify table is healthy after setup.

    Returns:
        The Pixeltable table object.

    Note:
        This function requires Pixeltable to be installed and configured.
        In OSS mode without Pixeltable, returns a mock object.
    """
    try:
        import pixeltable as pxt

        # Check if table already exists
        try:
            table = pxt.get_table(CONVERSATION_MEMORY_TABLE)
            print(f"Table {CONVERSATION_MEMORY_TABLE} already exists")
            return table
        except Exception:
            pass

        # Create the table
        table = pxt.create_table(
            CONVERSATION_MEMORY_TABLE,
            {
                "conversation_id": pxt.String,
                "user_id": pxt.String,
                "role": pxt.String,
                "content": pxt.String,
                "timestamp": pxt.Timestamp,
                "metadata": pxt.Json,
            },
        )

        print(f"Created {CONVERSATION_MEMORY_TABLE} table")

        # Add embedding index for semantic search
        from pixeltable.functions.huggingface import sentence_transformer

        embed_model = sentence_transformer.using(model_id="sentence-transformers/all-MiniLM-L6-v2")

        table.add_embedding_index("content", string_embed=embed_model)
        print(f"Added embedding index to {CONVERSATION_MEMORY_TABLE}")

        return table

    except ImportError:
        # Pixeltable not installed - return mock for OSS mode
        print(f"Pixeltable not available, {CONVERSATION_MEMORY_TABLE} table not created")
        return None
