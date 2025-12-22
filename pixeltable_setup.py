"""
Pixeltable Long-term Memory Setup

Creates persistent knowledge base for:
- Code repositories
- Architectural Decision Records (ADRs)
- Production incidents
- Meeting transcripts
- Design artifacts

This is Tier 2 memory - persistent, searchable, multimodal.

IMPORTANT: This module uses Pixeltable which serializes UDFs using pickle.
The database is bound to the Python version that created it.
See ADR-001 for details on Python version requirements.
"""

# CRITICAL: Version guard must run BEFORE any pixeltable import (ADR-001)
from src.version_guard import enforce_python_version
enforce_python_version()

import pixeltable as pxt  # Safe to import after version guard
from typing import Optional, Dict, Any, List
import os
from pathlib import Path
import json
import re
import subprocess


def _infer_service_name(file_path: str) -> Optional[str]:
    """
    Auto-infer service name from project configuration files.
    
    Walks up directory tree looking for:
    1. pyproject.toml (Python projects)
    2. package.json (Node.js projects)
    3. Git remote URL
    
    Args:
        file_path: Path to a file in the project
        
    Returns:
        Inferred service name or None if unable to infer
    """
    current_path = Path(file_path).resolve()
    
    # If file_path is a file, start from its parent directory
    if current_path.is_file():
        current_path = current_path.parent
    
    # Walk up directory tree (limit to 10 levels to avoid infinite loops)
    for _ in range(10):
        # Check for pyproject.toml
        pyproject_path = current_path / 'pyproject.toml'
        if pyproject_path.exists():
            try:
                import tomli
                with open(pyproject_path, 'rb') as f:
                    data = tomli.load(f)
                    # Try different common locations for project name
                    name = (data.get('project', {}).get('name') or 
                           data.get('tool', {}).get('poetry', {}).get('name'))
                    if name:
                        return name
            except Exception:
                # If tomli not available, try basic parsing
                try:
                    with open(pyproject_path, 'r') as f:
                        content = f.read()
                        match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                        if match:
                            return match.group(1)
                except Exception:
                    pass
        
        # Check for package.json
        package_json_path = current_path / 'package.json'
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r') as f:
                    data = json.load(f)
                    name = data.get('name')
                    if name:
                        # Remove npm scope if present (e.g., @org/package -> package)
                        return name.split('/')[-1]
            except Exception:
                pass
        
        # Check if this is a git repository root
        git_dir = current_path / '.git'
        if git_dir.exists():
            try:
                # Try to get remote URL
                result = subprocess.run(
                    ['git', 'config', '--get', 'remote.origin.url'],
                    cwd=current_path,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    url = result.stdout.strip()
                    # Extract repo name from URL
                    # Handles: git@github.com:org/repo.git, https://github.com/org/repo.git
                    match = re.search(r'[:/]([^/]+)/([^/]+?)(\.git)?$', url)
                    if match:
                        return match.group(2)
            except Exception:
                pass
        
        # Move up one directory
        parent = current_path.parent
        if parent == current_path:  # Reached root
            break
        current_path = parent
    
    return None


def _upsert_entry(kb, entry: Dict[str, Any]) -> bool:
    """
    Insert or update an entry in the knowledge base.
    
    Uses (service, path) as composite unique key. If entry exists:
    - Updates content, title, type (with promotion logic), and updated_at
    - Preserves created_at from original entry
    
    Type promotion logic:
    - documentation → decision (decisions are more specific)
    - decision → decision (no change)
    
    Args:
        kb: Knowledge base table
        entry: Entry dict with keys: type, path, content, title, metadata, etc.
        
    Returns:
        True if updated existing entry, False if inserted new entry
    """
    from datetime import datetime
    
    service = entry.get('metadata', {}).get('service', 'unknown')
    path = entry['path']
    
    # Query for existing entry with same (service, path)
    # Note: We can't directly filter on metadata['service'] in WHERE clause
    # so we need to fetch and filter in Python
    # Query for existing entry with same path
    # Optimization: Filter by path in the database query instead of fetching all rows
    try:
        # Filter by path first (indexed/primary identifier)
        # Note: We still need to check service match in Python because of metadata JSON structure
        existing_matches = kb.where(kb.path == path).select(
            kb.type, kb.path, kb.content, kb.title, 
            kb.created_at, kb.metadata
        ).collect()
        
        existing = None
        for row in existing_matches:
            row_meta = row.get('metadata', {})
            row_service = row_meta.get('service', 'unknown') if isinstance(row_meta, dict) else 'unknown'
            if row_service == service:
                existing = row
                break
        
        if existing:
            # Entry exists - perform update
            new_type = entry['type']
            old_type = existing['type']
            
            # Type promotion logic
            if old_type == 'documentation' and new_type == 'decision':
                final_type = 'decision'  # Promote
            elif old_type == 'decision':
                final_type = 'decision'  # Keep as decision
            else:
                final_type = new_type  # Use new type
            
            # Update the entry using Pixeltable's update syntax
            # Need to match on both path AND service (composite key)
            # Since we can't filter on JSON fields in WHERE, we delete and re-insert
            kb.delete(kb.path == path)
            
            # Re-insert with updated values
            entry['type'] = final_type
            entry['created_at'] = existing.get('created_at', datetime.now())
            entry['updated_at'] = datetime.now()
            kb.insert([entry])
            return True
        else:
            # Entry doesn't exist - insert new
            entry['created_at'] = entry.get('created_at', datetime.now())
            entry['updated_at'] = datetime.now()
            kb.insert([entry])
            return False
            
    except Exception as e:
        # If upsert fails, fall back to insert
        print(f"  Warning: Upsert failed for {path}, falling back to insert: {e}")
        entry['created_at'] = entry.get('created_at', datetime.now())
        entry['updated_at'] = datetime.now()
        kb.insert([entry])
        return False


def setup_knowledge_base():
    """Initialize Pixeltable knowledge base with computed columns"""
    
    # Check if table already exists
    try:
        kb = pxt.get_table('org_knowledge')
        print("Knowledge base already exists")
        
        # Check if updated_at column exists, add it if missing (schema migration)
        try:
            # Try to access the column
            _ = kb.updated_at
            print("  ✓ updated_at column already exists")
        except AttributeError:
            # Column doesn't exist, add it
            print("  Adding updated_at column (schema migration)...")
            from datetime import datetime
            kb.add_column(updated_at=pxt.Timestamp)
            # Set initial value for existing rows to created_at
            kb.update({}, {'updated_at': kb.created_at})
            print("  ✓ Added updated_at column and migrated existing rows")
        except Exception as e:
            print(f"  Warning: Could not add updated_at column: {e}")
        
        return kb
    except Exception as e:
        # Table doesn't exist, create it
        if "does not exist" not in str(e).lower():
            # Some other error
            print(f"Warning while checking for existing table: {e}")
    
    # Create main knowledge base table
    kb = pxt.create_table(
        'org_knowledge',
        {
            'type': pxt.String,           # 'code', 'decision', 'incident', 'meeting'
            'path': pxt.String,           # File path or URL
            'content': pxt.String,        # Main content
            'title': pxt.String,          # Short title
            'created_at': pxt.Timestamp,  # When created
            'updated_at': pxt.Timestamp,  # When last updated (for upsert tracking)
            'metadata': pxt.Json,         # Additional metadata
        }
    )
    
    print("✓ Created org_knowledge table")
    
    # Add embedding index for semantic search
    from pixeltable.functions.huggingface import sentence_transformer
    
    embed_model = sentence_transformer.using(
        model_id='sentence-transformers/all-MiniLM-L6-v2'
    )
    
    kb.add_embedding_index('content', string_embed=embed_model)
    print("✓ Added embedding index")
    
    # Add computed column for auto-summarization
    from pixeltable.functions import openai
    
    @pxt.udf
    def generate_summary(content: str) -> str:
        """Generate concise summary of content"""
        if len(content) < 200:
            return content
        
        # Take first 1000 chars to avoid token limits
        snippet = content[:1000]
        return f"Summary: {snippet[:200]}..."
    
    kb.add_computed_column(
        summary=generate_summary(kb.content)
    )
    print("✓ Added summary computed column")
    
    # Add computed column to identify ADRs
    @pxt.udf
    def is_architecture_decision(path: str, content: str) -> bool:
        """Detect if this is an architectural decision record.

        Tightened logic to reduce false positives:
        - Path must contain '/adr/' directory (not just 'adr' anywhere)
        - Or content has ADR-style header pattern
        """
        path_lower = path.lower()
        content_lower = content.lower()

        # Must be in an /adr/ directory
        if '/adr/' in path_lower:
            return True

        # Or have ADR-style header (e.g., "# ADR-001:" or "## ADR 001:")
        import re
        if re.search(r'#+ *adr[- ]?\d+', content_lower):
            return True

        return False
    
    kb.add_computed_column(
        is_adr=is_architecture_decision(kb.path, kb.content)
    )
    print("✓ Added ADR detection column")
    
    return kb


def setup_meetings_table():
    """Create table for meeting recordings and transcripts"""
    
    try:
        meetings = pxt.get_table('meetings')
        print("Meetings table already exists")
        return meetings
    except Exception:
        pass
    
    meetings = pxt.create_table(
        'meetings',
        {
            'title': pxt.String,
            'date': pxt.Timestamp,
            'attendees': pxt.Json,         # List of attendees
            'audio_path': pxt.String,      # Path to audio file
            'transcript': pxt.String,      # Will be computed
            'topics': pxt.Json,            # Tags/topics
        }
    )
    
    print("✓ Created meetings table")
    
    # Add embedding index on transcripts
    from pixeltable.functions.huggingface import sentence_transformer
    
    embed_model = sentence_transformer.using(
        model_id='sentence-transformers/all-MiniLM-L6-v2'
    )
    
    meetings.add_embedding_index('transcript', string_embed=embed_model)
    print("✓ Added transcript embedding index")
    
    return meetings


from datetime import datetime

def ingest_codebase(kb, repo_path: str, service_name: str, extensions: set = None):
    """
    Ingest code files from a repository into the knowledge base.
    
    This function filters files by extension to avoid ingesting:
    - Binary files (images, executables, compiled artifacts)
    - Generated files (build outputs, node_modules, vendor dirs)
    - Non-text formats that don't benefit from embedding-based search
    
    By filtering, we:
    1. Reduce storage costs (only index source code, not binaries)
    2. Improve search quality (embeddings work best on human-written text)
    3. Speed up ingestion (skip large binary/generated files)
    
    Args:
        kb: Pixeltable knowledge base table
        repo_path: Path to repository (absolute or relative)
        service_name: Service identifier for tagging (e.g., 'auth-service')
        extensions: Optional set of file extensions to include (e.g., {'.rs', '.py'})
                   If None, uses comprehensive default set covering most languages.
    
    Returns:
        int: Number of files successfully ingested
    
    Example:
        # Use defaults (Python, JS, Rust, Go, etc.)
        ingest_codebase(kb, './my-repo', 'my-service')
        
        # Only ingest Rust files
        ingest_codebase(kb, './my-repo', 'my-service', extensions={'.rs', '.toml'})
        
        # Custom set for specific project
        ingest_codebase(kb, './my-repo', 'my-service', 
                       extensions={'.proto', '.graphql', '.thrift'})
    """
    
    repo_path = Path(repo_path)
    
    # Default file extensions to include
    # Covers most common programming languages and config formats
    if extensions is None:
        extensions = {
            # Python
            '.py', 
            # JavaScript/TypeScript/Web
            '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json',
            # Rust
            '.rs', '.toml',
            # Go
            '.go',
            # Java/JVM
            '.java', '.kt', '.scala',
            # C/C++
            '.c', '.cpp', '.h', '.hpp',
            # Shell
            '.sh',
            # Data/Config
            '.md', '.yaml', '.yml', '.sql', '.xml', '.ini', '.conf'
        }
    
    
    # Parse .gitignore if it exists
    gitignore_spec = None
    gitignore_path = repo_path / '.gitignore'
    
    if gitignore_path.exists():
        try:
            import pathspec
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', f)
            print(f"✓ Using .gitignore from {repo_path}")
        except Exception as e:
            print(f"⚠ Could not parse .gitignore: {e}, using fallback filters")
    
    # Fallback directories to skip if no .gitignore
    # These contain generated/vendored code that shouldn't be indexed
    fallback_skip_dirs = {
        'node_modules', '__pycache__', '.git', 'dist', 'build',
        'venv', 'env', '.venv', 'target', 'vendor', '.idea', '.vscode'
    }
    
    files_ingested = 0
    
    for root, dirs, files in os.walk(repo_path):
        root_path = Path(root)
        
        # Filter directories
        if gitignore_spec:
            # Use .gitignore patterns
            dirs[:] = [
                d for d in dirs 
                if not gitignore_spec.match_file(str((root_path / d).relative_to(repo_path)))
            ]
        else:
            # Use fallback skip list
            dirs[:] = [d for d in dirs if d not in fallback_skip_dirs]
        
        for file in files:
            file_path = root_path / file
            relative_path = file_path.relative_to(repo_path)
            
            # Check .gitignore first
            if gitignore_spec and gitignore_spec.match_file(str(relative_path)):
                continue
            
            # Check extension filter
            if not any(file.endswith(ext) for ext in extensions):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Determine type
                file_type = 'documentation' if file.endswith('.md') else 'code'
                
                # Create entry
                entry = {
                    'type': file_type,
                    'path': str(relative_path),
                    'content': content,
                    'title': file,
                    'metadata': {
                        'service': service_name,
                        'language': file.split('.')[-1],
                        'absolute_path': str(file_path)
                    }
                }
                
                # Use upsert to avoid duplicates
                _upsert_entry(kb, entry)
                files_ingested += 1
                
                # Progress indicator every 100 files
                if files_ingested % 100 == 0:
                    import sys
                    print(f"  Processed {files_ingested} files...", flush=True)
                    sys.stdout.flush()  # Ensure output is visible in MCP logs
                    
            except Exception as e:
                print(f"  Skipping {relative_path}: {e}")
    
    
    print(f"✓ Ingested {files_ingested} files from {service_name}")
    return files_ingested


def ingest_adr(kb, adr_path: str, title: str, service: str = None):
    """Ingest an Architectural Decision Record

    Args:
        kb: Knowledge base table
        adr_path: Path to the ADR file
        title: ADR title
        service: Service name (e.g., 'council-cloud', 'llm-council-mcp')
                 If not provided, attempts to auto-infer from project files
    """
    # Auto-infer service from project files if not provided
    if service is None:
        service = _infer_service_name(adr_path)
        if service:
            print(f"  Auto-inferred service name: {service}")
        else:
            # Fallback to path-based inference (legacy behavior)
            path_lower = adr_path.lower()
            if 'council-cloud' in path_lower:
                service = 'council-cloud'
            elif 'llm-council' in path_lower:
                service = 'llm-council-mcp'
            else:
                service = 'unknown'
                print(f"  Warning: Could not infer service name, using 'unknown'")

    with open(adr_path, 'r') as f:
        content = f.read()

    entry = {
        'type': 'decision',
        'path': adr_path,
        'content': content,
        'title': title,
        'metadata': {
            'service': service,
            'category': 'architecture',
            'status': 'accepted'  # or 'proposed', 'deprecated'
        }
    }
    
    # Use upsert to avoid duplicates
    was_updated = _upsert_entry(kb, entry)
    action = "Updated" if was_updated else "Ingested"
    print(f"✓ {action} ADR: {title} (service: {service})")


def ingest_incident(kb, incident_data: Dict[str, Any]):
    """Ingest a production incident report"""
    
    kb.insert([{
        'type': 'incident',
        'path': incident_data.get('ticket_url', ''),
        'content': incident_data['description'],
        'title': incident_data['title'],
        'created_at': incident_data['date'],
        'metadata': {
            'service': incident_data.get('service'),
            'severity': incident_data.get('severity'),
            'resolved': incident_data.get('resolved', False),
            'root_cause': incident_data.get('root_cause', ''),
        }
    }])
    
    print(f"✓ Ingested incident: {incident_data['title']}")


def search_knowledge(kb, query: str, type_filter: Optional[str] = None, limit: int = 5):
    """Search the knowledge base"""
    
    results = kb
    
    # Apply type filter if specified
    if type_filter:
        results = results.where(kb.type == type_filter)
    
    # Semantic search
    sim = results.content.similarity(query)
    
    matches = (
        results.order_by(sim, asc=False)
        .select(
            kb.type,
            kb.path,
            kb.title,
            kb.summary,
            kb.metadata,
            kb.is_adr,
            score=sim
        )
        .limit(limit)
    )
    
    return list(matches.collect())


def get_adrs(kb, topic: Optional[str] = None):
    """Get all ADRs, optionally filtered by topic"""
    
    adrs = kb.where(kb.is_adr == True)
    
    if topic:
        sim = adrs.content.similarity(topic)
        adrs = adrs.order_by(sim, asc=False)
    else:
        adrs = adrs.order_by(kb.created_at, asc=False)
    
    return list(
        adrs.select(
            kb.path,
            kb.title,
            kb.summary,
            kb.created_at
        ).limit(10).collect()
    )


def snapshot_knowledge_base(name: str, tags: List[str] = None):
    """Create a snapshot of the knowledge base"""
    
    pxt.snapshot(
        'org_knowledge',
        name=name,
        tags=tags or []
    )
    
    print(f"✓ Created snapshot: {name}")


def list_snapshots():
    """List all knowledge base snapshots"""
    try:
        snapshots = pxt.list_snapshots('org_knowledge')
        return [{'name': s.name, 'created_at': s.created_at, 'tags': s.tags} for s in snapshots]
    except Exception:
        return []


def get_knowledge_stats(kb):
    """Get statistics about the knowledge base"""
    
    # Total counts
    total_items = kb.count()
    
    # Count by type
    type_counts = {}
    for type_val in ['code', 'decision', 'incident', 'documentation', 'meeting']:
        count = kb.where(kb.type == type_val).count()
        if count > 0:
            type_counts[type_val] = count
    
    # Count by service - use correct key name
    services = kb.select(kb.metadata['service']).collect()
    unique_services = set(
        s['metadata_service'] for s in services 
        if s.get('metadata_service')  # Pixeltable returns 'metadata_service' not 'service'
    )
    
    return {
        'total_items': total_items,
        'by_type': type_counts,
        'services_count': len(unique_services),
        'services': sorted(list(unique_services))
    }


def list_services(kb):
    """List all unique service names in the knowledge base"""
    # When selecting kb.metadata['service'], Pixeltable returns key as 'metadata_service'
    services = kb.select(kb.metadata['service']).collect()
    unique_services = sorted(set(
        s['metadata_service'] for s in services 
        if s.get('metadata_service')  # Note: key is 'metadata_service', not 'service'
    ))
    return unique_services


def delete_service_data(kb, service_name: str):
    """
    Delete all data for a specific service.
    
    Uses path-based deletion since:
    - JSON filtering (metadata['service'] == X) not SQL-expressible
    - _rowid column doesn't exist in Pixeltable
    """
    
    # Get all rows with paths and metadata
    all_rows = kb.select(kb.path, kb.metadata).collect()
    
    # Find paths to delete
    paths_to_delete = [
        row['path'] for row in all_rows
        if isinstance(row.get('metadata'), dict) 
        and row['metadata'].get('service') == service_name
    ]
    
    if not paths_to_delete:
        return {'deleted': 0, 'service': service_name, 'message': 'No data found'}
    
    # Delete rows by path (path should be unique)
    for path in paths_to_delete:
        try:
            kb.delete(kb.path == path)
        except Exception as e:
            print(f"Warning: Failed to delete {path}: {e}")
    
    return {
        'deleted': len(paths_to_delete),
        'service': service_name,
        'message': f'Deleted {len(paths_to_delete)} items from service {service_name}'
    }


def prune_old_data(kb, days_old: int):
    """Delete data older than specified days"""
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    # Count items to be deleted
    old_items = kb.where(kb.created_at < cutoff_date)
    count = old_items.count()
    
    if count == 0:
        return {'deleted': 0, 'message': f'No data older than {days_old} days'}
    
    # Delete old items
    kb.delete(kb.created_at < cutoff_date)
    
    return {'deleted': count, 'message': f'Deleted {count} items older than {days_old} days'}


if __name__ == "__main__":
    """Example setup"""
    
    print("Setting up Pixeltable knowledge base...")
    
    # Initialize
    kb = setup_knowledge_base()
    meetings = setup_meetings_table()
    
    print("\n✓ Knowledge base setup complete!")
    print("\nNext steps:")
    print("1. Ingest your codebase: ingest_codebase(kb, '/path/to/repo', 'service-name')")
    print("2. Add ADRs: ingest_adr(kb, 'path/to/adr.md', 'ADR Title')")
    print("3. Search: search_knowledge(kb, 'authentication flow')")
    print("4. Query ADRs: get_adrs(kb, 'database design')")
