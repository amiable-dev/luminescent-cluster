# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Maintenance module (ADR-003).

Provides automatic maintenance triggers for the memory system,
including HNSW reindexing when recall degrades.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)
"""

from .reindex_trigger import ReindexTrigger

__all__ = [
    "ReindexTrigger",
]
