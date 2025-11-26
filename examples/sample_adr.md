# ADR 001: Tiered Memory Architecture for Context-Aware AI

**Status**: Accepted

**Date**: 2024-11-25

**Deciders**: Engineering Team

---

## Context

AI coding assistants suffer from context amnesia between sessions. Every conversation starts from scratch, requiring developers to re-explain architectural decisions, past incidents, and design rationale. This wastes time and leads to inconsistent suggestions.

We need a persistent context infrastructure that:
1. Remembers architectural decisions across sessions
2. Learns from production incidents
3. Preserves team knowledge
4. Scales to large codebases
5. Optimizes cost and performance

## Decision

We will implement a **three-tiered memory architecture**:

### Tier 1: Session Memory (Hot)
- **Technology**: Lightweight Python MCP server with gitpython
- **Data**: Recent commits, active files, current diffs, branch status
- **Latency**: <10ms (in-memory)
- **Scope**: Current repository, last 24-48 hours
- **Persistence**: Ephemeral (session-scoped)

### Tier 2: Long-term Memory (Cold)
- **Technology**: Pixeltable with semantic embeddings
- **Data**: Code repos, ADRs, incidents, meeting transcripts, designs
- **Latency**: 100-500ms (semantic search)
- **Scope**: Entire organizational history
- **Persistence**: Durable (database)

### Tier 3: Orchestration
- **Technology**: Claude's Tool Search Tool + Programmatic Tool Calling
- **Purpose**: Efficient context management and multi-step workflows
- **Benefits**: 85% token reduction (Tool Search) + 37% context reduction (PTC)

## Rationale

### Why Tiered vs. Single Database?

Different access patterns require different solutions:

- **Session memory** needs microsecond latency → in-memory structures
- **Long-term memory** needs durability → persistent database

A single database would over-engineer hot paths and under-serve cold queries.

### Why Pixeltable for Long-term Memory?

**Alternatives Considered**:
1. PostgreSQL + pgvector + S3
2. Elasticsearch + MinIO
3. Pinecone/Weaviate

**Pixeltable chosen because**:
- **Incremental computation**: Embeddings auto-update when data changes
- **Multimodal native**: Videos, images, audio, documents in one system
- **Lineage tracking**: Audit trail for compliance
- **Unified interface**: One API instead of 3+ systems

### Why Tool Search Tool?

With 50+ MCP tools, loading all definitions upfront:
- Consumes 55K+ tokens before work begins
- Degrades model accuracy (79.5% → 88.1% with Tool Search)
- Wastes context on irrelevant tools

Tool Search enables on-demand discovery while maintaining access to full toolset.

### Why Programmatic Tool Calling?

Traditional approach: Each tool result enters Claude's context
- 20 expense queries = 200KB of raw data in context
- Multiple inference passes add latency
- Intermediate results distract from synthesis

Programmatic approach: Claude orchestrates in code
- Tool results processed in sandbox
- Only final summary enters context
- 37% token reduction, 10x latency improvement

## Consequences

### Positive

✅ Context persists across sessions  
✅ AI learns from organizational history  
✅ 60-90% reduction in token costs (combined optimization)  
✅ Audit trail for compliance (healthcare, finance)  
✅ Multimodal support (meetings, designs, demos)  
✅ Automatic embedding updates (no stale indexes)  

### Negative

⚠️ Infrastructure complexity (Pixeltable deployment)  
⚠️ Initial setup time (~2-4 weeks)  
⚠️ Learning curve for team  
⚠️ Embedding generation costs (mitigated with local models)  

### Neutral

🔄 Requires discipline to document decisions  
🔄 Team must maintain knowledge base  
🔄 Periodic cleanup of outdated content  

## Implementation Plan

1. **Week 1**: Deploy session memory MCP server
2. **Week 2**: Set up Pixeltable, ingest ADRs and incidents
3. **Week 3**: Enable Tool Search Tool and Programmatic Tool Calling
4. **Week 4**: Add multimodal support (meeting transcripts)

## Metrics

**Success criteria**:
- 40% reduction in developers manually pasting context (Week 1)
- 80% ADR retrieval accuracy in architecture discussions (Week 2)
- 90% reduction in token costs for complex queries (Week 3)
- AI references 3+ historical decisions correctly (Week 4)

## Review Date

Review after 90 days of production usage (March 2025)

---

## References

- [Pixeltable Documentation](https://docs.pixeltable.com)
- [Claude Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [MCP Protocol Specification](https://modelcontextprotocol.org)

## Notes

This architecture enables **compound knowledge** - the system gets smarter over time as more context is added, rather than forgetting everything between sessions.
