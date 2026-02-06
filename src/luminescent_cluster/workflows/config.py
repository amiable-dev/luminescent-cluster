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

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional

import yaml

# Hard limits to prevent DoS via malicious config
# These cannot be overridden by .agent/config.yaml
MAX_FILE_SIZE_KB_HARD_LIMIT = 10240  # 10MB absolute maximum
MIN_FILE_SIZE_KB = 1  # Minimum 1KB


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

# Glob patterns for detecting secrets files (fnmatch-based, not regex)
# Using glob patterns instead of regex to prevent ReDoS attacks from user config
DEFAULT_SECRETS_PATTERNS = [
    "*.env",           # .env files
    "*.env.*",         # .env.local, .env.production, etc.
    "**/.env",         # .env in any directory
    "**/.env.*",       # .env.* in any directory
    "*.key",           # Private key files
    "*.pem",           # PEM certificate/key files
    "*secret*",        # Any file with "secret" in name
    "*password*",      # Any file with "password" in name
    "*token*",         # Any file with "token" in name
    "*credential*",    # Any file with "credential" in name
]


@dataclass
class WorkflowConfig:
    """Configuration for workflow ingestion.

    Attributes:
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        max_file_size_kb: Maximum file size in KB to ingest
        skip_binary: Whether to skip binary files
        secrets_patterns: Glob patterns for detecting secrets files (fnmatch-based)
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
    if config_secrets and isinstance(config_secrets, list):
        # Extend with user-defined patterns (don't replace defaults for safety)
        # Filter to strings only to prevent type errors
        secrets_patterns.extend(p for p in config_secrets if isinstance(p, str))

    # Validate and clamp max_file_size_kb to prevent DoS via malicious config
    # If config is controlled by untrusted repo, this prevents memory exhaustion
    raw_max_size = ingestion.get("max_file_size_kb", 500)
    if not isinstance(raw_max_size, (int, float)):
        raw_max_size = 500  # Default if invalid type
    max_file_size_kb = max(MIN_FILE_SIZE_KB, min(int(raw_max_size), MAX_FILE_SIZE_KB_HARD_LIMIT))

    # Validate include/exclude patterns are lists of strings
    include_patterns = ingestion.get("include", DEFAULT_INCLUDE_PATTERNS.copy())
    if not isinstance(include_patterns, list):
        include_patterns = DEFAULT_INCLUDE_PATTERNS.copy()
    else:
        include_patterns = [p for p in include_patterns if isinstance(p, str)]

    exclude_patterns = ingestion.get("exclude", DEFAULT_EXCLUDE_PATTERNS.copy())
    if not isinstance(exclude_patterns, list):
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS.copy()
    else:
        exclude_patterns = [p for p in exclude_patterns if isinstance(p, str)]

    return WorkflowConfig(
        include_patterns=include_patterns or DEFAULT_INCLUDE_PATTERNS.copy(),
        exclude_patterns=exclude_patterns or DEFAULT_EXCLUDE_PATTERNS.copy(),
        max_file_size_kb=max_file_size_kb,
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

    Uses fnmatch (glob patterns) instead of regex to prevent ReDoS attacks
    from user-configurable patterns in .agent/config.yaml.

    Args:
        file_path: Path to the file (can be relative or absolute)
        secrets_patterns: Glob patterns to match (defaults to DEFAULT_SECRETS_PATTERNS)

    Returns:
        True if the file appears to be a secrets file
    """
    # Normalize path and get filename
    file_path = file_path.replace("\\", "/")
    path_lower = file_path.lower()

    # Use provided patterns or defaults
    patterns = secrets_patterns if secrets_patterns is not None else DEFAULT_SECRETS_PATTERNS

    for pattern in patterns:
        # Use _matches_pattern for consistent glob handling (supports **)
        if _matches_pattern(path_lower, pattern.lower()):
            return True

    return False


def _matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a glob pattern.

    Uses safe pattern matching without regex to prevent ReDoS vulnerabilities.
    Handles ** for recursive directory matching using simple string operations.

    Args:
        file_path: Path to check
        pattern: Glob pattern (supports *, **, ?)

    Returns:
        True if the path matches the pattern
    """
    # Normalize both paths to forward slashes
    file_path = file_path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")

    # Split path and pattern into components
    path_parts = file_path.split("/")
    pattern_parts = pattern.split("/")

    # Handle ** patterns using simple component matching (no regex, no ReDoS)
    if "**" in pattern:
        # Pattern like "**/dir/**" - check if 'dir' appears anywhere in path
        # This handles the common case of exclude patterns
        if pattern.startswith("**/") and pattern.endswith("/**"):
            # Extract the middle part (e.g., "node_modules" from "**/node_modules/**")
            middle = pattern[3:-3]  # Remove **/ and /**
            if "/" not in middle:
                # Simple case: check if this directory name appears in path
                return middle in path_parts
            else:
                # Complex case: check if the middle sequence appears
                middle_parts = middle.split("/")
                for i in range(len(path_parts) - len(middle_parts) + 1):
                    if path_parts[i:i+len(middle_parts)] == middle_parts:
                        return True
                return False

        # Pattern like "**/suffix" - check if path ends with suffix
        if pattern.startswith("**/"):
            suffix = pattern[3:]  # Remove **/
            return _fnmatch_parts(path_parts, suffix.split("/"))

        # Pattern like "prefix/**" - check if path starts with prefix
        if pattern.endswith("/**"):
            prefix = pattern[:-3]  # Remove /**
            prefix_parts = prefix.split("/")
            if len(path_parts) < len(prefix_parts):
                return False
            for i, ppart in enumerate(prefix_parts):
                if not fnmatch(path_parts[i], ppart):
                    return False
            return True

        # Pattern like "prefix/**/suffix" - complex recursive pattern
        # For safety, use a simple substring approach
        if "/**/" in pattern:
            prefix, suffix = pattern.split("/**/", 1)
            # Check if prefix matches start and suffix matches any later part
            prefix_parts = prefix.split("/") if prefix else []
            suffix_parts = suffix.split("/") if suffix else []

            # Verify prefix
            if prefix_parts:
                if len(path_parts) < len(prefix_parts):
                    return False
                for i, ppart in enumerate(prefix_parts):
                    if not fnmatch(path_parts[i], ppart):
                        return False

            # Check if suffix appears anywhere after prefix
            if suffix_parts:
                return _fnmatch_parts(path_parts[len(prefix_parts):], suffix_parts)
            return True

    # Use fnmatch for simple patterns (no **)
    return fnmatch(file_path, pattern)


def _fnmatch_parts(path_parts: list, pattern_parts: list) -> bool:
    """Check if pattern_parts matches the suffix of path_parts using fnmatch.

    This anchors matching to the END of the path to prevent policy bypass.
    E.g., pattern "*.md" should only match files ending in .md, not directories.
    """
    if len(pattern_parts) > len(path_parts):
        return False

    # Only match at the end (suffix matching) to prevent policy bypass
    # E.g., "docs/readme.md/secret.key" should NOT match "*.md"
    start = len(path_parts) - len(pattern_parts)
    for i, ppart in enumerate(pattern_parts):
        if not fnmatch(path_parts[start + i], ppart):
            return False
    return True
