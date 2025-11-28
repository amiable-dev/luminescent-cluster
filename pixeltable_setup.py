"""
Pixeltable Long-term Memory Setup

Creates persistent knowledge base for:
- Code repositories
- Architectural Decision Records (ADRs)
- Production incidents
- Meeting transcripts
- Design artifacts

This is Tier 2 memory - persistent, searchable, multimodal.
"""

import pixeltable as pxt
from typing import Optional, Dict, Any, List
import os
from pathlib import Path


def setup_knowledge_base():
    """Initialize Pixeltable knowledge base with computed columns"""
    
    # Check if table already exists
    try:
        kb = pxt.get_table('org_knowledge')
        print("Knowledge base already exists")
        return kb
    except Exception:
        pass
    
    # Create main knowledge base table
    kb = pxt.create_table(
        'org_knowledge',
        {
            'type': pxt.String,           # 'code', 'decision', 'incident', 'meeting'
            'path': pxt.String,           # File path or URL
            'content': pxt.String,        # Main content
            'title': pxt.String,          # Short title
            'created_at': pxt.Timestamp,  # When created
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
        """Detect if this is an architectural decision record"""
        path_lower = path.lower()
        content_lower = content.lower()
        
        return (
            'adr' in path_lower or
            'decision' in path_lower or
            '## decision' in content_lower or
            'architectural decision' in content_lower
        )
    
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
    batch = []  # Collect files for batch insertion
    
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
                
                # Add to batch instead of inserting immediately
                batch.append({
                    'type': file_type,
                    'path': str(relative_path),
                    'content': content,
                    'title': file,
                    'created_at': datetime.now(),
                    'metadata': {
                        'service': service_name,
                        'language': file.split('.')[-1],
                        'absolute_path': str(file_path)
                    }
                })
                
                files_ingested += 1
                
                # Insert in batches of 100 for better performance
                if len(batch) >= 100:
                    kb.insert(batch)
                    batch = []
                    print(f"  Ingested {files_ingested} files...")
                    
            except Exception as e:
                print(f"  Skipping {relative_path}: {e}")
    
    # Insert any remaining items in the batch
    if batch:
        kb.insert(batch)
    
    print(f"✓ Ingested {files_ingested} files from {service_name}")
    return files_ingested


def ingest_adr(kb, adr_path: str, title: str):
    """Ingest an Architectural Decision Record"""
    
    with open(adr_path, 'r') as f:
        content = f.read()
    
    kb.insert([{
        'type': 'decision',
        'path': adr_path,
        'content': content,
        'title': title,
        'created_at': datetime.now(),
        'metadata': {
            'category': 'architecture',
            'status': 'accepted'  # or 'proposed', 'deprecated'
        }
    }])
    
    print(f"✓ Ingested ADR: {title}")


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
    
    Uses row-by-row deletion since JSON filtering (metadata['service'] == X)
    is not expressible in SQL in all Pixeltable versions.
    """
    
    # Get all rows with their IDs and metadata
    all_rows = kb.select(kb._rowid, kb.metadata).collect()
    
    # Find row IDs to delete
    rows_to_delete = [
        row['_rowid'] for row in all_rows
        if isinstance(row.get('metadata'), dict) 
        and row['metadata'].get('service') == service_name
    ]
    
    if not rows_to_delete:
        return {'deleted': 0, 'service': service_name, 'message': 'No data found'}
    
    # Delete rows by ID
    for row_id in rows_to_delete:
        kb.delete(kb._rowid == row_id)
    
    return {
        'deleted': len(rows_to_delete),
        'service': service_name,
        'message': f'Deleted {len(rows_to_delete)} items from service {service_name}'
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
