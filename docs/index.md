# Luminescent Cluster

**Context-aware AI development with persistent memory.**

Luminescent Cluster gives AI assistants persistent technical memory - the ability to recall project context, architectural decisions, incident history, and codebase knowledge across sessions and even across different LLM providers.

---

## Features

<div class="grid cards" markdown>

-   :material-memory:{ .lg .middle } **Session Memory**

    ---

    Fast access to git history, recent commits, current branch state, and active file tracking.

    [:octicons-arrow-right-24: Session Memory](mcp/session-memory.md)

-   :material-database:{ .lg .middle } **Long-term Memory**

    ---

    Semantic search over organizational knowledge: code, ADRs, incidents, and documentation.

    [:octicons-arrow-right-24: Pixeltable Memory](mcp/pixeltable-memory.md)

-   :material-puzzle:{ .lg .middle } **Extension System**

    ---

    Protocol/Registry pattern for multi-tenancy, usage tracking, and audit logging.

    [:octicons-arrow-right-24: Extensions](EXTENSIONS.md)

-   :material-chat:{ .lg .middle } **Chatbot Integrations**

    ---

    Query organizational memory from Slack, Discord, Telegram, or WhatsApp.

    [:octicons-arrow-right-24: ADR-006](adrs/ADR-006-chatbot-platform-integrations.md)

</div>

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/amiable-dev/luminescent-cluster.git
cd luminescent-cluster
./install.sh
```

### 2. Configure MCP Servers

Restart Claude Code to load the MCP servers.

### 3. Ingest Your Codebase

```
> "Ingest this codebase as 'my-service'"
```

### 4. Query Your Knowledge

```
> "What architectural decisions did we make about caching?"
> "Have we had any incidents related to database connections?"
> "Find all code related to user authentication"
```

[:octicons-arrow-right-24: Full Installation Guide](getting-started/installation.md)

---

## Architecture

Luminescent Cluster implements a three-tier memory architecture:

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

[:octicons-arrow-right-24: Architecture Overview](architecture/overview.md)

---

## Documentation

| Section | Description |
|---------|-------------|
| [Getting Started](getting-started/index.md) | Installation, quickstart, configuration |
| [Architecture](architecture/index.md) | System design and memory tiers |
| [MCP Servers](mcp/index.md) | Session and Pixeltable memory servers |
| [Memory System](memory/index.md) | Providers, MaaS, and retrieval |
| [ADRs](adrs/index.md) | Architectural Decision Records |
| [Blog](blog/index.md) | Technical deep dives |
| [Operations](operations/index.md) | Runbooks and maintenance |

---

## Python Version Requirements

!!! warning "Critical"

    The Pixeltable database is bound to the Python version that created it.
    Using a different Python minor version will cause a **silent segmentation fault**.

| Created With | Safe to Run | Unsafe |
|--------------|-------------|--------|
| 3.10.x | 3.10.0 - 3.10.99 | 3.9.x, 3.11+ |
| 3.11.x | 3.11.0 - 3.11.99 | 3.10.x, 3.12+ |
| 3.12.x | 3.12.0 - 3.12.99 | 3.11.x, 3.13+ |

[:octicons-arrow-right-24: ADR-001: Python Version Requirement](adrs/ADR-001-python-version-requirement-for-mcp-servers.md)

---

## Contributing

Luminescent Cluster is open-source under Apache 2.0 license.

```bash
# Development setup
git clone https://github.com/amiable-dev/luminescent-cluster.git
cd luminescent-cluster
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

[:octicons-arrow-right-24: Contributing Guide](https://github.com/amiable-dev/luminescent-cluster/blob/main/CONTRIBUTING.md)
