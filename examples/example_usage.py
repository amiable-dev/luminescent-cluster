"""
Example usage of the context-aware AI development system
"""

import asyncio
from pathlib import Path
import sys

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixeltable_setup import (
    setup_knowledge_base,
    setup_meetings_table,
    ingest_codebase,
    ingest_adr,
    ingest_incident,
    search_knowledge,
    get_adrs,
    snapshot_knowledge_base
)
from datetime import datetime


def example_1_setup():
    """Example 1: Initial setup and ingestion"""
    print("=" * 60)
    print("Example 1: Setting up knowledge base")
    print("=" * 60)
    
    # Initialize tables
    kb = setup_knowledge_base()
    meetings = setup_meetings_table()
    
    print("\n✓ Knowledge base initialized")
    return kb


def example_2_ingest_code(kb):
    """Example 2: Ingest a codebase"""
    print("\n" + "=" * 60)
    print("Example 2: Ingesting codebase")
    print("=" * 60)
    
    # Ingest current directory as example
    current_dir = Path(__file__).parent.parent
    
    ingest_codebase(kb, str(current_dir), 'context-aware-system')
    
    print("\n✓ Codebase ingested")


def example_3_add_adr(kb):
    """Example 3: Add an Architectural Decision Record"""
    print("\n" + "=" * 60)
    print("Example 3: Adding ADR")
    print("=" * 60)
    
    # Create a sample ADR
    adr_path = Path(__file__).parent / 'sample_adr.md'
    
    if adr_path.exists():
        ingest_adr(
            kb,
            str(adr_path),
            'ADR 001: Tiered Memory Architecture'
        )
        print("\n✓ ADR added")
    else:
        print("\n⚠ Sample ADR not found, skipping")


def example_4_add_incident(kb):
    """Example 4: Add a production incident"""
    print("\n" + "=" * 60)
    print("Example 4: Adding incident report")
    print("=" * 60)
    
    incident = {
        'title': 'Context Window Overflow - Oct 2024',
        'description': '''
        ## Incident Summary
        AI assistant failed to provide accurate responses due to context window overflow.
        
        ## Timeline
        - 14:30 UTC: User reports inaccurate suggestions
        - 14:45 UTC: Investigation reveals 180K tokens in context
        - 15:00 UTC: Implemented Tool Search Tool
        - 15:30 UTC: System restored
        
        ## Root Cause
        All MCP tool definitions loaded upfront (55K tokens) before session started.
        
        ## Resolution
        Enabled defer_loading for non-critical tools. Token usage dropped to 8K.
        
        ## Prevention
        - Monitor token usage metrics
        - Default new tools to deferred loading
        - Alert when context exceeds 50K tokens
        ''',
        'date': datetime(2024, 10, 15, 14, 30),
        'service': 'ai-assistant',
        'severity': 'high',
        'resolved': True,
        'root_cause': 'All tools loaded upfront without Tool Search Tool'
    }
    
    ingest_incident(kb, incident)
    print("\n✓ Incident added")


def example_5_search(kb):
    """Example 5: Search the knowledge base"""
    print("\n" + "=" * 60)
    print("Example 5: Searching knowledge base")
    print("=" * 60)
    
    # Semantic search
    results = search_knowledge(
        kb,
        query="How do we manage context and memory?",
        limit=3
    )
    
    print(f"\nFound {len(results)} results for 'context and memory':")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.get('title', 'Untitled')}")
        print(f"   Type: {result.get('type')}")
        print(f"   Path: {result.get('path')}")
        print(f"   Score: {result.get('score', 0):.3f}")


def example_6_get_adrs(kb):
    """Example 6: Query ADRs by topic"""
    print("\n" + "=" * 60)
    print("Example 6: Querying ADRs")
    print("=" * 60)
    
    adrs = get_adrs(kb, topic="architecture")
    
    print(f"\nFound {len(adrs)} ADRs related to 'architecture':")
    for i, adr in enumerate(adrs, 1):
        print(f"\n{i}. {adr.get('title')}")
        print(f"   Created: {adr.get('created_at')}")
        print(f"   Path: {adr.get('path')}")


def example_7_snapshot(kb):
    """Example 7: Create snapshot"""
    print("\n" + "=" * 60)
    print("Example 7: Creating snapshot")
    print("=" * 60)
    
    snapshot_knowledge_base(
        name='example-snapshot',
        tags=['demo', 'v1.0']
    )
    
    print("\n✓ Snapshot created: example-snapshot")


def example_8_programmatic_query():
    """Example 8: Demonstrate programmatic tool calling concept"""
    print("\n" + "=" * 60)
    print("Example 8: Programmatic Tool Calling (Conceptual)")
    print("=" * 60)
    
    print("""
When Claude uses Programmatic Tool Calling, it writes orchestration code like:

```python
# Claude's orchestration code
import asyncio

# Query multiple sources in parallel
adrs, incidents, code = await asyncio.gather(
    search_organizational_memory(
        query="authentication design",
        type_filter="decision",
        limit=3
    ),
    search_organizational_memory(
        query="authentication failures",
        type_filter="incident",
        limit=5
    ),
    search_organizational_memory(
        query="authentication implementation",
        type_filter="code",
        limit=10
    )
)

# Process results (not in Claude's context!)
auth_issues = [inc for inc in incidents if inc['metadata']['severity'] == 'critical']

# Only return synthesis
summary = {
    'decision_count': len(adrs),
    'critical_incidents': len(auth_issues),
    'implementation_files': len(code)
}

print(json.dumps(summary))
```

This keeps massive intermediate data OUT of Claude's context!
Token usage: ~200KB of raw data → 1KB of summarized results
    """)


def run_all_examples():
    """Run all examples in sequence"""
    print("\n" + "=" * 60)
    print("CONTEXT-AWARE AI SYSTEM - USAGE EXAMPLES")
    print("=" * 60)
    
    # Example 1: Setup
    kb = example_1_setup()
    
    # Example 2: Ingest code
    example_2_ingest_code(kb)
    
    # Example 3: Add ADR
    example_3_add_adr(kb)
    
    # Example 4: Add incident
    example_4_add_incident(kb)
    
    # Example 5: Search
    example_5_search(kb)
    
    # Example 6: Get ADRs
    example_6_get_adrs(kb)
    
    # Example 7: Snapshot
    example_7_snapshot(kb)
    
    # Example 8: Programmatic concept
    example_8_programmatic_query()
    
    print("\n" + "=" * 60)
    print("✓ All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_examples()
