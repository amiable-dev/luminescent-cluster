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
            'type': pxt.StringType(),           # 'code', 'decision', 'incident', 'meeting'
            'path': pxt.StringType(),           # File path or URL
            'content': pxt.StringType(),        # Main content
            'title': pxt.StringType(),          # Short title
            'created_at': pxt.TimestampType(),  # When created
            'metadata': pxt.JsonType(),         # Additional metadata
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
        'summary',
        generate_summary(kb.content)
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
        'is_adr',
        is_architecture_decision(kb.path, kb.content)
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
            'title': pxt.StringType(),
            'date': pxt.TimestampType(),
            'attendees': pxt.JsonType(),         # List of attendees
            'audio_path': pxt.StringType(),      # Path to audio file
            'transcript': pxt.StringType(),      # Will be computed
            'topics': pxt.JsonType(),            # Tags/topics
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


def ingest_codebase(kb, repo_path: str, service_name: str):
    """Ingest code files from a repository"""
    
    repo_path = Path(repo_path)
    
    # File extensions to include
    extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.java', '.md', '.yaml', '.yml'}
    
    # Directories to skip
    skip_dirs = {
        'node_modules', '__pycache__', '.git', 'dist', 'build',
        'venv', 'env', '.venv', 'target', 'vendor'
    }
    
    files_ingested = 0
    
    for root, dirs, files in os.walk(repo_path):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if not any(file.endswith(ext) for ext in extensions):
                continue
            
            file_path = Path(root) / file
            relative_path = file_path.relative_to(repo_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Determine type
                file_type = 'documentation' if file.endswith('.md') else 'code'
                
                kb.insert([{
                    'type': file_type,
                    'path': str(relative_path),
                    'content': content,
                    'title': file,
                    'created_at': pxt.functions.now(),
                    'metadata': {
                        'service': service_name,
                        'language': file.split('.')[-1],
                        'absolute_path': str(file_path)
                    }
                }])
                
                files_ingested += 1
                
                if files_ingested % 10 == 0:
                    print(f"  Ingested {files_ingested} files...")
                    
            except Exception as e:
                print(f"  Skipping {relative_path}: {e}")
    
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
        'created_at': pxt.functions.now(),
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
    
    return list(matches)


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
        ).limit(10)
    )


def snapshot_knowledge_base(name: str, tags: List[str] = None):
    """Create a snapshot of the knowledge base"""
    
    pxt.snapshot(
        'org_knowledge',
        name=name,
        tags=tags or []
    )
    
    print(f"✓ Created snapshot: {name}")


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
