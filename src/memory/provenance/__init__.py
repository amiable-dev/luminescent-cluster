# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Memory Provenance module for tracking source attribution (ADR-003 Phase 2).

This module provides provenance tracking to meet the ADR-003 Phase 2
exit criterion: "Provenance available for all retrieved items"

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from .service import ProvenanceService

__all__ = [
    "ProvenanceService",
]
