# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Baseline persistence for HNSW recall drift detection.

Provides storage and retrieval of recall baselines for comparing
current recall against established baselines.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)
"""

import json
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
      - filtered_tenant.json  (tenant-filtered baseline)
      - history/
        - 2025-01-08T10-00-00.json (historical baselines)

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

    def _get_baseline_path(self, filtered: bool, filter_name: str | None) -> Path:
        """Get the path for a baseline file."""
        if filtered and filter_name:
            return self.storage_path / f"filtered_{filter_name}.json"
        return self.storage_path / self.UNFILTERED_FILENAME

    def save_baseline(
        self,
        baseline: RecallBaseline,
        filter_name: str | None = None,
        archive_previous: bool = True,
    ) -> None:
        """Save a new baseline.

        Args:
            baseline: The baseline to save.
            filter_name: Name for filtered baseline (e.g., "tenant", "tag").
            archive_previous: If True, move existing baseline to history.
        """
        path = self._get_baseline_path(baseline.filtered, filter_name)

        # Archive existing baseline if requested
        if archive_previous and path.exists():
            self._archive_baseline(path)

        # Save new baseline
        with open(path, "w") as f:
            json.dump(baseline.to_dict(), f, indent=2)

    def _archive_baseline(self, path: Path) -> None:
        """Move a baseline file to history directory."""
        history_dir = self.storage_path / self.HISTORY_DIR

        # Read existing baseline to get timestamp
        with open(path) as f:
            data = json.load(f)

        # Use created_at for archive filename
        created_at = datetime.fromisoformat(data["created_at"])
        archive_name = f"{path.stem}_{created_at.strftime('%Y-%m-%dT%H-%M-%S')}.json"
        archive_path = history_dir / archive_name

        # Copy to history
        with open(archive_path, "w") as f:
            json.dump(data, f, indent=2)

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
        """
        path = self._get_baseline_path(filtered, filter_name)

        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

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
            filter_name: Name of the filter.
            limit: Maximum number of historical baselines to return.

        Returns:
            List of baselines sorted by created_at descending (newest first).
        """
        history_dir = self.storage_path / self.HISTORY_DIR
        prefix = f"filtered_{filter_name}_" if filtered and filter_name else "unfiltered_"

        baselines = []
        for path in history_dir.glob(f"{prefix}*.json"):
            with open(path) as f:
                data = json.load(f)
            baselines.append(RecallBaseline.from_dict(data))

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
