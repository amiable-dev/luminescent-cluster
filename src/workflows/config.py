# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Workflow configuration parsing for ADR-002.

This module provides:
- WorkflowConfig dataclass for ingestion settings
- load_config() to parse .agent/config.yaml
- should_ingest_file() to check if a file should be ingested
- is_secret_file() to detect sensitive files

Related: ADR-002 Workflow Integration, Phase 1 (Core Infrastructure)
"""

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional

import yaml


# Default patterns for ingestion
DEFAULT_INCLUDE_PATTERNS = [
    "docs/**/*.md",
    "*.md",
    "docs/adrs/**",
]

DEFAULT_EXCLUDE_PATTERNS = [
    "**/node_modules/**",
    "**/.venv/**",
    "**/dist/**",
    "**/build/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.env",
    "**/*.key",
    "**/*.pem",
    "**/secrets/**",
    "**/*secret*",
    "**/*password*",
    "**/*token*",
    "**/*credential*",
]

# Patterns for detecting secrets files
DEFAULT_SECRETS_PATTERNS = [
    r"\.env($|\.)",  # .env, .env.local, etc.
    r"\.key$",
    r"\.pem$",
    r"secret",
    r"password",
    r"token",
    r"credential",
]


@dataclass
class WorkflowConfig:
    """Configuration for workflow ingestion.

    Attributes:
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        max_file_size_kb: Maximum file size in KB to ingest
        skip_binary: Whether to skip binary files
        secrets_patterns: Regex patterns for detecting secrets files
    """

    include_patterns: List[str] = field(default_factory=lambda: DEFAULT_INCLUDE_PATTERNS.copy())
    exclude_patterns: List[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())
    max_file_size_kb: int = 500
    skip_binary: bool = True
    secrets_patterns: List[str] = field(default_factory=lambda: DEFAULT_SECRETS_PATTERNS.copy())


def load_config(project_root: Path) -> WorkflowConfig:
    """Load workflow configuration from .agent/config.yaml.

    Args:
        project_root: Path to the project root directory

    Returns:
        WorkflowConfig with settings from config file or defaults
    """
    config_path = Path(project_root) / ".agent" / "config.yaml"

    if not config_path.exists():
        return WorkflowConfig()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        return WorkflowConfig()

    ingestion = data.get("ingestion", {})

    # Load secrets patterns from config, with defaults as base
    # User can extend or override default secrets patterns
    config_secrets = ingestion.get("secrets_patterns", [])
    secrets_patterns = DEFAULT_SECRETS_PATTERNS.copy()
    if config_secrets:
        # Extend with user-defined patterns (don't replace defaults for safety)
        secrets_patterns.extend(config_secrets)

    return WorkflowConfig(
        include_patterns=ingestion.get("include", DEFAULT_INCLUDE_PATTERNS.copy()),
        exclude_patterns=ingestion.get("exclude", DEFAULT_EXCLUDE_PATTERNS.copy()),
        max_file_size_kb=ingestion.get("max_file_size_kb", 500),
        skip_binary=ingestion.get("skip_binary", True),
        secrets_patterns=secrets_patterns,
    )


def should_ingest_file(file_path: str, config: WorkflowConfig) -> bool:
    """Determine if a file should be ingested based on config.

    Args:
        file_path: Relative path to the file
        config: WorkflowConfig with include/exclude patterns

    Returns:
        True if the file should be ingested, False otherwise
    """
    # Normalize path separators
    file_path = file_path.replace("\\", "/")

    # Check if it's a secrets file first (highest priority)
    # Pass config's secrets_patterns to use user-defined patterns
    if is_secret_file(file_path, config.secrets_patterns):
        return False

    # Check exclude patterns
    for pattern in config.exclude_patterns:
        if _matches_pattern(file_path, pattern):
            return False

    # Check include patterns
    for pattern in config.include_patterns:
        if _matches_pattern(file_path, pattern):
            return True

    return False


def is_secret_file(file_path: str, secrets_patterns: Optional[List[str]] = None) -> bool:
    """Check if a file is a secrets/sensitive file.

    Args:
        file_path: Path to the file (can be relative or absolute)
        secrets_patterns: Regex patterns to match (defaults to DEFAULT_SECRETS_PATTERNS)

    Returns:
        True if the file appears to be a secrets file
    """
    # Normalize path and get filename
    file_path = file_path.replace("\\", "/")
    path_lower = file_path.lower()

    # Use provided patterns or defaults
    patterns = secrets_patterns if secrets_patterns is not None else DEFAULT_SECRETS_PATTERNS

    for pattern in patterns:
        if re.search(pattern, path_lower):
            return True

    return False


def _matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a glob pattern.

    Supports ** for directory recursion and * for wildcards.

    Args:
        file_path: Path to check
        pattern: Glob pattern

    Returns:
        True if the path matches the pattern
    """
    # Normalize both paths
    file_path = file_path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")

    # Handle ** patterns (recursive directory matching)
    if "**" in pattern:
        # Convert glob pattern to regex:
        # ** matches zero or more directories (including none)
        # * matches any character except /

        # Start building the regex
        regex = ""
        i = 0
        while i < len(pattern):
            if i < len(pattern) - 1 and pattern[i:i+2] == "**":
                # ** matches any path (including empty)
                if i + 2 < len(pattern) and pattern[i+2] == "/":
                    # **/ at start or middle - match zero or more directories
                    regex += "(?:.*/)?"
                    i += 3
                elif i > 0 and pattern[i-1] == "/":
                    # /** at end - match zero or more directories/files
                    regex += "(?:/.*)?"
                    i += 2
                else:
                    # standalone ** - match anything
                    regex += ".*"
                    i += 2
            elif pattern[i] == "*":
                # * matches any character except /
                regex += "[^/]*"
                i += 1
            elif pattern[i] in ".^$+{}[]|()":
                # Escape regex special chars
                regex += "\\" + pattern[i]
                i += 1
            else:
                regex += pattern[i]
                i += 1

        # Anchor the pattern appropriately
        if not pattern.startswith("**/"):
            regex = "^" + regex
        if not pattern.endswith("/**"):
            regex = regex + "$"

        try:
            return bool(re.search(regex, file_path))
        except re.error:
            return fnmatch(file_path, pattern)

    # Use fnmatch for simple patterns
    return fnmatch(file_path, pattern)
