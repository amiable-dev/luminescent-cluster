# Memory Tiers

Deep dive into Luminescent Cluster's three-tier memory architecture.

---

## Tier 1: Session Memory

### Purpose

Fast access to current development context without latency or cost overhead.

### Implementation

`session_memory_server.py` provides MCP tools for:

| Tool | Description |
|------|-------------|
| `get_recent_commits` | Last N commits with messages, authors, dates |
| `get_changed_files` | Files modified in last N hours |
| `get_current_diff` | Staged and unstaged changes |
| `get_current_branch` | Branch info and tracking status |
| `search_commits` | Search commit messages |
| `get_file_history` | Commit history for a specific file |
| `set_task_context` | Set current work context |
| `get_task_context` | Retrieve current context |

### Characteristics

```
+------------------------------------------+
|           SESSION MEMORY                 |
+------------------------------------------+
| Storage:     In-memory (git)             |
| Latency:     <10ms                       |
| Persistence: Ephemeral                   |
| Scope:       Current repository          |
| Cost:        Zero                        |
+------------------------------------------+
```

### Use Cases

```
"What files were changed in the last 24 hours?"
"Show me recent commits about authentication"
"What's the current branch status?"
```

---

## Tier 2: Long-term Memory

### Purpose

Semantic search over organizational knowledge that persists across sessions.

### Implementation

`pixeltable_mcp_server.py` provides MCP tools for:

| Tool | Description |
|------|-------------|
| `search_organizational_memory` | Semantic search across knowledge base |
| `ingest_codebase` | Index code files with embeddings |
| `ingest_architectural_decision` | Add ADR to knowledge base |
| `ingest_incident` | Record production incident |
| `get_knowledge_base_stats` | Statistics and health |
| `list_services` | List indexed services |

### Storage Schema

```python
org_knowledge = pt.Table(
    columns={
        "type": pt.String,       # code, decision, incident, documentation
        "path": pt.String,       # File path or identifier
        "content": pt.String,    # Full text content
        "title": pt.String,      # Human-readable title
        "service": pt.String,    # Service/project name
        "created_at": pt.Timestamp,
        "updated_at": pt.Timestamp,
        "metadata": pt.JSON,     # Additional structured data
    },
    computed_columns={
        "embedding": embed_text(content),  # Auto-computed
    }
)
```

### HybridRAG Architecture

Tier 2 uses a sophisticated two-stage retrieval system:

#### Stage 1: Candidate Generation

Three parallel retrieval paths:

| Method | Strengths | Weaknesses |
|--------|-----------|------------|
| **Vector (Dense)** | Semantic similarity, handles synonyms | Miss exact matches |
| **BM25 (Sparse)** | Exact keyword matches | Miss semantic similarity |
| **Graph** | Relationships, multi-hop reasoning | Requires entity extraction |

#### Stage 2: Fusion and Reranking

1. **Reciprocal Rank Fusion (RRF)**: Merge ranked lists using `Σ 1/(k + rank_i)`
2. **Cross-Encoder Reranker**: Score top candidates with `ms-marco-MiniLM-L-6-v2`
3. **Return top 5** to context window

### Characteristics

```
+------------------------------------------+
|           LONG-TERM MEMORY               |
+------------------------------------------+
| Storage:     Pixeltable (local)          |
| Latency:     100-500ms                   |
| Persistence: Durable                     |
| Scope:       Multi-project               |
| Cost:        Embedding generation        |
+------------------------------------------+
```

### Use Cases

```
"What architectural decisions did we make about caching?"
"Have we had any incidents related to database connections?"
"Find all code related to user authentication"
```

---

## Tier 3: Intelligent Orchestration

### Purpose

Efficient coordination of multi-tool workflows without polluting context.

### Tool Search

On-demand tool discovery reduces token usage by 85%:

```
User: "How do I query the auth service incidents?"

Claude: [Discovers relevant tools on-demand]
        [Calls search_organizational_memory]
        [Returns results]
```

### Programmatic Tool Calling

Batch operations in sandbox reduce token usage by 37%:

```python
# Claude writes orchestration code
async def investigate_auth():
    # 1. Search ADRs
    adrs = await search_organizational_memory("authentication ADR")

    # 2. Search incidents
    incidents = await get_incident_history(service="auth-service")

    # 3. Search code
    code = await search_organizational_memory("authentication", type="code")

    # 4. Synthesize (only synthesis returned to context)
    return synthesize(adrs, incidents, code)
```

### Deferred Loading

Heavy tools loaded only when needed:

```json
{
  "deferredLoading": {
    "pixeltableMemory": true  // Load only when memory queries needed
  }
}
```

---

## Memory Data Flow

### Ingestion

```
Source Data → Validation → Storage → Indexing
                              ↓
                    +------------------+
                    |   Pixeltable     |
                    |   +-----------+  |
                    |   | Content   |  |
                    |   | Embedding |  | ← sentence-transformers
                    |   | Entities  |  | ← LLM extraction
                    |   +-----------+  |
                    +------------------+
                              ↓
                    +------------------+
                    | Knowledge Graph  |
                    | (NetworkX)       |
                    +------------------+
```

### Retrieval

```
User Query
    ↓
Query Rewriting (optional)
    ↓
+-------------------+
| Stage 1 (parallel)|
| +---------+       |
| | BM25    |       |
| +---------+       |
| +---------+       |
| | Vector  |       |
| +---------+       |
| +---------+       |
| | Graph   |       |
| +---------+       |
+-------------------+
    ↓
RRF Fusion
    ↓
Cross-Encoder Rerank
    ↓
Top 5 Results → Context Window
```

---

## Performance Benchmarks

| Operation | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| Session Memory Query | 5ms | 10ms | 15ms |
| Vector Search | 100ms | 200ms | 300ms |
| BM25 Search | 30ms | 60ms | 100ms |
| Graph Traversal | 50ms | 150ms | 250ms |
| HybridRAG (full) | 200ms | 400ms | 600ms |
| Cross-Encoder Rerank | 100ms | 180ms | 250ms |

---

## Related Documentation

- [Architecture Overview](overview.md) - System architecture
- [MCP Servers](../mcp/index.md) - Tool documentation
- [Memory Runbook](../operations/memory-runbook.md) - Operations guide
