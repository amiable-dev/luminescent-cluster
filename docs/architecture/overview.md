# Architecture Overview

Luminescent Cluster provides AI assistants with persistent technical memory through a three-tier architecture exposed via the Model Context Protocol (MCP).

---

## System Architecture

```
+------------------------------------------------------------------+
|                 AI Assistant (Claude, GPT, etc.)                 |
+------------------------------------------------------------------+
|                  Model Context Protocol (MCP)                    |
+------------------+--------------------+--------------------------+
|    Tier 1        |      Tier 2        |        Tier 3            |
|  Session Memory  |  Long-term Memory  |    Orchestration         |
+------------------+--------------------+--------------------------+
| - Git state      | - Pixeltable DB    | - Tool Search            |
| - Recent commits | - Semantic search  | - Programmatic Calls     |
| - Current diff   | - Multi-project    | - Deferred Loading       |
| - Task context   | - ADRs, incidents  |                          |
+------------------+--------------------+--------------------------+
```

---

## Tier 1: Session Memory

**Purpose**: Fast access to current development state

**Implementation**: `session_memory_server.py`

**Capabilities**:

- Git repository state (current branch, status)
- Recent commits (last 200)
- Current diff (staged/unstaged changes)
- File change history
- Active task context

**Characteristics**:

| Property | Value |
|----------|-------|
| Latency | <10ms (in-memory) |
| Scope | Current repository |
| Persistence | Ephemeral (session-bound) |
| Cost | Zero (local computation) |

---

## Tier 2: Long-term Memory

**Purpose**: Semantic search over organizational knowledge

**Implementation**: `pixeltable_mcp_server.py` + `pixeltable_setup.py`

**Data Sources**:

- Code repositories (multi-service)
- Architectural Decision Records (ADRs)
- Production incident history
- Meeting transcripts
- Documentation

**Characteristics**:

| Property | Value |
|----------|-------|
| Latency | 100-500ms (semantic search) |
| Scope | Entire organization, cross-project |
| Persistence | Durable (survives restarts) |
| Cost | Embedding generation (local sentence-transformers) |

### HybridRAG Architecture

Long-term memory uses a two-stage retrieval architecture:

```
+---------------------------------------------------------------------+
|                    TWO-STAGE RETRIEVAL ARCHITECTURE                  |
+---------------------------------------------------------------------+
| STAGE 1: Candidate Generation (parallel)                            |
|   - Vector Similarity (Dense)                                       |
|   - Keyword BM25 (Sparse)                                           |
|   - Knowledge Graph Traversal (Relationship-based)                  |
+---------------------------------------------------------------------+
| STAGE 2: Fusion + Reranking                                         |
|   - Reciprocal Rank Fusion (RRF): Merge ranked lists                |
|   - Cross-Encoder Reranker: Score top candidates on relevance       |
|   - Return top 5 to context window                                  |
+---------------------------------------------------------------------+
```

---

## Tier 3: Intelligent Orchestration

**Purpose**: Efficient multi-tool coordination

**Mechanisms**:

| Feature | Description | Token Savings |
|---------|-------------|---------------|
| Tool Search | On-demand tool discovery | 85% |
| Programmatic Tool Calling | Batch operations in sandbox | 37% |
| Deferred Loading | Heavy tools loaded only when needed | Variable |

---

## Data Flow

### Ingestion Flow

```
User Request → MCP Tool → Pixeltable
                            ├── Content extraction
                            ├── Embedding generation (sentence-transformers)
                            ├── Entity extraction (LLM)
                            └── Knowledge graph construction
```

### Retrieval Flow

```
User Query → MCP Tool → HybridRetriever
                           ├── BM25 (keyword)
                           ├── Vector Search (semantic)
                           └── Graph Traversal (relationships)
                                    ↓
                           RRF Fusion + Reranking
                                    ↓
                           Top 5 Results → Context Window
```

---

## Security Model

### Python Version Safety

Per [ADR-001](../adrs/ADR-001-python-version-requirement-for-mcp-servers.md), the system includes 7 layers of protection against Python version mismatch:

1. Version pinning (`.python-version`)
2. Package constraint (`pyproject.toml`)
3. Runtime guard (hard exit, not warning)
4. Docker pinning
5. CI matrix testing
6. Migration procedure
7. Monitoring and observability

### Extension Trust Model

Per [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md), MaaS APIs follow a trusted orchestrator pattern:

- **Authentication**: MCP Server / CLI Layer
- **Authorization**: Orchestrator Layer
- **Capability Checks**: MaaS API Layer
- **Audit Trail**: MaaS Audit Logger

---

## Performance Characteristics

| Component | Latency | Token Impact |
|-----------|---------|--------------|
| Session Memory | <10ms | Minimal |
| Vector Search | 100-300ms | N/A |
| BM25 Search | 50-100ms | N/A |
| Graph Traversal | 50-200ms | N/A |
| HybridRAG (full) | 200-500ms | Top 5 results |
| Cross-Encoder Rerank | 100-200ms | N/A |

---

## Related Documentation

- [Memory Tiers](memory-tiers.md) - Detailed tier breakdown
- [MCP Servers](../mcp/index.md) - Tool documentation
- [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md) - Full architecture ADR
