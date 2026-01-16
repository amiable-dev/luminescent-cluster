# Architecture

Luminescent Cluster implements a three-tier memory architecture for context-aware AI development.

---

## Overview

<div class="grid cards" markdown>

-   :material-layers:{ .lg .middle } **System Overview**

    ---

    Three-tier architecture: Session, Long-term, and Orchestration.

    [:octicons-arrow-right-24: Overview](overview.md)

-   :material-memory:{ .lg .middle } **Memory Tiers**

    ---

    Deep dive into each memory tier's implementation and trade-offs.

    [:octicons-arrow-right-24: Memory Tiers](memory-tiers.md)

</div>

---

## Key Concepts

### Model Context Protocol (MCP)

Luminescent Cluster uses MCP as its integration standard, enabling:

- **Portability** across Claude, GPT, Gemini, and custom agents
- **Discoverability** via self-documenting tools
- **Composability** with other MCP servers

### Memory-First Architecture

The system prioritizes persistent memory over ephemeral context:

1. **Phase 0**: Evaluation, governance, and observability foundations
2. **Phase 1**: Conversational memory on Pixeltable
3. **Phase 2**: Context engineering optimization
4. **Phase 3**: HybridRAG with knowledge graph
5. **Phase 4**: Advanced features (Hindsight, MaaS)

See [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md) for the full roadmap.

### Extension System

Protocol-based extensibility for:

- Multi-tenancy (`TenantProvider`)
- Usage tracking (`UsageTracker`)
- Audit logging (`AuditLogger`)

See [ADR-005](../adrs/ADR-005-repository-organization-strategy.md) for the extension architecture.

---

## Related Documentation

- [ADR-001](../adrs/ADR-001-python-version-requirement-for-mcp-servers.md) - Python version safety
- [ADR-003](../adrs/ADR-003-project-intent-persistent-context.md) - Memory architecture
- [ADR-007](../adrs/ADR-007-cross-adr-integration-guide.md) - Cross-ADR integration
