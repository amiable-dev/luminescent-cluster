# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Embedding model version tracking for index compatibility.

Tracks embedding model versions to detect when stored embeddings
are incompatible with the current model and require reindexing.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)
"""

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class EmbeddingModelProtocol(Protocol):
    """Protocol for embedding models that expose version info."""

    def get_sentence_embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        ...


@dataclass
class EmbeddingVersion:
    """Version information for an embedding model.

    Attributes:
        model_id: Full model identifier (e.g., "sentence-transformers/all-MiniLM-L6-v2").
        version_hash: SHA256 hash of model configuration.
        dimension: Embedding dimension.
        created_at: When this version was recorded.
        config_snapshot: Optional snapshot of model config for debugging.
    """

    model_id: str
    version_hash: str
    dimension: int
    created_at: datetime
    config_snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingVersion":
        """Create from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class EmbeddingVersionTracker:
    """Track embedding model versions for index compatibility.

    This class monitors embedding model versions to detect when
    the model has changed and stored embeddings need reindexing.

    Changes that require reindex:
    - Different model ID
    - Different embedding dimension
    - Different version hash (model weights changed)

    Example:
        >>> tracker = EmbeddingVersionTracker(Path("/data/embeddings"))
        >>> model = SentenceTransformer("all-MiniLM-L6-v2")
        >>> current = tracker.get_current_version(model, "all-MiniLM-L6-v2")
        >>> stored = tracker.load_stored_version()
        >>> if tracker.requires_reindex(stored):
        ...     print("Model changed, reindexing required")
    """

    VERSION_FILENAME = "embedding_version.json"

    def __init__(self, storage_path: Path):
        """Initialize the version tracker.

        Args:
            storage_path: Directory for storing version files.
        """
        self.storage_path = storage_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Create storage directory if it doesn't exist."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _compute_version_hash(
        self,
        model_id: str,
        dimension: int,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Compute a version hash for the model.

        Args:
            model_id: Model identifier.
            dimension: Embedding dimension.
            config: Optional model configuration.

        Returns:
            SHA256 hash of version-relevant information.
        """
        # Build a deterministic representation
        version_data = {
            "model_id": model_id,
            "dimension": dimension,
        }
        if config:
            # Only include version-relevant config keys
            relevant_keys = [
                "max_seq_length",
                "word_embedding_dimension",
                "pooling_mode",
            ]
            version_data["config"] = {
                k: v for k, v in config.items() if k in relevant_keys
            }

        # Compute hash
        json_str = json.dumps(version_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def get_current_version(
        self,
        model: EmbeddingModelProtocol | None = None,
        model_id: str = "unknown",
        dimension: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> EmbeddingVersion:
        """Get version information for the current model.

        Args:
            model: Optional model object with get_sentence_embedding_dimension().
            model_id: Model identifier.
            dimension: Embedding dimension (extracted from model if not provided).
            config: Optional model configuration.

        Returns:
            EmbeddingVersion for the current model.
        """
        # Get dimension from model if not provided
        if dimension is None and model is not None:
            dimension = model.get_sentence_embedding_dimension()
        elif dimension is None:
            dimension = 0  # Unknown

        version_hash = self._compute_version_hash(model_id, dimension, config)

        return EmbeddingVersion(
            model_id=model_id,
            version_hash=version_hash,
            dimension=dimension,
            created_at=datetime.now(),
            config_snapshot=config,
        )

    def save_version(self, version: EmbeddingVersion) -> None:
        """Save current version as the stored version using atomic write.

        Args:
            version: Version to save.

        Raises:
            ValueError: If target path is a symlink (potential attack).
        """
        path = self.storage_path / self.VERSION_FILENAME

        # Check for symlink attack
        if path.exists() and path.is_symlink():
            raise ValueError(
                f"Refusing to write to symlink: {path}. "
                "This may be a symlink attack."
            )

        # Write to temp file first, then atomically rename
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json.tmp",
            dir=self.storage_path,
            text=True,
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(version.to_dict(), f, indent=2)
            # Atomic rename (on POSIX systems)
            os.rename(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load_stored_version(self) -> EmbeddingVersion | None:
        """Load the stored embedding version.

        Returns:
            Stored version, or None if not found.

        Raises:
            ValueError: If path is a symlink (potential attack).
        """
        path = self.storage_path / self.VERSION_FILENAME
        if not path.exists():
            return None

        # Check for symlink attack
        if path.is_symlink():
            raise ValueError(
                f"Refusing to read symlink: {path}. "
                "This may be a symlink attack."
            )

        with open(path) as f:
            data = json.load(f)
        return EmbeddingVersion.from_dict(data)

    def is_compatible(
        self,
        stored: EmbeddingVersion,
        current: EmbeddingVersion,
    ) -> bool:
        """Check if stored embeddings are compatible with current model.

        Args:
            stored: Version of stored embeddings.
            current: Version of current model.

        Returns:
            True if compatible (no reindex needed).
        """
        # Different model IDs are incompatible
        if stored.model_id != current.model_id:
            return False

        # Different dimensions are incompatible
        if stored.dimension != current.dimension:
            return False

        # Different version hashes indicate model weights changed
        if stored.version_hash != current.version_hash:
            return False

        return True

    def requires_reindex(
        self,
        stored: EmbeddingVersion | None,
        current: EmbeddingVersion | None = None,
    ) -> bool:
        """Determine if model change requires full reindex.

        Args:
            stored: Version of stored embeddings.
            current: Version of current model (loads current if not provided).

        Returns:
            True if reindex is required.
        """
        # No stored version means first index (not reindex)
        if stored is None:
            return False

        # No current version to compare
        if current is None:
            return False

        return not self.is_compatible(stored, current)

    def get_compatibility_report(
        self,
        stored: EmbeddingVersion,
        current: EmbeddingVersion,
    ) -> dict[str, Any]:
        """Get detailed compatibility report.

        Args:
            stored: Version of stored embeddings.
            current: Version of current model.

        Returns:
            Dictionary with compatibility details.
        """
        return {
            "compatible": self.is_compatible(stored, current),
            "stored": {
                "model_id": stored.model_id,
                "version_hash": stored.version_hash,
                "dimension": stored.dimension,
                "created_at": stored.created_at.isoformat(),
            },
            "current": {
                "model_id": current.model_id,
                "version_hash": current.version_hash,
                "dimension": current.dimension,
                "created_at": current.created_at.isoformat(),
            },
            "differences": {
                "model_id_changed": stored.model_id != current.model_id,
                "dimension_changed": stored.dimension != current.dimension,
                "version_hash_changed": stored.version_hash != current.version_hash,
            },
        }

    def has_stored_version(self) -> bool:
        """Check if a stored version exists."""
        return (self.storage_path / self.VERSION_FILENAME).exists()
