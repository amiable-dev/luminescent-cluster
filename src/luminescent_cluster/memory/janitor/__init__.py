# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Janitor process for memory maintenance.

Provides automated cleanup tasks:
- Deduplication (>85% similarity threshold)
- Contradiction handling ("newer wins")
- Expiration cleanup

Related GitHub Issues:
- #102: Janitor Process Framework
- #103: Deduplication
- #104: Contradiction Handling
- #105: Expiration Cleanup

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

from luminescent_cluster.memory.janitor.contradiction import ContradictionHandler
from luminescent_cluster.memory.janitor.deduplication import Deduplicator
from luminescent_cluster.memory.janitor.expiration import ExpirationCleaner
from luminescent_cluster.memory.janitor.runner import JanitorRunner
from luminescent_cluster.memory.janitor.scheduler import JanitorScheduler

__all__ = [
    "JanitorRunner",
    "JanitorScheduler",
    "Deduplicator",
    "ContradictionHandler",
    "ExpirationCleaner",
]
