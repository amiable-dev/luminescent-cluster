# Memory Architecture

This document describes the memory architecture implemented in Luminescent Cluster following [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md).

## Overview

The memory system provides persistent technical context for AI development assistants, enabling:
- Cross-session context retention
- User preference and fact storage
- Decision tracking with rationale
- Scope-aware retrieval (user > project > global)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Memory Module                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Schemas    │  │  Extraction  │  │  Retrieval   │           │
│  │              │  │              │  │              │           │
│  │ • Memory     │  │ • Pipeline   │  │ • Ranker     │           │
│  │ • MemoryType │  │ • Extractors │  │ • Rewriter   │           │
│  │ • Lifecycle  │  │ • Prompts    │  │ • Scoped     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Providers   │  │   Janitor    │  │ Observability│           │
│  │              │  │              │  │              │           │
│  │ • Local      │  │ • Dedup      │  │ • Metrics    │           │
│  │ • Protocol   │  │ • Contradict │  │ • Tracing    │           │
│  │              │  │ • Expiration │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Schemas (`src/memory/schemas/`)

Defines the core data models:

```python
from src.memory.schemas import Memory, MemoryType

memory = Memory(
    user_id="user-123",
    content="Prefers tabs over spaces",
    memory_type=MemoryType.PREFERENCE,
    confidence=0.9,
    source="conversation",
    raw_source="I prefer tabs over spaces",
    extraction_version=1,
    created_at=datetime.now(timezone.utc),
    last_accessed_at=datetime.now(timezone.utc),
)
```

**Memory Types:**
- `PREFERENCE` - User preferences (tabs vs spaces, editor choice)
- `FACT` - Technical facts (database used, API version)
- `DECISION` - Architectural decisions (why we chose X over Y)

### Providers (`src/memory/providers/`)

Storage implementations following the `MemoryProvider` protocol:

```python
from src.memory.providers.local import LocalMemoryProvider

provider = LocalMemoryProvider()

# Store
memory_id = await provider.store(memory, {})

# Retrieve
results = await provider.retrieve("tabs spaces", "user-123", limit=5)

# Search with filters
results = await provider.search("user-123", {"memory_type": "preference"}, limit=10)

# Delete
await provider.delete(memory_id)
```

See [providers.md](./providers.md) for implementing custom providers.

### Extraction (`src/memory/extraction/`)

Async memory extraction from conversations:

```python
from src.memory.extraction import ExtractionPipeline

pipeline = ExtractionPipeline()

# Process conversation (async, non-blocking)
task = await pipeline.process_async(
    conversation="I prefer tabs over spaces and always use pytest",
    user_id="user-123",
)
```

**Extractors:**
- `MockExtractor` - Pattern-based for testing (no API calls)
- `HaikuExtractor` - Claude Haiku with temperature=0 for determinism

### Retrieval (`src/memory/retrieval/`)

Ranked memory retrieval with query expansion:

```python
from src.memory.retrieval import MemoryRanker, QueryRewriter, ScopedRetriever

# Ranking combines similarity, recency, and confidence
ranker = MemoryRanker(
    similarity_weight=0.5,
    recency_weight=0.3,
    confidence_weight=0.2,
)

# Query rewriting expands terms for better recall
rewriter = QueryRewriter()
expanded = rewriter.rewrite("auth")  # Includes "authentication", "login", etc.

# Scope-aware retrieval respects user > project > global hierarchy
retriever = ScopedRetriever(provider)
results = await retriever.retrieve(
    query="database choice",
    user_id="user-123",
    scope="project",
    cascade=True,  # Search up hierarchy if not found
)
```

### Janitor (`src/memory/janitor/`)

Automated memory maintenance:

```python
from src.memory.janitor import JanitorRunner

janitor = JanitorRunner(provider)

# Run all cleanup tasks
result = await janitor.run_all(user_id="user-123")
# Returns: {'deduplication': {...}, 'contradiction': {...}, 'expiration': {...}}
```

**Tasks:**
- **Deduplication** - Removes memories with >85% similarity, keeps highest confidence
- **Contradiction Handling** - "Newer wins" strategy with flagging for review
- **Expiration Cleanup** - Removes memories past their `expires_at` date

### MCP Tools (`src/memory/mcp/`)

Memory tools integrated with the MCP server:

```python
from src.memory.mcp import (
    create_memory,
    get_memories,
    get_memory_by_id,
    search_memories,
    delete_memory,
    update_memory,
    invalidate_memory,
    get_memory_provenance,
)

# Create a memory
result = await create_memory(
    user_id="user-123",
    content="Prefers tabs over spaces",
    memory_type="preference",
    source="conversation",
)
print(result["memory_id"])

# Retrieve memories by query
result = await get_memories(
    query="coding style",
    user_id="user-123",
    limit=5,
)

# Search with filters
result = await search_memories(
    user_id="user-123",
    memory_type="preference",
)

# Update a memory
result = await update_memory(
    memory_id="mem-123",
    content="Now prefers spaces over tabs",
    source="user-correction",
)

# Invalidate (soft delete) a memory
result = await invalidate_memory(
    memory_id="mem-123",
    reason="User corrected this preference",
)

# Get provenance history
provenance = await get_memory_provenance(memory_id="mem-123")
```

**ADR-003 Interface Contract:**
- `create_memory` - Store new memories with type and confidence
- `get_memories` - Semantic search for relevant memories
- `update_memory` - Update existing memory content with provenance tracking
- `invalidate_memory` - Soft delete with reason (excluded from retrieval)
- `get_memory_provenance` - Full history including updates and invalidations

### Observability (`src/memory/observability/`)

OpenTelemetry-compatible metrics and tracing:

```python
from src.memory.observability import MemoryMetrics, MemoryTracer

metrics = MemoryMetrics()
metrics.record_store("preference", "user-123", success=True)
metrics.record_latency("retrieve", 45.2)

tracer = MemoryTracer()
with tracer.trace_operation("memory.store", {"user_id": "user-123"}) as span:
    # Operation
    pass
```

## Exit Criteria (ADR-003)

| Metric | Target | Achieved |
|--------|--------|----------|
| Hot memory latency | <50ms p95 | <0.05ms |
| Query latency | <200ms p95 | <1ms |
| Extraction precision | >85% | 100% |
| Cross-user leakage | Zero | Zero |
| Janitor for 10k | <10 min | <3s |

## Testing

```bash
# Run all memory tests
pytest tests/memory/ -v

# Run benchmarks
pytest tests/memory/benchmarks/ -v

# Run security tests
pytest tests/memory/security/ -v
```

## Related ADRs

- [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md) - Memory Architecture
- [ADR-005](../adrs/ADR-005-repository-organization.md) - Dual Repo Pattern
- [ADR-007](../adrs/ADR-007-cross-adr-integration.md) - Protocol Consolidation
