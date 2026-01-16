# Configuration

Configure Luminescent Cluster for your environment.

---

## MCP Server Configuration

### Claude Code Configuration

Edit `~/.config/claude/config.json`:

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "python3",
      "args": ["/path/to/session_memory_server.py"]
    },
    "pixeltable-memory": {
      "command": "python3",
      "args": ["/path/to/pixeltable_mcp_server.py"],
      "env": {
        "PIXELTABLE_MCP_DEBUG": "1"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PIXELTABLE_HOME` | Pixeltable data directory | `~/.pixeltable` |
| `PIXELTABLE_MCP_DEBUG` | Enable debug logging | `0` |

---

## Debug Logging

Enable detailed logging for troubleshooting:

### Step 1: Add Environment Variable

```json
{
  "mcpServers": {
    "pixeltable-memory": {
      "command": "python3",
      "args": ["/path/to/pixeltable_mcp_server.py"],
      "env": {
        "PIXELTABLE_MCP_DEBUG": "1"
      }
    }
  }
}
```

### Step 2: Restart Claude Code

### Step 3: Check Logs

```bash
tail -f ~/.mcp-servers/logs/pixeltable-memory.log
```

Logs include:

- Exact paths being ingested
- File counts and timing
- Error details and stack traces
- MCP call parameters

See [Debug Logging](../DEBUG_LOGGING.md) for details.

---

## Extension System

Luminescent Cluster uses a Protocol/Registry pattern for extensibility.

### Available Extensions

| Extension | Purpose | OSS Default |
|-----------|---------|-------------|
| `TenantProvider` | Multi-tenancy isolation | None (single-user) |
| `UsageTracker` | Usage metering/billing | None (no tracking) |
| `AuditLogger` | Compliance audit logs | None (local logs only) |

### Registering Extensions

```python
from src.extensions import ExtensionRegistry

class MyTenantProvider:
    def get_tenant_id(self, ctx: dict) -> str:
        return ctx.get("x-tenant-id")

    def get_tenant_filter(self, tenant_id: str) -> dict:
        return {"tenant_id": {"$eq": tenant_id}}

    def validate_tenant_access(self, tenant_id, user_id, resource) -> bool:
        return True  # Your RBAC logic

# Register at startup
registry = ExtensionRegistry.get()
registry.tenant_provider = MyTenantProvider()
```

### Checking Extension Mode

```python
registry = ExtensionRegistry.get()
status = registry.get_status()
# {'mode': 'oss', ...} or {'mode': 'cloud', ...}
```

See [Extensions](../EXTENSIONS.md) for the full API.

---

## Advanced Tool Use

### Tool Search

Enable on-demand tool discovery:

```json
{
  "toolConfiguration": {
    "toolSearch": {
      "enabled": true,
      "provider": "regex"
    }
  }
}
```

### Programmatic Tool Calling

Enable efficient multi-step workflows:

```json
{
  "toolConfiguration": {
    "programmaticToolCalling": {
      "enabled": true
    }
  }
}
```

### Deferred Loading

Defer heavy tools until needed:

```json
{
  "toolConfiguration": {
    "deferredLoading": {
      "pixeltableMemory": true
    }
  }
}
```

---

## Performance Tuning

### Session Memory

- **Latency**: <10ms (in-memory)
- **Commit Limit**: Last 200 commits

### Long-term Memory

- **Latency**: 100-500ms (semantic search)
- **Default Limit**: 5 results per query

### Token Efficiency

| Feature | Token Savings |
|---------|---------------|
| Tool Search | 85% reduction |
| Programmatic Tool Calling | 37% reduction |
| Combined | ~90% for complex queries |

---

## Next Steps

- [Architecture](../architecture/overview.md) - Understand the system design
- [MCP Servers](../mcp/index.md) - Explore available tools
- [Operations](../operations/index.md) - Maintenance and monitoring
