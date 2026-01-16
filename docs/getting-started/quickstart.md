# Quick Start

Get up and running with Luminescent Cluster in 5 minutes.

---

## 1. Ingest Your Codebase

After installation, navigate to your project and ask Claude to ingest it:

```
> "Ingest this codebase as 'my-service'"
```

Or use the MCP tool directly:

```python
ingest_codebase(
    repo_path=".",
    service_name="my-service"
)
```

### Custom Extensions

For non-standard projects:

```
> "Ingest this codebase as 'my-service' with only Rust files"
```

```python
ingest_codebase(
    repo_path=".",
    service_name="my-service",
    extensions=[".rs", ".toml", ".proto"]
)
```

---

## 2. Add Historical Context

### Architectural Decision Records

```
> "Add this ADR to the knowledge base"
```

```python
ingest_architectural_decision(
    adr_path="docs/adr/001-database.md",
    title="ADR 001: Database Choice"
)
```

### Incidents

```
> "Record this incident: Auth service outage on Nov 27 due to timeout"
```

```python
ingest_incident(
    title="Auth Service Outage",
    description="Timeout in auth service caused 500 errors...",
    service="auth-service"
)
```

---

## 3. Query Your Knowledge

### Session Queries (Fast)

```
> "What files were changed in the last 24 hours?"
> "Show me recent commits about authentication"
> "What's the current branch status?"
```

### Long-term Queries (Semantic)

```
> "What architectural decisions did we make about caching?"
> "Have we had any incidents related to database connections?"
> "Find all code related to user authentication"
```

### Project-specific Queries

```
> "Show me ADRs about database design in the auth-service project"
> "What incidents has payment-api had?"
> "Search for rate limiting code in the web-app service"
```

---

## 4. Complex Orchestration

Leverage programmatic tool calling for multi-step queries:

```
> "Compare our current auth implementation against the ADR and
any related incidents to suggest improvements"
```

This orchestrates:

1. Search ADRs for "authentication"
2. Search incidents for "auth-related failures"
3. Search code for "authentication implementation"
4. Synthesize findings

---

## Example Session

```
User: I'm adding rate limiting to the auth service

Claude: [Queries incidents] Note: You had an outage in November due to
rate limiter misconfiguration. The post-mortem recommended using
token bucket with adaptive limits.

User: What was the exact recommendation?

Claude: [Queries ADR] Based on ADR-012 and INC-234:
1. Use token bucket algorithm (not fixed window)
2. Start with conservative limits: 100 req/s per client
3. Add circuit breaker for external auth providers
4. Monitor p99 latency, alert at 500ms

Related code: auth-service/middleware/rate_limiter.py
```

---

## Next Steps

- [Configuration](configuration.md) - Enable debug logging
- [Architecture](../architecture/overview.md) - Understand the system
- [MCP Servers](../mcp/index.md) - Deep dive into available tools
