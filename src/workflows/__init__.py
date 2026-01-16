# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Workflow Integration module for ADR-002.

This module provides:
- Config parsing for .agent/config.yaml
- Single-file ingestion for git hook automation
- Security filtering (secrets protection)

Related: ADR-002 Workflow Integration
"""

from .config import WorkflowConfig, load_config, should_ingest_file, is_secret_file
from .ingestion import ingest_file, compute_content_hash

__all__ = [
    "WorkflowConfig",
    "load_config",
    "should_ingest_file",
    "is_secret_file",
    "ingest_file",
    "compute_content_hash",
]
