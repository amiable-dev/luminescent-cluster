# Memory System

The Luminescent Cluster memory system provides persistent context for AI development.

---

## Documentation

<div class="grid cards" markdown>

-   :material-file-document:{ .lg .middle } **Overview**

    ---

    Overview of the memory system architecture.

    [:octicons-arrow-right-24: Overview](../architecture/memory-tiers.md)

-   :material-package:{ .lg .middle } **Providers**

    ---

    Memory provider implementations and protocols.

    [:octicons-arrow-right-24: Providers](providers.md)

-   :material-cloud:{ .lg .middle } **MaaS**

    ---

    Memory as a Service for multi-agent collaboration.

    [:octicons-arrow-right-24: MaaS](maas.md)

</div>

---

## Architecture

The memory system is built on three layers:

### Storage Layer

- **Pixeltable**: Vector database with computed columns
- **Auto-embeddings**: Sentence-transformers for semantic search
- **Multi-project**: Service-scoped knowledge organization

### Retrieval Layer

- **HybridRAG**: BM25 + Vector + Graph fusion
- **Reranking**: Cross-encoder for relevance
- **Caching**: LRU cache with TTL

### Orchestration Layer

- **MaaS**: Agent registry, pools, handoffs
- **Janitor**: Async consolidation
- **Governance**: Provenance tracking

---

## Implementation Status

See [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md#implementation-tracker) for the full implementation tracker.

| Phase | Status |
|-------|--------|
| Phase 0: Foundations | Complete |
| Phase 1: Conversational Memory | Complete |
| Phase 2: Context Engineering | Complete |
| Phase 3: HybridRAG | Complete |
| Phase 4: Advanced (MaaS) | Complete |

**Total Tests**: 1282 memory tests passing

---

## Related Documentation

- [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md) - Memory architecture ADR
- [Architecture Overview](../architecture/overview.md)
- [Memory Runbook](../operations/memory-runbook.md)
