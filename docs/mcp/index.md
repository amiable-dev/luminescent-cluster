# MCP Servers

Luminescent Cluster provides two MCP servers for context-aware AI development.

---

## Available Servers

<div class="grid cards" markdown>

-   :material-git:{ .lg .middle } **Session Memory**

    ---

    Fast access to git state, commits, diffs, and task context.

    [:octicons-arrow-right-24: Session Memory](session-memory.md)

-   :material-database:{ .lg .middle } **Pixeltable Memory**

    ---

    Semantic search over organizational knowledge.

    [:octicons-arrow-right-24: Pixeltable Memory](pixeltable-memory.md)

</div>

---

## Configuration

### Claude Code

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
      "args": ["/path/to/pixeltable_mcp_server.py"]
    }
  }
}
```

### Verification

After configuration, restart Claude Code and verify:

```
> "What MCP tools are available?"
```

---

## Tool Categories

### Session Memory Tools

| Tool | Description | Latency |
|------|-------------|---------|
| `get_recent_commits` | Recent commit history | <10ms |
| `get_changed_files` | Recently modified files | <10ms |
| `get_current_diff` | Staged/unstaged changes | <10ms |
| `get_current_branch` | Branch information | <10ms |
| `search_commits` | Search commit messages | <10ms |
| `get_file_history` | File commit history | <10ms |
| `set_task_context` | Set current task | <10ms |
| `get_task_context` | Get current task | <10ms |

### Pixeltable Memory Tools

| Tool | Description | Latency |
|------|-------------|---------|
| `search_organizational_memory` | Semantic search | 100-500ms |
| `ingest_codebase` | Index code files | Variable |
| `ingest_architectural_decision` | Add ADR | 50-100ms |
| `ingest_incident` | Record incident | 50-100ms |
| `get_knowledge_base_stats` | Statistics | <50ms |
| `list_services` | List services | <50ms |
| `create_snapshot` | Backup knowledge base | Variable |

### User Memory Tools

| Tool | Description | Latency |
|------|-------------|---------|
| `create_user_memory` | Store user preference/fact | 50-100ms |
| `get_user_memories` | Retrieve memories | 100-200ms |
| `search_user_memories` | Search with filters | 100-200ms |
| `update_user_memory` | Update memory | 50-100ms |
| `invalidate_user_memory` | Soft delete | 50-100ms |

---

## Resources

MCP Resources provide read-only context:

```
project://memory/recent_decisions     # Last N architectural decisions
project://memory/active_incidents     # Open incidents
project://memory/conventions          # Coding patterns
project://memory/dependency_graph     # Service relationships
```

---

## Performance Characteristics

### Session Memory
- **Latency**: <10ms (in-memory)
- **Scope**: Current repository
- **Commit Limit**: Last 200 commits

### Pixeltable Memory
- **Latency**: 100-500ms (semantic search)
- **Scope**: Multi-project organizational knowledge
- **Default Limit**: 5 results per query

---

## Related Documentation

- [Architecture Overview](../architecture/overview.md)
- [Memory Tiers](../architecture/memory-tiers.md)
- [Configuration](../getting-started/configuration.md)
