# Pixeltable Memory Server

The Pixeltable Memory MCP server provides semantic search over organizational knowledge.

---

## Overview

**Implementation**: `pixeltable_mcp_server.py`

**Purpose**: Long-term persistent knowledge with semantic search

**Characteristics**:

| Property | Value |
|----------|-------|
| Latency | 100-500ms |
| Persistence | Durable (survives restarts) |
| Scope | Multi-project organizational |
| Cost | Embedding generation |

---

## Knowledge Base Tools

### search_organizational_memory

Search the organization's long-term knowledge base using semantic search.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `query` | string | required | Natural language search query |
| `limit` | integer | 5 | Maximum results |
| `type_filter` | string | - | Filter by type: code, decision, incident, documentation |
| `service_filter` | string | - | Filter by service name |

**Returns**: Matching documents with relevance scores.

**Example**:

```
> "What architectural decisions did we make about caching?"
> "Search for rate limiting code in auth-service"
```

---

### get_architectural_decisions

Retrieve Architectural Decision Records (ADRs).

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `topic` | string | - | Filter by topic |
| `service` | string | - | Filter by service |
| `limit` | integer | 5 | Maximum results |

**Returns**: Matching ADRs with summaries.

**Example**:

```
> "Show me ADRs about database design"
```

---

### get_incident_history

Get production incident history.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `service` | string | - | Filter by service |
| `limit` | integer | 5 | Maximum results |

**Returns**: Incidents with descriptions, root causes, and resolutions.

**Example**:

```
> "What incidents has the auth service had?"
```

---

## Ingestion Tools

### ingest_codebase

Index code files from a repository into the knowledge base.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `repo_path` | string | required | Path to repository |
| `service_name` | string | required | Service identifier |
| `extensions` | array | default set | File extensions to include |

**Default Extensions**: Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, Shell, SQL, YAML, Markdown

**Example**:

```
> "Ingest this codebase as 'auth-service'"
> "Ingest with only Rust files"
```

---

### ingest_architectural_decision

Add an ADR to the knowledge base.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `adr_path` | string | required | Path to ADR file |
| `title` | string | required | ADR title |
| `service` | string | - | Associated service |

**Example**:

```
> "Add docs/adr/001-database.md as 'ADR 001: Database Choice'"
```

---

### ingest_incident

Record a production incident.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | required | Incident title |
| `description` | string | required | Detailed description |
| `date` | string | - | ISO 8601 date |
| `service` | string | - | Affected service |
| `severity` | string | - | critical, high, medium, low |
| `root_cause` | string | - | Root cause analysis |

**Example**:

```
> "Record incident: Auth service outage due to timeout"
```

---

## Management Tools

### get_knowledge_base_stats

Get statistics about the knowledge base.

**Parameters**: None

**Returns**: Total items, breakdown by type, list of services.

**Example**:

```
> "Show me knowledge base stats"
```

---

### list_services

List all services in the knowledge base.

**Parameters**: None

**Returns**: List of service names.

---

### create_snapshot

Create a backup snapshot of the knowledge base.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | string | required | Snapshot name |
| `description` | string | - | Optional description |
| `tags` | array | - | Optional tags |

**Example**:

```
> "Create a snapshot called 'pre-refactor'"
```

---

## User Memory Tools

### create_user_memory

Store a user preference, fact, or decision.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `user_id` | string | required | User identifier |
| `content` | string | required | Memory content |
| `memory_type` | string | required | preference, fact, decision |
| `confidence` | number | 1.0 | Confidence score (0-1) |
| `source` | string | conversation | Memory source |

**Example**:

```
> "Remember that I prefer TypeScript over JavaScript"
```

---

### get_user_memories

Retrieve memories matching a query.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `query` | string | required | Search query |
| `user_id` | string | required | User identifier |
| `limit` | integer | 5 | Maximum results |

**Returns**: Matching memories with relevance scores.

---

### search_user_memories

Search memories with filters.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `user_id` | string | required | User identifier |
| `memory_type` | string | - | Filter by type |
| `source` | string | - | Filter by source |
| `limit` | integer | 10 | Maximum results |

---

## Use Cases

### Architectural Research

```
"What decisions did we make about authentication?"
"Why did we choose PostgreSQL over MongoDB?"
"Show me all ADRs from the payment team"
```

### Incident Analysis

```
"Have we had issues with rate limiting before?"
"What was the root cause of last month's outage?"
"Show me critical incidents in auth-service"
```

### Code Discovery

```
"Find all code related to user authentication"
"Search for rate limiting implementations"
"Show me how we handle database connections"
```

---

## Related Documentation

- [MCP Servers Overview](index.md)
- [Session Memory](session-memory.md)
- [Memory Tiers](../architecture/memory-tiers.md)
- [HybridRAG](../blog/03-hybridrag-two-stage-retrieval.md)
