# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Memory Provider Protocol re-export from extensions.

This module re-exports the MemoryProvider protocol from luminescent_cluster.extensions.protocols
to maintain backward compatibility while consolidating to a single definition.

The canonical definition is in src.extensions.protocols following ADR-007.

Related GitHub Issues:
- #80: Define MemoryProvider Protocol

ADR Reference: ADR-003 Memory Architecture, ADR-007 Extension Points
"""

# Re-export from canonical location (ADR-007 consolidation)
from luminescent_cluster.extensions.protocols import (  # noqa: F401
    MEMORY_PROVIDER_VERSION,
    MemoryProvider,
)

__all__ = ["MemoryProvider", "MEMORY_PROVIDER_VERSION"]
