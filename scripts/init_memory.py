#!/usr/bin/env python3
# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
ADR-002: Bootstrap knowledge base for fresh clone.

This script initializes the knowledge base with existing documentation
after cloning the repository. It should be run once after cloning.

Usage:
    python scripts/init_memory.py [--force]

Options:
    --force     Re-ingest even if KB appears to be initialized

Related: ADR-002 Workflow Integration
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    # Try git first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback to script location
    return Path(__file__).parent.parent


def get_head_sha() -> str:
    """Get current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "unknown"


def bootstrap_memory(project_root: Path, force: bool = False) -> bool:
    """Ingest existing documentation for fresh clones.

    Args:
        project_root: Project root directory
        force: Re-ingest even if already initialized

    Returns:
        True if bootstrap succeeded
    """
    print("=" * 60)
    print("ADR-002: Bootstrapping Knowledge Base")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print()

    # Check if already initialized
    state_dir = project_root / ".agent" / "state"
    last_ingest_file = state_dir / "last_ingest_sha"

    if last_ingest_file.exists() and not force:
        last_sha = last_ingest_file.read_text().strip()
        print(f"Knowledge base already initialized (last ingest: {last_sha[:8]})")
        print("Use --force to re-initialize")
        return True

    # Create directories
    state_dir.mkdir(parents=True, exist_ok=True)
    (project_root / ".agent" / "logs").mkdir(parents=True, exist_ok=True)
    (project_root / ".claude" / "skills").mkdir(parents=True, exist_ok=True)

    # Import pixeltable setup
    try:
        sys.path.insert(0, str(project_root))
        from pixeltable_setup import setup_knowledge_base, ingest_codebase
    except ImportError as e:
        print(f"ERROR: Could not import pixeltable_setup: {e}")
        print("Make sure you have the project dependencies installed.")
        return False

    try:
        print("Initializing knowledge base...")
        kb = setup_knowledge_base()
        print("  Knowledge base ready")

        # Ingest docs directory
        docs_dir = project_root / "docs"
        if docs_dir.exists():
            print(f"\nIngesting documentation from {docs_dir}...")
            ingest_codebase(kb, str(docs_dir), service_name="luminescent-cluster")
            print("  Documentation ingested")
        else:
            print(f"  No docs directory found at {docs_dir}")

        # Record initial state
        head_sha = get_head_sha()
        last_ingest_file.write_text(head_sha)
        print(f"\nRecorded last ingest SHA: {head_sha[:8]}")

        print()
        print("=" * 60)
        print("Bootstrap complete!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Run: ./scripts/install_hooks.sh")
        print("  2. Start coding - hooks will auto-sync on commit")
        print()

        return True

    except Exception as e:
        print(f"ERROR: Bootstrap failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap knowledge base for fresh clone (ADR-002)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-ingest even if KB appears to be initialized"
    )

    args = parser.parse_args()

    project_root = get_project_root()
    success = bootstrap_memory(project_root, force=args.force)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
