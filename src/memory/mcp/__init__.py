# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""MCP tools for memory operations.

This module provides MCP-compatible tool functions for memory CRUD.

Related GitHub Issues:
- #86: create_memory MCP Tool
- #87: get_memories MCP Tool
- #88: search_memories MCP Tool
- #89: delete_memory MCP Tool

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

from src.memory.mcp.tools import (
    create_memory,
    delete_memory,
    get_memories,
    get_memory_by_id,
    get_memory_provenance,
    invalidate_memory,
    reset_provider,
    search_memories,
    update_memory,
)

__all__ = [
    "create_memory",
    "get_memories",
    "get_memory_by_id",
    "search_memories",
    "delete_memory",
    "update_memory",
    "invalidate_memory",
    "get_memory_provenance",
    "reset_provider",
]
