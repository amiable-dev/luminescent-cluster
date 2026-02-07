#!/usr/bin/env python3
# Copyright 2024-2025 Amiable Development
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Database Health Check Utility.

Diagnoses issues with the Pixeltable knowledge base without modifying data.
For recovery operations, use scripts/backup_restore.py instead.

Usage:
    python -m scripts.db_repair --check

Related:
    - ADR-001: Python Version Guard
    - GitHub Issue #8
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import pixeltable lazily to allow version guard to run first
pxt = None

# Required computed columns that must exist in the knowledge base
REQUIRED_COMPUTED_COLUMNS = ["is_adr", "summary"]


def _lazy_import_pixeltable():
    """Lazily import pixeltable after version guard has run."""
    global pxt
    if pxt is None:
        import pixeltable as _pxt

        pxt = _pxt
    return pxt


def get_knowledge_base():
    """
    Get the org_knowledge table from Pixeltable.

    Returns:
        Pixeltable table object

    Raises:
        Exception: If table doesn't exist
    """
    _lazy_import_pixeltable()
    return pxt.get_table("org_knowledge")


def _get_pixeltable_dir() -> Path:
    """Get the Pixeltable data directory."""
    if "PIXELTABLE_HOME" in os.environ:
        return Path(os.environ["PIXELTABLE_HOME"])
    return Path.home() / ".pixeltable"


def _check_version_marker() -> Optional[Dict[str, Any]]:
    """
    Check if the version marker matches the current Python version.

    Returns:
        None if versions match, or issue dict if mismatch
    """
    pixeltable_dir = _get_pixeltable_dir()
    version_marker = pixeltable_dir / ".python_version"

    if not version_marker.exists():
        return None

    marker_content = version_marker.read_text().strip()
    marker_version = marker_content.split("\n")[0]

    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    if marker_version != current_version:
        return {
            "type": "version_mismatch",
            "message": f"Version marker shows {marker_version}, but running Python {current_version}",
            "marker_version": marker_version,
            "current_version": current_version,
        }

    return None


def _get_embedding_indices() -> List[Dict[str, Any]]:
    """
    Get all embedding indices on the knowledge base.

    Returns:
        List of index info dicts with 'name' and 'column' keys
    """
    try:
        kb = get_knowledge_base()
        indices = []

        if hasattr(kb, "_tbl_version") and hasattr(kb._tbl_version, "embedding_indices"):
            for idx in kb._tbl_version.embedding_indices:
                indices.append(
                    {
                        "name": idx.name if hasattr(idx, "name") else str(idx),
                        "column": idx.column.name if hasattr(idx, "column") else "content",
                    }
                )
        else:
            if hasattr(kb, "content") and hasattr(kb.content, "similarity"):
                indices.append({"name": "default_idx", "column": "content"})

        return indices
    except Exception as e:
        print(f"Warning: Could not get embedding indices: {e}")
        return []


def check_health() -> Dict[str, Any]:
    """
    Check the health of the Pixeltable knowledge base.

    Checks for:
    - Missing computed columns (is_adr, summary)
    - Duplicate embedding indices
    - Version marker mismatches
    - Missing embedding index on content

    Returns:
        Dict with 'healthy' (bool) and 'issues' (list of issue dicts)
    """
    issues = []

    try:
        kb = get_knowledge_base()
    except Exception as e:
        return {
            "healthy": False,
            "issues": [
                {
                    "type": "table_not_found",
                    "message": f"Could not access org_knowledge table: {e}",
                }
            ],
        }

    # Check for missing computed columns
    existing_columns = set(kb.columns.keys()) if hasattr(kb, "columns") else set()
    for col_name in REQUIRED_COMPUTED_COLUMNS:
        if col_name not in existing_columns:
            issues.append(
                {
                    "type": "missing_computed_column",
                    "message": f"Missing computed column: {col_name}",
                    "column": col_name,
                }
            )

    # Check for embedding indices
    indices = _get_embedding_indices()
    content_indices = [idx for idx in indices if idx.get("column") == "content"]

    if len(content_indices) == 0:
        issues.append(
            {
                "type": "missing_embedding_index",
                "message": "No embedding index found on 'content' column",
            }
        )
    elif len(content_indices) > 1:
        issues.append(
            {
                "type": "duplicate_index",
                "message": f"Multiple embedding indices on 'content': {[i['name'] for i in content_indices]}",
                "indices": content_indices,
            }
        )

    # Check version marker
    version_issue = _check_version_marker()
    if version_issue:
        issues.append(version_issue)

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
    }


def check_health_cli():
    """CLI entry point for health check - exits with appropriate code."""
    result = check_health()

    if result["healthy"]:
        print("Database health check: HEALTHY")
        sys.exit(0)
    else:
        print("Database health check: ISSUES FOUND")
        for issue in result["issues"]:
            print(f"  - [{issue['type']}] {issue['message']}")
        print("\nTo recover, use: python -m scripts.backup_restore --help")
        sys.exit(1)


# ========================================
# UDF Implementation Functions (for testing)
# ========================================


def is_architecture_decision_impl(path: str, content: str) -> bool:
    """
    Detect if this is an architectural decision record.

    Implementation logic (matches pixeltable_setup.py):
    - Path must contain '/adr/' directory
    - Or content has ADR-style header pattern
    """
    path_lower = path.lower()
    content_lower = content.lower()

    if "/adr/" in path_lower:
        return True

    if re.search(r"#+ *adr[- ]?\d+", content_lower):
        return True

    return False


def generate_summary_impl(content: str) -> str:
    """
    Generate concise summary of content.

    Implementation logic (matches pixeltable_setup.py):
    - Short content returned as-is
    - Long content truncated with "Summary:" prefix
    """
    if len(content) < 200:
        return content

    snippet = content[:1000]
    return f"Summary: {snippet[:200]}..."


# Module-level references (for testing compatibility)
is_architecture_decision = is_architecture_decision_impl
generate_summary = generate_summary_impl


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Pixeltable Database Health Check Utility")
    parser.add_argument("--check", action="store_true", help="Check database health")

    args = parser.parse_args()

    if args.check:
        check_health_cli()
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
