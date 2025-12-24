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
Backup and Restore Utility for Pixeltable Knowledge Base.

Use this utility when:
- Intentionally upgrading Python versions
- Recovering from corrupted databases
- Creating backups before major changes

The backup/restore process:
1. Backs up existing data to Parquet files (preserving content)
2. Drops and recreates tables with fresh schema and UDFs
3. Restores data (embeddings will be recomputed)
4. Updates the version marker

Usage:
    # Backup only (safe, no modifications)
    python -m scripts.backup_restore --backup --export-dir ./backup

    # Full backup and restore (requires confirmation)
    python -m scripts.backup_restore --backup-restore --confirm

    # Full backup/restore with custom directory
    python -m scripts.backup_restore --backup-restore --confirm --export-dir ./backup

Related:
    - ADR-001: Python Version Guard
    - GitHub Issue #10
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Lazy imports
pxt = None
pd = None


def _lazy_import_pixeltable():
    """Lazily import pixeltable."""
    global pxt
    if pxt is None:
        import pixeltable as _pxt
        pxt = _pxt
    return pxt


def _lazy_import_pandas():
    """Lazily import pandas."""
    global pd
    if pd is None:
        import pandas as _pd
        pd = _pd
    return pd


def _get_pixeltable_dir() -> Path:
    """Get the Pixeltable data directory."""
    if "PIXELTABLE_HOME" in os.environ:
        return Path(os.environ["PIXELTABLE_HOME"])
    return Path.home() / ".pixeltable"


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


def export_data(export_dir: Path) -> Dict[str, Any]:
    """
    Export knowledge base data to Parquet files.

    This creates a backup of all data before migration. Parquet format
    preserves data types and is efficient for large datasets.

    Args:
        export_dir: Directory to export data to

    Returns:
        Dict with 'success', 'export_path', and 'row_count'
    """
    _lazy_import_pandas()

    try:
        kb = get_knowledge_base()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not access knowledge base: {e}",
            "row_count": 0,
        }

    # Ensure export directory exists
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    # Generate export filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = export_dir / f"org_knowledge_export_{timestamp}.parquet"

    try:
        # Select all columns except computed columns (they'll be recreated)
        # Core columns: type, path, content, title, created_at, updated_at, metadata
        rows = kb.select(
            kb.type,
            kb.path,
            kb.content,
            kb.title,
            kb.created_at,
            kb.metadata,
        ).collect()

        row_count = len(rows)

        if row_count == 0:
            # Create empty parquet file
            empty_df = pd.DataFrame(columns=["type", "path", "content", "title", "created_at", "metadata"])
            empty_df.to_parquet(export_path, index=False)
        else:
            # Convert to DataFrame and save
            df = pd.DataFrame(rows)
            df.to_parquet(export_path, index=False)

        print(f"  Exported {row_count} rows to {export_path}")

        return {
            "success": True,
            "export_path": str(export_path),
            "row_count": row_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Export failed: {e}",
            "row_count": 0,
        }


def recreate_table() -> Dict[str, Any]:
    """
    Drop and recreate the knowledge base table with fresh UDFs.

    This creates a new table with the same schema but fresh computed
    columns that use the current Python version's bytecode.

    Returns:
        Dict with 'success' and optionally 'error'
    """
    _lazy_import_pixeltable()

    try:
        # Drop existing table
        try:
            pxt.drop_table("org_knowledge", force=True)
            print("  Dropped existing org_knowledge table")
        except Exception as e:
            print(f"  Warning: Could not drop table (may not exist): {e}")

        # Create new table with fresh schema
        kb = pxt.create_table(
            "org_knowledge",
            {
                "type": pxt.String,
                "path": pxt.String,
                "content": pxt.String,
                "title": pxt.String,
                "created_at": pxt.Timestamp,
                "updated_at": pxt.Timestamp,
                "metadata": pxt.Json,
            },
        )
        print("  Created new org_knowledge table")

        # Add embedding index
        from pixeltable.functions.huggingface import sentence_transformer

        embed_model = sentence_transformer.using(
            model_id="sentence-transformers/all-MiniLM-L6-v2"
        )

        kb.add_embedding_index("content", string_embed=embed_model)
        print("  Added embedding index")

        # Add computed columns with fresh UDFs
        @pxt.udf
        def generate_summary(content: str) -> str:
            """Generate concise summary of content."""
            if len(content) < 200:
                return content
            snippet = content[:1000]
            return f"Summary: {snippet[:200]}..."

        @pxt.udf
        def is_architecture_decision(path: str, content: str) -> bool:
            """Detect if this is an architectural decision record."""
            path_lower = path.lower()
            content_lower = content.lower()
            if "/adr/" in path_lower:
                return True
            import re

            if re.search(r"#+ *adr[- ]?\d+", content_lower):
                return True
            return False

        kb.add_computed_column(summary=generate_summary(kb.content))
        kb.add_computed_column(is_adr=is_architecture_decision(kb.path, kb.content))
        print("  Added computed columns")

        return {"success": True}

    except Exception as e:
        return {
            "success": False,
            "error": f"Table recreation failed: {e}",
        }


