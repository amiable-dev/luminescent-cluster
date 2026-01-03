# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory provider implementations for ADR-003.

This module provides implementations of the MemoryProvider protocol:
- LocalMemoryProvider: In-memory OSS implementation

Related GitHub Issues:
- #85: Implement LocalMemoryProvider

ADR Reference: ADR-003 Memory Architecture, Phase 1a (Storage)
"""

from src.memory.providers.local import LocalMemoryProvider

__all__ = [
    "LocalMemoryProvider",
]
