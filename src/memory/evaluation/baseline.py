# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Baseline persistence for HNSW recall drift detection.

Provides storage and retrieval of recall baselines for comparing
current recall against established baselines.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)
"""

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RecallBaseline:
    """A recall baseline measurement for drift detection.

    Attributes:
        recall_at_k: The measured Recall@k value.
        k: The k value used for measurement.
        query_count: Number of queries used in measurement.
        embedding_model: ID of the embedding model used.
        embedding_version: Version hash of the embedding model.
        created_at: When the baseline was created.
        corpus_size: Number of documents in the corpus.
        filtered: Whether this baseline was for filtered search.
        filter_description: Description of the filter applied (if any).
    """

    recall_at_k: float
    k: int
    query_count: int
    embedding_model: str
    embedding_version: str
    created_at: datetime
    corpus_size: int
    filtered: bool = False
    filter_description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecallBaseline":
        """Create from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class BaselineStore:
    """Persist and load recall baselines for drift detection.

    Baselines are stored as JSON files in a directory structure:
    - baselines/
      - unfiltered.json       (default unfiltered baseline)
      - filtered_<hash>.json  (tenant-filtered baseline)
      - history/
        - 2025-01-08T10-00-00.json (historical baselines)

    History files are automatically pruned to prevent unbounded growth.

    Example:
        >>> store = BaselineStore(Path("/data/recall_baselines"))
        >>> baseline = RecallBaseline(
        ...     recall_at_k=0.95, k=10, query_count=50,
        ...     embedding_model="all-MiniLM-L6-v2",
        ...     embedding_version="abc123", corpus_size=10000,
        ...     created_at=datetime.now(),
        ... )
        >>> store.save_baseline(baseline)
        >>> loaded = store.load_baseline()
        >>> print(loaded.recall_at_k)
        0.95
    """

    UNFILTERED_FILENAME = "unfiltered.json"
    HISTORY_DIR = "history"
    MAX_HISTORY_FILES = 100  # Prevent unbounded disk usage

    def __init__(self, storage_path: Path):
        """Initialize the baseline store.

        Args:
            storage_path: Directory for storing baseline files.
        """
        self.storage_path = storage_path
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / self.HISTORY_DIR).mkdir(exist_ok=True)

    def _safe_write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Safely write JSON to file using atomic write pattern.

        Uses write-to-temp-then-rename for atomicity and checks for
        symlinks to prevent symlink attacks.

        Args:
            path: Target file path.
            data: Data to write as JSON.

        Raises:
            ValueError: If path is a symlink (potential attack).
        """
        # Check for symlink attack
        if path.exists() and path.is_symlink():
            raise ValueError(
                f"Refusing to write to symlink: {path}. "
                "This may be a symlink attack."
            )

        # Verify path is within storage directory
        if not path.resolve().is_relative_to(self.storage_path.resolve()):
            raise ValueError(f"Path {path} is outside storage directory")

        # Write to temp file first, then atomically rename
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json.tmp",
            dir=self.storage_path,
            text=True,
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            # Atomic replace (cross-platform)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _sanitize_filter_name(self, filter_name: str) -> str:
        """Sanitize filter name to prevent path traversal and PII leakage.

        Uses a pure hash-based approach to ensure:
        1. Distinct inputs always produce distinct outputs (no collisions)
        2. Output is safe for filenames (alphanumeric only)
        3. Original name is NOT stored (prevents PII leakage)

        Args:
            filter_name: The raw filter name.

        Returns:
            Hash-based identifier safe for use in filenames.

        Raises:
            ValueError: If filter_name is empty.
        """
        import hashlib

        if not filter_name:
            raise ValueError("filter_name cannot be empty")

        # Use only hash - do not preserve any part of the original name
        # This prevents PII leakage into filenames
        name_hash = hashlib.sha256(filter_name.encode("utf-8")).hexdigest()[:16]
        return name_hash

    def _get_baseline_path(self, filtered: bool, filter_name: str | None) -> Path:
        """Get the path for a baseline file.

        Args:
            filtered: Whether this is a filtered baseline.
            filter_name: Name of the filter (sanitized before use).

        Returns:
            Path to the baseline file within storage_path.

        Raises:
            ValueError: If filtered=True but filter_name is None or empty.
        """
        if filtered:
            # Require filter_name for filtered baselines to prevent
            # accidentally overwriting the global unfiltered baseline
            if not filter_name:
                raise ValueError(
                    "filter_name is required for filtered baselines. "
                    "Cannot use filtered=True with filter_name=None."
                )
            safe_name = self._sanitize_filter_name(filter_name)
            path = self.storage_path / f"filtered_{safe_name}.json"
            # Verify path stays within storage_path (defense in depth)
            if not path.resolve().is_relative_to(self.storage_path.resolve()):
                raise ValueError("Invalid filter_name: path escape detected")
            return path
        return self.storage_path / self.UNFILTERED_FILENAME

    def save_baseline(
        self,
        baseline: RecallBaseline,
        filter_name: str | None = None,
        archive_previous: bool = True,
    ) -> None:
        """Save a new baseline using atomic write.

        Args:
            baseline: The baseline to save.
            filter_name: Name for filtered baseline (e.g., "tenant", "tag").
            archive_previous: If True, move existing baseline to history.
        """
        path = self._get_baseline_path(baseline.filtered, filter_name)

        # Archive existing baseline if requested
        if archive_previous and path.exists():
            self._archive_baseline(path)

        # Save new baseline using atomic write
        self._safe_write_json(path, baseline.to_dict())

    def _archive_baseline(self, path: Path) -> None:
        """Move a baseline file to history directory using atomic write."""
        history_dir = self.storage_path / self.HISTORY_DIR

        # Read existing baseline safely (includes symlink check)
        data = self._safe_read_json(path)
        if data is None:
            return  # Nothing to archive

        # Use created_at for archive filename
        created_at = datetime.fromisoformat(data["created_at"])
        archive_name = f"{path.stem}_{created_at.strftime('%Y-%m-%dT%H-%M-%S')}.json"
        archive_path = history_dir / archive_name

        # Copy to history using atomic write
        self._safe_write_json(archive_path, data)

        # Prune old history files to prevent unbounded growth
        self._prune_history()

    def _prune_history(self) -> None:
        """Remove oldest history files to stay within MAX_HISTORY_FILES limit."""
        history_dir = self.storage_path / self.HISTORY_DIR

        # Get all history files sorted by modification time (oldest first)
        history_files = sorted(
            history_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime if not p.is_symlink() else 0,
        )

        # Remove oldest files if over limit
        files_to_remove = len(history_files) - self.MAX_HISTORY_FILES
        if files_to_remove > 0:
            for path in history_files[:files_to_remove]:
                if not path.is_symlink():  # Don't follow symlinks
                    path.unlink()

    def _safe_read_json(self, path: Path) -> dict[str, Any] | None:
        """Safely read JSON from file with symlink protection.

        Args:
            path: File path to read.

        Returns:
            Parsed JSON data, or None if file doesn't exist.

        Raises:
            ValueError: If path is a symlink (potential attack).
        """
        if not path.exists():
            return None

        # Check for symlink attack
        if path.is_symlink():
            raise ValueError(
                f"Refusing to read symlink: {path}. "
                "This may be a symlink attack."
            )

        # Verify path is within storage directory
        if not path.resolve().is_relative_to(self.storage_path.resolve()):
            raise ValueError(f"Path {path} is outside storage directory")

        with open(path) as f:
            return json.load(f)

    def load_baseline(
        self,
        filtered: bool = False,
        filter_name: str | None = None,
    ) -> RecallBaseline | None:
        """Load the current baseline.

        Args:
            filtered: Whether to load a filtered baseline.
            filter_name: Name of the filter (required if filtered=True).

        Returns:
            The loaded baseline, or None if not found.

        Raises:
            ValueError: If path is a symlink.
        """
        path = self._get_baseline_path(filtered, filter_name)
        data = self._safe_read_json(path)

        if data is None:
            return None

        return RecallBaseline.from_dict(data)

    def load_history(
        self,
        filtered: bool = False,
        filter_name: str | None = None,
        limit: int = 10,
    ) -> list[RecallBaseline]:
        """Load historical baselines.

        Args:
            filtered: Whether to load filtered baseline history.
            filter_name: Name of the filter (sanitized before use in glob).
            limit: Maximum number of historical baselines to return.

        Returns:
            List of baselines sorted by created_at descending (newest first).

        Raises:
            ValueError: If filtered=True but filter_name is None or empty.
        """
        history_dir = self.storage_path / self.HISTORY_DIR

        if filtered:
            # Require and sanitize filter_name for filtered history
            if not filter_name:
                raise ValueError(
                    "filter_name is required for filtered baseline history. "
                    "Cannot use filtered=True with filter_name=None."
                )
            safe_name = self._sanitize_filter_name(filter_name)
            prefix = f"filtered_{safe_name}_"
        else:
            prefix = "unfiltered_"

        baselines = []
        for path in history_dir.glob(f"{prefix}*.json"):
            # Use safe read to check symlinks and path containment
            try:
                data = self._safe_read_json(path)
                if data is None:
                    continue  # Skip files that couldn't be read
                baselines.append(RecallBaseline.from_dict(data))
            except ValueError:
                # Skip symlinks or files outside storage path
                continue

        # Sort by created_at descending
        baselines.sort(key=lambda b: b.created_at, reverse=True)
        return baselines[:limit]

    def compute_drift(self, current_recall: float, baseline: RecallBaseline) -> float:
        """Calculate relative drift percentage from baseline.

        Args:
            current_recall: Current Recall@k measurement.
            baseline: Baseline to compare against.

        Returns:
            Relative drift as a percentage (e.g., 0.05 for 5% drift).
            Positive values indicate degradation (current < baseline).
        """
        if baseline.recall_at_k == 0:
            return 0.0

        drift = (baseline.recall_at_k - current_recall) / baseline.recall_at_k
        return drift

    def has_baseline(
        self,
        filtered: bool = False,
        filter_name: str | None = None,
    ) -> bool:
        """Check if a baseline exists.

        Args:
            filtered: Whether to check for filtered baseline.
            filter_name: Name of the filter.

        Returns:
            True if baseline exists.
        """
        path = self._get_baseline_path(filtered, filter_name)
        return path.exists()

    def delete_baseline(
        self,
        filtered: bool = False,
        filter_name: str | None = None,
    ) -> bool:
        """Delete a baseline file.

        Args:
            filtered: Whether to delete filtered baseline.
            filter_name: Name of the filter.

        Returns:
            True if file was deleted, False if it didn't exist.
        """
        path = self._get_baseline_path(filtered, filter_name)
        if path.exists():
            path.unlink()
            return True
        return False