def import_data(parquet_path: Path) -> Dict[str, Any]:
    """
    Import data from Parquet file into the knowledge base.

    Embeddings will be recomputed automatically by Pixeltable.

    Args:
        parquet_path: Path to Parquet file

    Returns:
        Dict with 'success' and 'rows_imported'
    """
    _lazy_import_pandas()

    parquet_path = Path(parquet_path)

    if not parquet_path.exists():
        return {
            "success": False,
            "error": f"Parquet file not found: {parquet_path}",
            "rows_imported": 0,
        }

    try:
        kb = get_knowledge_base()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not access knowledge base: {e}",
            "rows_imported": 0,
        }

    try:
        # Read Parquet file
        df = pd.read_parquet(parquet_path)
        rows = df.to_dict("records")

        if len(rows) == 0:
            print("  No rows to import")
            return {"success": True, "rows_imported": 0}

        # Add updated_at if missing
        for row in rows:
            if "updated_at" not in row or row["updated_at"] is None:
                row["updated_at"] = row.get("created_at", datetime.now())

        # Insert in batches for better performance
        batch_size = 100
        total_imported = 0

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            kb.insert(batch)
            total_imported += len(batch)
            print(f"  Imported {total_imported}/{len(rows)} rows...")

        print(f"  Successfully imported {total_imported} rows")

        return {
            "success": True,
            "rows_imported": total_imported,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Import failed: {e}",
            "rows_imported": 0,
        }


def update_version_marker() -> Dict[str, Any]:
    """
    Update the Python version marker to current version.

    This should be called after successful migration.

    Returns:
        Dict with 'success' and version info
    """
    pixeltable_dir = _get_pixeltable_dir()
    version_marker = pixeltable_dir / ".python_version"

    try:
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        full_version = sys.version

        # Ensure directory exists
        pixeltable_dir.mkdir(parents=True, exist_ok=True)

        # Write version marker
        version_marker.write_text(f"{current_version}\n{full_version}\n")

        print(f"  Updated version marker to {current_version}")

        return {
            "success": True,
            "version": current_version,
            "full_version": full_version,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update version marker: {e}",
        }


def full_backup_restore(
    confirm: bool = False, export_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Run the full backup and restore workflow.

    Steps:
    1. Backup existing data to Parquet
    2. Drop and recreate table with fresh UDFs
    3. Restore data (embeddings recomputed)
    4. Update version marker

    Args:
        confirm: Must be True to proceed
        export_dir: Directory for backup (defaults to current dir)

    Returns:
        Dict with 'success' and details
    """
    if not confirm:
        return {
            "success": False,
            "message": "Backup/restore requires confirmation. Use --confirm flag.",
        }

    if export_dir is None:
        export_dir = Path.cwd() / "pixeltable_backup"

    export_dir = Path(export_dir)

    print("Starting backup and restore...")
    print("=" * 50)

    # Step 1: Backup data
    print("\n1. Backing up data...")
    export_result = export_data(export_dir)
    if not export_result["success"]:
        return {
            "success": False,
            "error": export_result.get("error", "Backup failed"),
            "stage": "backup",
        }

    # Step 2: Recreate table
    print("\n2. Recreating table...")
    recreate_result = recreate_table()
    if not recreate_result["success"]:
        print(f"\nRestore failed at table recreation.")
        print(f"Your data is safely backed up at: {export_result['export_path']}")
        return {
            "success": False,
            "error": recreate_result.get("error", "Table recreation failed"),
            "stage": "recreate",
            "backup_path": export_result["export_path"],
        }

    # Step 3: Restore data
    print("\n3. Restoring data...")
    import_result = import_data(export_result["export_path"])
    if not import_result["success"]:
        print(f"\nRestore failed at data import.")
        print(f"Your data is safely backed up at: {export_result['export_path']}")
        return {
            "success": False,
            "error": import_result.get("error", "Restore failed"),
            "stage": "restore",
            "backup_path": export_result["export_path"],
        }

    # Step 4: Update version marker
    print("\n4. Updating version marker...")
    marker_result = update_version_marker()
    if not marker_result["success"]:
        print(f"Warning: Could not update version marker: {marker_result.get('error')}")

    print("\n" + "=" * 50)
    print("Backup and restore complete!")
    print(f"  Rows restored: {import_result['rows_imported']}")
    print(f"  Backup location: {export_result['export_path']}")

    return {
        "success": True,
        "backup": export_result,
        "recreate": recreate_result,
        "restore": import_result,
        "marker": marker_result,
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pixeltable Backup and Restore Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup only (safe, no modifications)
  python -m scripts.backup_restore --backup --export-dir ./backup

  # Full backup and restore
  python -m scripts.backup_restore --backup-restore --confirm

  # Full backup/restore with custom directory
  python -m scripts.backup_restore --backup-restore --confirm --export-dir ./backup
        """,
    )
    parser.add_argument(
        "--backup-restore",
        action="store_true",
        help="Run full backup and restore (backup, recreate, restore)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Only backup data (no modifications)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm operation (required with --backup-restore)",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default=None,
        help="Directory for backup files (default: ./pixeltable_backup)",
    )

    args = parser.parse_args()

    if args.backup:
        export_dir = Path(args.export_dir) if args.export_dir else Path.cwd() / "pixeltable_backup"
        result = export_data(export_dir)
        if result["success"]:
            print(f"\nBackup successful!")
            print(f"  Rows: {result['row_count']}")
            print(f"  Path: {result['export_path']}")
            sys.exit(0)
        else:
            print(f"\nBackup failed: {result.get('error')}")
            sys.exit(1)

    elif args.backup_restore:
        if not args.confirm:
            print("Error: --backup-restore requires --confirm flag")
            print("This is a safety measure for destructive operations.")
            print("\nThis operation will:")
            print("  1. Backup your data to Parquet")
            print("  2. DROP and recreate the org_knowledge table")
            print("  3. Restore data (embeddings will be recomputed)")
            print("\nRun with --confirm to proceed.")
            sys.exit(2)

        export_dir = Path(args.export_dir) if args.export_dir else None
        result = full_backup_restore(confirm=True, export_dir=export_dir)

        if result["success"]:
            sys.exit(0)
        else:
            print(f"\nBackup/restore failed: {result.get('error')}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
