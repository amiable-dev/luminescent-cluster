# Session Memory Server

The Session Memory MCP server provides fast access to git repository state and task context.

---

## Overview

**Implementation**: `session_memory_server.py`

**Purpose**: Hot context for current development state

**Characteristics**:

| Property | Value |
|----------|-------|
| Latency | <10ms |
| Persistence | Ephemeral (session-bound) |
| Scope | Current repository |
| Cost | Zero (local git) |

---

## Tools

### get_recent_commits

Retrieve recent commits from the current repository.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `limit` | integer | 10 | Number of commits to retrieve |

**Returns**: List of commits with hash, message, author, date, and statistics.

**Example**:

```
> "Show me the last 5 commits"
```

---

### get_changed_files

Get files modified in the last N hours.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `since_hours` | integer | 24 | Look back this many hours |

**Returns**: List of modified files with change types.

**Example**:

```
> "What files were changed today?"
```

---

### get_current_diff

Get staged and unstaged changes in the repository.

**Parameters**: None

**Returns**: Current diff output.

**Example**:

```
> "Show me what I've changed"
```

---

### get_current_branch

Get information about the current git branch.

**Parameters**: None

**Returns**: Branch name, commit, tracking status.

**Example**:

```
> "What branch am I on?"
```

---

### search_commits

Search commit messages for specific terms.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `query` | string | required | Search term |
| `limit` | integer | 5 | Maximum results |

**Returns**: Matching commits with context.

**Example**:

```
> "Find commits about authentication"
```

---

### get_file_history

Get commit history for a specific file.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `file_path` | string | required | Path to the file |
| `limit` | integer | 5 | Number of commits |

**Returns**: Commits that modified the file.

**Example**:

```
> "Show me the history of auth.py"
```

---

### set_task_context

Set the current task context for the session.

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `task` | string | required | Brief task description |
| `details` | object | {} | Additional task details |

**Returns**: Confirmation of context set.

**Example**:

```
> "I'm working on implementing OAuth2 PKCE flow"
```

---

### get_task_context

Retrieve the current task context.

**Parameters**: None

**Returns**: Current task and details if set.

**Example**:

```
> "What am I working on?"
```

---

## Use Cases

### Development Context

```
"What's the current branch status?"
"Show me recent commits"
"What files changed since yesterday?"
```

### Code Investigation

```
"Find commits that mention 'rate limiting'"
"Show me the history of the auth module"
"Who last modified config.py?"
```

### Task Management

```
"I'm working on the payment integration"
"What was I working on?"
```

---

## Related Documentation

- [MCP Servers Overview](index.md)
- [Pixeltable Memory](pixeltable-memory.md)
- [Architecture](../architecture/memory-tiers.md)
