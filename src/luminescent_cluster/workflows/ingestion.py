# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Single-file ingestion for ADR-002 workflow integration.

This module provides:
- ingest_file() for single file ingestion into Pixeltable KB
- compute_content_hash() for idempotency checking
- Metadata extraction (commit_sha, branch, timestamp)

Related: ADR-002 Workflow Integration, Phase 1 (Core Infrastructure)
"""

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import re

from .config import WorkflowConfig, load_config, should_ingest_file

# Regex to validate commit SHA (7-40 hex characters)
COMMIT_SHA_PATTERN = re.compile(r'^[0-9a-fA-F]{7,40}$')


def get_knowledge_base():
    """Get the Pixeltable knowledge base.

    This function imports and returns the knowledge base instance.
    Separated for easy mocking in tests.
    """
    from pixeltable_setup import setup_knowledge_base
    return setup_knowledge_base()


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content for idempotency.

    Args:
        content: The text content to hash

    Returns:
        SHA256 hex digest of the content
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def ingest_file(
    file_path: str,
    commit_sha: str,
    project_root: Optional[Path] = None,
    config: Optional[WorkflowConfig] = None,
) -> Dict[str, Any]:
    """Ingest a single file into the Pixeltable knowledge base.

    Args:
        file_path: Path to the file (absolute or relative to project_root)
        commit_sha: Git commit SHA for this ingestion
        project_root: Project root directory (for relative path calculation)
        config: WorkflowConfig (loaded from project_root if not provided)

    Returns:
        Dict with:
            - success: bool indicating if ingestion succeeded
            - skipped: bool if file was skipped (duplicate, excluded)
            - reason: str explaining failure or skip reason
            - path: str relative path of the file
    """
    try:
        # Validate commit_sha (security: prevent injection attacks)
        if not commit_sha or not COMMIT_SHA_PATTERN.match(commit_sha):
            return {
                "success": False,
                "reason": f"Invalid commit SHA format: {commit_sha}",
                "path": str(file_path),
            }

        # Resolve paths
        file_path = Path(file_path)
        if project_root is None:
            project_root = Path.cwd()
        else:
            project_root = Path(project_root)

        # Make file_path absolute if it isn't
        if not file_path.is_absolute():
            file_path = project_root / file_path

        # Calculate relative path for storage
        # Use canonical path to prevent traversal attacks (e.g., docs/../secrets.env)
        # FAIL-CLOSED: If path cannot be resolved relative to root, reject it
        try:
            canonical_path = file_path.resolve()
            canonical_root = project_root.resolve()
            relative_path = str(canonical_path.relative_to(canonical_root))
        except ValueError:
            # Path is outside project root - reject (fail-closed)
            return {
                "success": False,
                "skipped": True,
                "reason": f"Path outside project root: {file_path}",
                "path": str(file_path),
            }

        # Normalize path separators and remove any remaining traversal
        relative_path = relative_path.replace("\\", "/")

        # Reject paths that still contain .. after resolution (defense in depth)
        if ".." in relative_path:
            return {
                "success": False,
                "skipped": True,
                "reason": f"Rejected path with traversal: {relative_path}",
                "path": relative_path,
            }

        # Security: Reject paths with null bytes (null byte injection prevention)
        # Python 3 largely handles this, but defense-in-depth for embedded nulls
        if "\x00" in relative_path:
            return {
                "success": False,
                "skipped": True,
                "reason": f"Rejected path with null bytes",
                "path": str(file_path),
            }

        # Security: Reject paths starting with hyphen (argument injection prevention)
        # Git commands could interpret "-filename.md" as a flag
        if relative_path.startswith("-"):
            return {
                "success": False,
                "skipped": True,
                "reason": f"Rejected path starting with hyphen: {relative_path}",
                "path": relative_path,
            }

        # Load config if not provided
        if config is None:
            config = load_config(project_root)

        # Note: We intentionally DO NOT check working tree existence or follow symlinks.
        # We read from the git object database (git show commit:path), not the working tree.
        # Working tree state is irrelevant for provenance integrity - we ingest exactly
        # what was committed. The blob existence check (_get_blob_size) handles non-existent
        # paths by returning None, causing the file to be skipped.

        # Policy check: enforce include/exclude patterns from config
        if not should_ingest_file(relative_path, config):
            return {
                "success": False,
                "skipped": True,
                "reason": f"File excluded by policy (include/exclude patterns): {relative_path}",
                "path": relative_path,
            }

        # Check blob size BEFORE reading content (DoS prevention - fail-closed)
        # This prevents loading large files into memory before checking size
        # If we can't determine size, we fail-closed (reject file) for safety
        blob_size = _get_blob_size(relative_path, commit_sha, project_root)
        if blob_size is None:
            return {
                "success": False,
                "skipped": True,
                "reason": f"Cannot determine blob size (file may not exist in commit {commit_sha[:8]})",
                "path": relative_path,
            }
        blob_size_kb = blob_size / 1024
        if blob_size_kb > config.max_file_size_kb:
            return {
                "success": False,
                "skipped": True,
                "reason": f"File too large ({blob_size_kb:.1f}KB > {config.max_file_size_kb}KB)",
                "path": relative_path,
            }

        # Read content from git object database (not working tree) for provenance integrity
        # This ensures we ingest exactly what was committed, not potentially modified working tree
        # NO FALLBACK to working tree - if git fails, we skip (maintains provenance integrity)
        content = _read_committed_content(relative_path, commit_sha, project_root)
        if content is None:
            return {
                "success": False,
                "skipped": True,
                "reason": f"Could not read from git object database (commit: {commit_sha[:8]})",
                "path": relative_path,
            }

        # Check if binary content (null bytes indicate binary)
        if config.skip_binary and "\x00" in content:
            return {
                "success": False,
                "skipped": True,
                "reason": "Skipped binary file",
                "path": relative_path,
            }

        # Compute content hash for idempotency
        content_hash = compute_content_hash(content)

        # Get knowledge base
        kb = get_knowledge_base()

        # Check if this content already exists (idempotency)
        existing = kb.where(kb.path == relative_path).select(kb.metadata).collect()
        if existing:
            existing_hash = existing[0].get("metadata", {}).get("content_hash")
            if existing_hash == content_hash:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Content unchanged (same hash)",
                    "path": relative_path,
                }
            # Content changed - delete old entry before inserting new
            kb.where(kb.path == relative_path).delete()

        # Get git branch
        branch = _get_git_branch(project_root)

        # Determine content type
        content_type = _determine_content_type(relative_path, content)

        # Prepare metadata
        metadata = {
            "commit_sha": commit_sha,
            "branch": branch,
            "content_hash": content_hash,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        # Prepare record for insertion
        record = {
            "type": content_type,
            "path": relative_path,
            "content": content,
            "service": "luminescent-cluster",
            "created_at": datetime.now(timezone.utc),
            "metadata": metadata,
        }

        # Insert into knowledge base
        kb.insert([record])

        return {
            "success": True,
            "skipped": False,
            "path": relative_path,
            "content_hash": content_hash,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "reason": f"Ingestion error: {e}",
            "path": str(file_path),
        }


def _is_blob(relative_path: str, commit_sha: str, project_root: Path) -> bool:
    """Check if the git object at path is a blob (file), not a tree (directory).

    Prevents ingestion of directory listings by verifying object type.

    Args:
        relative_path: Path relative to project root
        commit_sha: Git commit SHA
        project_root: Project root directory

    Returns:
        True if the object is a blob (file), False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", f"{commit_sha}:{relative_path}"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            obj_type = result.stdout.strip()
            return obj_type == "blob"
        return False
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _get_blob_size(relative_path: str, commit_sha: str, project_root: Path) -> Optional[int]:
    """Get the size of a blob in the git object database.

    Used for DoS prevention - check size before loading content into memory.

    Args:
        relative_path: Path relative to project root
        commit_sha: Git commit SHA
        project_root: Project root directory

    Returns:
        Blob size in bytes, or None if git command fails or not a blob
    """
    try:
        # First verify it's a blob (file), not a tree (directory)
        # This prevents ingestion of directory listings
        if not _is_blob(relative_path, commit_sha, project_root):
            return None

        # Note: cat-file uses <commit>:<path> format which doesn't need -- separator
        # The path is part of the object specifier, not a positional argument
        result = subprocess.run(
            ["git", "cat-file", "-s", f"{commit_sha}:{relative_path}"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
        return None
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        return None


def _read_committed_content(relative_path: str, commit_sha: str, project_root: Path) -> Optional[str]:
    """Read file content from git object database at specific commit.

    This ensures we ingest exactly what was committed, not working tree state.
    Prevents race conditions where files are modified between commit and ingestion.

    Uses binary mode with explicit decode to handle non-UTF-8 files gracefully
    (errors='replace' prevents crashes on malformed encodings).

    Args:
        relative_path: Path relative to project root
        commit_sha: Git commit SHA to read from
        project_root: Project root directory

    Returns:
        File content as string, or None if git show fails
    """
    try:
        # Note: git show uses <commit>:<path> format which doesn't need -- separator
        # The path is part of the object specifier, not a positional argument
        # Use binary mode to avoid UnicodeDecodeError on non-UTF-8 files
        result = subprocess.run(
            ["git", "show", f"{commit_sha}:{relative_path}"],
            cwd=project_root,
            capture_output=True,
            text=False,  # Binary mode for explicit decode
            timeout=10,
        )
        if result.returncode == 0:
            # Decode with error handling to prevent crashes on non-UTF-8 content
            # errors='replace' substitutes invalid bytes with U+FFFD
            return result.stdout.decode("utf-8", errors="replace")
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _get_git_branch(project_root: Path) -> str:
    """Get the current git branch name.

    Args:
        project_root: Project root directory

    Returns:
        Branch name or "unknown" if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "HEAD"
        return "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _determine_content_type(path: str, content: str) -> str:
    """Determine the content type based on path and content.

    Args:
        path: File path
        content: File content

    Returns:
        Content type: "decision" for ADRs, "documentation" otherwise
    """
    path_lower = path.lower()

    # ADRs are decision documents
    if "adr" in path_lower or "adr-" in path_lower:
        return "decision"

    # Check content for ADR markers
    content_lower = content.lower()
    if "## status" in content_lower and "## decision" in content_lower:
        return "decision"

    # Default to documentation
    return "documentation"
