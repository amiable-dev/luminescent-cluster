# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Architecture module for ADR-003.

This module provides persistent technical context for AI development,
implementing a three-tier memory architecture:

- Tier 1 (Hot): Session memory for fast access to current state
- Tier 2 (Warm): User/conversation memory with async extraction
- Tier 3 (Cold): Organizational knowledge with semantic search

See ADR-003 for architecture details.
"""

from src.memory.schemas.memory_types import (
    Memory,
    MemoryScope,
    MemoryType,
)

__all__ = [
    "Memory",
    "MemoryScope",
    "MemoryType",
]
